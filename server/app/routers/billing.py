"""Начисление пакетов фото после оплаты.

Развилка по провайдеру, а не отдельный маршрут на каждую платформу: тело запроса
и ответа одинаковое, различается только то, чем доказывается оплата. Google-ветка
оставлена нетронутой — этот сервер обслуживает iOS, но общий код проще держать
одинаковым с Android-инстансом.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Package, Purchase, User
from app.schemas import PurchaseOut, VerifyPurchaseRequest
from app.services import app_store, google_play

router = APIRouter()
log = logging.getLogger(__name__)


def _out(purchase: Purchase, sku: str) -> PurchaseOut:
    return PurchaseOut(
        id=purchase.id,
        sku=sku,
        status=purchase.status,
        scenes_selected=purchase.scenes_selected or [],
        photos_remaining=purchase.photos_remaining,
    )


@router.post("/verify", response_model=PurchaseOut)
def verify(
    req: VerifyPurchaseRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    pkg = db.query(Package).filter(Package.sku == req.sku).first()
    if not pkg:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown SKU")

    n = len(req.scenes_selected)
    if n < 1 or n > pkg.max_scenes:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"В пакете '{pkg.title}' можно выбрать от 1 до {pkg.max_scenes} сцен, получено {n}"
        )

    # ── Кто проверяет и что именно ──
    if req.provider == "app_store":
        if not req.signed_transaction:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "signed_transaction обязателен для app_store")
        result = app_store.verify_purchase(req.sku, req.signed_transaction)
        # У Apple ключ покупки — transactionId из проверенной подписи, а не то,
        # что прислал клиент. Иначе повтор можно обойти, поменяв присланную строку.
        token = result.order_id or ""
    elif req.provider == "google_play":
        if not req.purchase_token:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "purchase_token обязателен для google_play")
        result = google_play.verify_purchase(req.sku, req.purchase_token)
        token = req.purchase_token
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Неизвестный провайдер: {req.provider}")

    # ── Повтор по уже начисленной покупке ──
    # Проверяется до обращения к провайдеру только для Google: там ключ известен
    # заранее. У Apple ключ появляется после проверки подписи, поэтому здесь.
    existing = db.query(Purchase).filter(
        Purchase.provider == req.provider,
        Purchase.provider_token == token,
    ).first() if token else None
    if existing:
        return _out(existing, pkg.sku)

    if not result.ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Purchase verify failed: {result.reason}")

    if req.provider == "app_store":
        log.info(
            "Покупка Apple принята: tx=%s product=%s env=%s",
            result.order_id, result.product_id, result.environment,
        )

    purchase = Purchase(
        user_id=user.id,
        package_id=pkg.id,
        provider=req.provider,
        provider_token=token,
        status="paid",
        scenes_selected=req.scenes_selected,
        photos_remaining=pkg.total_photos,
    )
    db.add(purchase)
    try:
        db.commit()
    except IntegrityError:
        # Второй одновременный запрос с тем же токеном упёрся в уникальный индекс.
        # Начисление уже сделал первый — отдаём его результат, а не ошибку.
        db.rollback()
        existing = db.query(Purchase).filter(
            Purchase.provider == req.provider,
            Purchase.provider_token == token,
        ).first()
        if existing:
            return _out(existing, pkg.sku)
        raise
    db.refresh(purchase)

    return _out(purchase, pkg.sku)


@router.get("/purchases", response_model=list[PurchaseOut])
def my_purchases(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (
        db.query(Purchase, Package)
        .join(Package, Package.id == Purchase.package_id)
        .filter(Purchase.user_id == user.id)
        .all()
    )
    return [_out(p, pkg.sku) for p, pkg in rows]


@router.post("/apple/notifications")
async def apple_notifications(request: Request, db: Session = Depends(get_db)):
    """App Store Server Notifications V2.

    Адрес указывается в App Store Connect отдельно для боевой среды и песочницы.
    Без этого эндпоинта о возврате денег мы просто не узнаём: статус покупки
    остаётся paid навсегда.

    Отвечаем 200 всегда, когда разобрали тело: Apple повторяет доставку при любом
    другом коде, а повторять нам нечего.
    """
    body = await request.json()
    signed = body.get("signedPayload")
    if not signed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "signedPayload отсутствует")

    payload = app_store.verify_notification(signed)
    if payload is None:
        # Подпись не подтвердилась — это не наше уведомление либо проверка не настроена.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Подпись уведомления не подтверждена")

    kind = getattr(payload, "notificationType", None)
    kind = getattr(kind, "value", None) or str(kind)

    transaction_id = None
    data = getattr(payload, "data", None)
    signed_tx = getattr(data, "signedTransactionInfo", None) if data else None
    if signed_tx:
        # Транзакция внутри уведомления подписана отдельно, разбираем её тем же путём.
        inner, _ = app_store.decode_transaction(signed_tx)
        transaction_id = getattr(inner, "transactionId", None) if inner else None

    log.info("Уведомление Apple: %s tx=%s", kind, transaction_id)

    if kind == "REFUND" and transaction_id:
        purchase = db.query(Purchase).filter(
            Purchase.provider == "app_store",
            Purchase.provider_token == transaction_id,
        ).first()
        if purchase:
            # Помечаем возврат. Остаток фото НЕ обнуляем: что делать с уже
            # начисленными снимками — продуктовое решение, а не техническое.
            purchase.status = "refunded"
            db.commit()
            log.warning("Возврат по покупке %s, остаток фото %s не тронут",
                        purchase.id, purchase.photos_remaining)

    return {"ok": True}
