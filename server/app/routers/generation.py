"""Генерация: фото + scene_key → готовое изображение через DashScope.

── Что здесь защищено и почему ──

Раньше этот маршрут не требовал ничего: любой запрос с картинкой получал
готовый портрет за счёт владельца сервера. Теперь генерация возможна только
при оплаченной покупке с ненулевым остатком, и каждый снимок списывается.

Порядок операций важен. Фото резервируется ДО обращения к генератору и
возвращается обратно, если тот не ответил: иначе при сбое провайдера человек
терял бы оплаченную генерацию. Обратный порядок — сначала сгенерировать,
потом списать — открывает гонку: параллельные запросы успевают проскочить
мимо нулевого остатка.
"""
import os
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import GenerationEvent, Package, Purchase, User
from app.routers.styles import get_prompt, tier_for_pool, tier_of
from app.services.prompts import build_headshot_prompt
from app.services.dashscope import DashScopeError, edit_image_by_url

router = APIRouter()

MEDIA_DIR = Path("./media")
MEDIA_DIR.mkdir(exist_ok=True)

PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://89.221.203.218:8010").rstrip("/")

# Потолок скорости. Человек выбирает сцены и разглядывает результат, так что
# пятнадцати в час ему хватает с запасом. А выгрести пакет из 120 снимков
# за десять минут и вернуть деньги — уже нельзя.
MAX_PER_HOUR = 15

# Сколько держим файлы. Исходник удаляется сразу после генерации — так написано
# в политике конфиденциальности, и так теперь и происходит. Результаты живут
# сутки: галерея в приложении хранит ссылки только в памяти сессии, так что
# дольше они всё равно недоступны, а диск на сервере не бесконечный.
RESULT_TTL_HOURS = 24


def _purge_old_media() -> None:
    """Чистка по времени. Вызывается на каждой генерации — операций мало, диск дешевле."""
    cutoff = time.time() - RESULT_TTL_HOURS * 3600
    for p in MEDIA_DIR.glob("out_*"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
        except OSError:
            pass
    # Разовая уборка того, что накопилось за время, пока чистки не было вовсе.
    # После первого прохода цикл выше держит папку в норме сам.
    # Исходники не должны залёживаться вовсе: если такой файл есть и он старый,
    # значит генерация оборвалась на середине.
    for p in MEDIA_DIR.glob("in_*"):
        try:
            if p.stat().st_mtime < time.time() - 3600:
                p.unlink()
        except OSError:
            pass


def _active_purchase(db: Session, user: User) -> Purchase:
    """Самая свежая оплаченная покупка с непотраченными фото."""
    purchase = (
        db.query(Purchase)
        .filter(
            Purchase.user_id == user.id,
            Purchase.status == "paid",
            Purchase.photos_remaining > 0,
        )
        .order_by(Purchase.created_at.desc())
        .first()
    )
    if purchase is None:
        raise HTTPException(402, "no_photos_left")
    return purchase


def _check_rate(db: Session, user: User) -> None:
    """Единственное ограничение скорости: не больше MAX_PER_HOUR генераций в час.

    Человеку этого хватает с запасом — он выбирает сцены и разглядывает результат.
    А выгрести весь пакет за десять минут и вернуть деньги уже не получится.
    """
    hour_ago = datetime.utcnow() - timedelta(hours=1)
    per_hour = (
        db.query(func.count(GenerationEvent.id))
        .filter(GenerationEvent.user_id == user.id, GenerationEvent.created_at >= hour_ago)
        .scalar()
    ) or 0
    if per_hour >= MAX_PER_HOUR:
        raise HTTPException(429, "hourly_limit")


@router.post("/generate")
async def generate(
    scene_key: str = Form(...),
    image: UploadFile = File(...),
    height_cm: int | None = Form(default=None),
    weight_kg: int | None = Form(default=None),
    size: str = Form("1024x1024"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # device_id обязателен: без него ротация вариантов одежды идёт в общем ведре
    # "_shared" на всех пользователей, и в одной серии снимков костюм может
    # повториться, а другой не выпасть вовсе.
    scene_text = get_prompt(scene_key, user.device_id)
    if not scene_text:
        raise HTTPException(404, f"Unknown scene_key: {scene_key}")

    purchase = _active_purchase(db, user)

    # Сцена должна быть из списка, выбранного при оплате. Без этой проверки
    # тариф ограничивал выбор только в приложении: запрос с чужим scene_key
    # проходил, и базовый пакет дотягивался до премиальных сцен.
    # Покупки без списка (старые записи) пропускаем как раньше.
    allowed = purchase.scenes_selected or []
    if allowed and scene_key not in allowed:
        raise HTTPException(403, "scene_not_in_purchase")

    # И тир сцены должен укладываться в оплаченный пакет. Проверка именно
    # здесь, а не только в приложении: список сцен человек присылает сам
    # при оплате, и без этой строки базовым пакетом можно было оплатить
    # премиальные сцены.
    scene_tier = tier_of(scene_key)
    package = db.query(Package).filter(Package.id == purchase.package_id).first()
    if scene_tier is not None and package is not None:
        if scene_tier > tier_for_pool(package.scenes_pool):
            raise HTTPException(403, "scene_above_tier")

    _check_rate(db, user)

    # Резервируем фото до обращения к генератору.
    purchase.photos_remaining -= 1
    event = GenerationEvent(user_id=user.id, purchase_id=purchase.id, scene_key=scene_key)
    db.add(event)
    db.commit()

    in_id = uuid.uuid4().hex
    in_ext = (Path(image.filename or "photo.jpg").suffix.lower() or ".jpg")
    in_name = f"in_{in_id}{in_ext}"
    in_path = MEDIA_DIR / in_name
    out_name = f"out_{in_id}.png"
    out_path = MEDIA_DIR / out_name

    def _refund() -> None:
        purchase.photos_remaining += 1
        db.delete(event)
        db.commit()

    try:
        with open(in_path, "wb") as f:
            f.write(await image.read())

        prompt = build_headshot_prompt(scene_text, height_cm=height_cm, weight_kg=weight_kg)
        ref_url = f"{PUBLIC_BASE_URL}/api/v1/generation/media/{in_name}"
        ds_size = size.replace("x", "*")

        img_bytes = edit_image_by_url(ref_url, prompt, size=ds_size)

        with open(out_path, "wb") as f:
            f.write(img_bytes)
    except DashScopeError as e:
        _refund()
        raise HTTPException(500, f"{e}") from e
    except Exception:
        _refund()
        raise
    finally:
        # Исходное фото не хранится: провайдер его уже скачал, дальше оно не нужно.
        try:
            in_path.unlink(missing_ok=True)
        except OSError:
            pass

    _purge_old_media()

    return {
        "scene_key": scene_key,
        "image_url": f"{PUBLIC_BASE_URL}/api/v1/generation/media/{out_name}",
        "photos_remaining": purchase.photos_remaining,
    }


@router.get("/media/{name}")
def get_media(name: str):
    if "/" in name or ".." in name:
        raise HTTPException(400, "bad name")
    p = MEDIA_DIR / name
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p)
