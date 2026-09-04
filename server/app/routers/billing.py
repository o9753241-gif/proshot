"""Начисление пакетов фото после оплаты.

Развилка по провайдеру, а не отдельный маршрут на каждую платформу: тело запроса
и ответа одинаковое, различается только то, чем доказывается оплата. Google-ветка
оставлена нетронутой — этот сервер обслуживает iOS, но общий код проще держать
одинаковым с Android-инстансом.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import GenerationEvent, Package, Purchase, User
from app.schemas import PurchaseOut, VerifyPurchaseRequest
from app.config import settings
from app.services import app_store, google_play
from app.services.i18n import REGIONAL_PRICES

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


def apply_refund(db: Session, transaction_id: str) -> Purchase | None:
    """Возврат денег: покупка закрывается, остаток фото обнуляется.

    Деньги вернули — генерации по этой покупке прекращаются немедленно.
    Обнуление и статус делают это двумя независимыми способами: _active_purchase
    в generation.py отбирает покупки по status == "paid" И photos_remaining > 0,
    так что достаточно любого из них, но полагаться на один не хочется.
    """
    purchase = db.query(Purchase).filter(
        Purchase.provider == "app_store",
        Purchase.provider_token == transaction_id,
    ).first()
    if purchase is None:
        log.warning("Возврат по неизвестной транзакции %s", transaction_id)
        return None

    was = purchase.photos_remaining
    purchase.status = "refunded"
    purchase.photos_remaining = 0
    db.commit()
    log.warning("Возврат по покупке %s: остаток %s фото обнулён", purchase.id, was)
    return purchase


def _photos_used(db: Session, purchase: Purchase) -> int:
    """Сколько снимков из пакета человек успел получить.

    Считается по событиям генерации, а не по остатку: остаток обнуляется при
    возврате, а события остаются. Благодаря этому остаток восстановим точно.
    """
    return db.query(GenerationEvent).filter(GenerationEvent.purchase_id == purchase.id).count()


def apply_refund_reversed(db: Session, transaction_id: str) -> Purchase | None:
    """Apple отменила возврат — покупка снова действует.

    Остаток восстанавливается как «куплено минус израсходовано», а не из
    сохранённого числа: событий генерации возврат не касается, так что это
    точная величина, а не догадка.
    """
    purchase = db.query(Purchase).filter(
        Purchase.provider == "app_store",
        Purchase.provider_token == transaction_id,
    ).first()
    if purchase is None:
        log.warning("Отмена возврата по неизвестной транзакции %s", transaction_id)
        return None

    pkg = db.query(Package).filter(Package.id == purchase.package_id).first()
    if pkg is None:
        return None

    purchase.status = "paid"
    purchase.photos_remaining = max(pkg.total_photos - _photos_used(db, purchase), 0)
    db.commit()
    log.warning("Возврат отменён по покупке %s: остаток восстановлен до %s",
                purchase.id, purchase.photos_remaining)
    return purchase


def _account_tenure(created_at: datetime):
    """Возраст учётной записи в терминах Apple."""
    from appstoreserverlibrary.models.AccountTenure import AccountTenure

    days = (datetime.utcnow() - created_at).days
    if days < 3:    return AccountTenure.ZERO_TO_THREE_DAYS
    if days < 10:   return AccountTenure.THREE_DAYS_TO_TEN_DAYS
    if days < 30:   return AccountTenure.TEN_DAYS_TO_THIRTY_DAYS
    if days < 90:   return AccountTenure.THIRTY_DAYS_TO_NINETY_DAYS
    if days < 180:  return AccountTenure.NINETY_DAYS_TO_ONE_HUNDRED_EIGHTY_DAYS
    if days < 365:  return AccountTenure.ONE_HUNDRED_EIGHTY_DAYS_TO_THREE_HUNDRED_SIXTY_FIVE_DAYS
    return AccountTenure.GREATER_THAN_THREE_HUNDRED_SIXTY_FIVE_DAYS


def _lifetime_purchased(db: Session, user: User):
    """Сумма покупок человека в долларах, разложенная по корзинам Apple."""
    from appstoreserverlibrary.models.LifetimeDollarsPurchased import LifetimeDollarsPurchased

    total = 0.0
    rows = (
        db.query(Purchase, Package)
        .join(Package, Package.id == Purchase.package_id)
        .filter(Purchase.user_id == user.id, Purchase.status.in_(("paid", "refunded")))
        .all()
    )
    for _p, pkg in rows:
        usd = REGIONAL_PRICES.get(pkg.sku, {}).get("USD")
        if usd:
            total += float(usd[1].lstrip("$"))

    if total <= 0:      return LifetimeDollarsPurchased.ZERO_DOLLARS
    if total < 50:      return LifetimeDollarsPurchased.ONE_CENT_TO_FORTY_NINE_DOLLARS_AND_NINETY_NINE_CENTS
    if total < 100:     return LifetimeDollarsPurchased.FIFTY_DOLLARS_TO_NINETY_NINE_DOLLARS_AND_NINETY_NINE_CENTS
    if total < 500:     return LifetimeDollarsPurchased.ONE_HUNDRED_DOLLARS_TO_FOUR_HUNDRED_NINETY_NINE_DOLLARS_AND_NINETY_NINE_CENTS
    if total < 1000:    return LifetimeDollarsPurchased.FIVE_HUNDRED_DOLLARS_TO_NINE_HUNDRED_NINETY_NINE_DOLLARS_AND_NINETY_NINE_CENTS
    if total < 2000:    return LifetimeDollarsPurchased.ONE_THOUSAND_DOLLARS_TO_ONE_THOUSAND_NINE_HUNDRED_NINETY_NINE_DOLLARS_AND_NINETY_NINE_CENTS
    return LifetimeDollarsPurchased.TWO_THOUSAND_DOLLARS_OR_GREATER


def build_consumption(db: Session, transaction_id: str):
    """Собирает ответ на CONSUMPTION_REQUEST из того, что мы действительно знаем.

    Ничего не выдумываем: чего не знаем — UNDECLARED. Apple сверяет присланное
    с собственными данными, и приукрашивание работает против нас.
    """
    from appstoreserverlibrary.models.ConsumptionRequest import ConsumptionRequest
    from appstoreserverlibrary.models.ConsumptionStatus import ConsumptionStatus
    from appstoreserverlibrary.models.DeliveryStatus import DeliveryStatus
    from appstoreserverlibrary.models.Platform import Platform
    from appstoreserverlibrary.models.PlayTime import PlayTime
    from appstoreserverlibrary.models.RefundPreference import RefundPreference
    from appstoreserverlibrary.models.UserStatus import UserStatus
    from appstoreserverlibrary.models.LifetimeDollarsRefunded import LifetimeDollarsRefunded

    purchase = db.query(Purchase).filter(
        Purchase.provider == "app_store",
        Purchase.provider_token == transaction_id,
    ).first()
    if purchase is None:
        return None

    pkg = db.query(Package).filter(Package.id == purchase.package_id).first()
    user = db.query(User).filter(User.id == purchase.user_id).first()
    if pkg is None or user is None:
        return None

    used = _photos_used(db, purchase)
    if used == 0:
        status = ConsumptionStatus.NOT_CONSUMED
        preference = RefundPreference.NO_PREFERENCE
    elif used >= pkg.total_photos:
        status = ConsumptionStatus.FULLY_CONSUMED
        preference = getattr(RefundPreference,
                             settings.apple_refund_preference_when_consumed,
                             RefundPreference.NO_PREFERENCE)
    else:
        status = ConsumptionStatus.PARTIALLY_CONSUMED
        preference = RefundPreference.NO_PREFERENCE

    consented = settings.apple_consumption_consented
    if not consented:
        # Без согласия человека Apple данные не использует, и отправлять их
        # незачем. Отвечаем честно: согласия нет.
        return ConsumptionRequest(customerConsented=False)

    return ConsumptionRequest(
        customerConsented=True,
        consumptionStatus=status,
        platform=Platform.APPLE,
        # Бесплатных генераций в ProShot нет: пакеты только платные.
        sampleContentProvided=False,
        deliveryStatus=DeliveryStatus.DELIVERED_AND_WORKING_PROPERLY,
        appAccountToken=user.device_id,
        accountTenure=_account_tenure(user.created_at),
        # Время в приложении мы не измеряем — не выдумываем.
        playTime=PlayTime.UNDECLARED,
        lifetimeDollarsRefunded=LifetimeDollarsRefunded.UNDECLARED,
        lifetimeDollarsPurchased=_lifetime_purchased(db, user),
        userStatus=UserStatus.ACTIVE,
        refundPreference=preference,
    )


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

    if transaction_id:
        if kind == "REFUND":
            apply_refund(db, transaction_id)
        elif kind == "REFUND_REVERSED":
            # Apple отказала в возврате — покупка снова действует.
            apply_refund_reversed(db, transaction_id)
        elif kind == "CONSUMPTION_REQUEST":
            # Ответ ждут в течение 12 часов, иначе решение примут без наших данных.
            payload_out = build_consumption(db, transaction_id)
            if payload_out is not None:
                app_store.send_consumption(transaction_id, payload_out)
            else:
                log.warning("CONSUMPTION_REQUEST по неизвестной транзакции %s", transaction_id)

    return {"ok": True}
