from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Package
from app.schemas import PackageOut
from app.services.i18n import pick_lang, price_for, tr_package

router = APIRouter()

DEFAULT_PACKAGES = [
    dict(sku="pack_basic",    title="Базовый",  scenes_pool=14, max_scenes=3, total_photos=20,  price_rub=990),
    dict(sku="pack_standard", title="Стандарт", scenes_pool=29, max_scenes=5, total_photos=50,  price_rub=1890),
    dict(sku="pack_premium",  title="Премиум",  scenes_pool=47, max_scenes=8, total_photos=120, price_rub=2990),
]


def _seed(db: Session):
    """Приводит таблицу пакетов в соответствие с DEFAULT_PACKAGES.

    Раньше здесь стояла проверка вида «если scenes_pool == 14 и == 47, ничего
    не делаем». Она ломалась при каждом изменении: поменяешь количество фото —
    сторож этого не заметит, решит, что пакеты уже засеяны, и в базе останутся
    старые значения. Приходилось помнить про сторож и править и его тоже.

    Теперь сравниваем поля напрямую: что разошлось — то и обновляем. Ничего
    помнить не нужно, достаточно поменять DEFAULT_PACKAGES.

    Записи не удаляются и не пересоздаются: у покупок есть внешний ключ
    package_id, и пересоздание строк оборвало бы связь с оплаченными заказами.
    """
    by_sku = {p.sku: p for p in db.query(Package).all()}
    changed = False

    for want in DEFAULT_PACKAGES:
        row = by_sku.get(want["sku"])
        if row is None:
            db.add(Package(**want))
            changed = True
            continue
        for field, value in want.items():
            if getattr(row, field) != value:
                setattr(row, field, value)
                changed = True

    if changed:
        db.commit()


@router.get("", response_model=list[PackageOut])
def list_packages(
    db: Session = Depends(get_db),
    accept_language: str | None = Header(default=None, alias="Accept-Language"),
):
    _seed(db)
    lang = pick_lang(accept_language)
    rows = db.query(Package).order_by(Package.price_rub).all()
    out = []
    for r in rows:
        _amount, currency, display = price_for(r.sku, lang)
        out.append(PackageOut(
            sku=r.sku,
            title=tr_package(r.title, lang),
            scenes_pool=r.scenes_pool,
            max_scenes=r.max_scenes,
            total_photos=r.total_photos,
            price_rub=r.price_rub,
            price_display=display,
            currency=currency,
        ))
    return out
