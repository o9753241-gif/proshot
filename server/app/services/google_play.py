"""Проверка purchase_token из Google Play Billing.

Токен приходит от клиента и сам по себе ничего не доказывает: подделать HTTP-запрос
может кто угодно. Единственный источник истины — Google Play Developer API, к которому
сервер обращается со своим ключом сервисного аккаунта.

── Что настроить один раз ──

1. Google Cloud Console → создать сервисный аккаунт, выпустить JSON-ключ.
2. Play Console → Настройки → Доступ к API → связать проект Cloud и выдать
   этому сервисному аккаунту право «Просмотр финансовых данных» и
   «Управление заказами и подписками».
3. Положить JSON на сервер и указать путь в .env:
       GOOGLE_SERVICE_ACCOUNT_JSON=/opt/proshot/play-service-account.json
       GOOGLE_PACKAGE_NAME=ai.proshot.app
4. Установить зависимость:
       pip3 install google-api-python-client google-auth --break-system-packages

Права появляются не мгновенно — Google пишет про задержку до 24 часов.
Пока ключ не подложен, сервер работает в режиме разработки (см. ниже).
"""

from dataclasses import dataclass
import logging
import os

from app.config import settings

log = logging.getLogger(__name__)


@dataclass
class VerifyResult:
    ok: bool
    reason: str = ""
    order_id: str | None = None


# Состояния покупки в ответе Play Developer API.
_PURCHASE_STATE_PURCHASED = 0
_PURCHASE_STATE_CANCELED = 1
_PURCHASE_STATE_PENDING = 2

# Уже потреблённая покупка. Начислять по ней второй раз нельзя.
_CONSUMPTION_STATE_CONSUMED = 1


def _client():
    """Ленивая инициализация клиента Play Developer API."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        settings.google_service_account_json,
        scopes=["https://www.googleapis.com/auth/androidpublisher"],
    )
    # cache_discovery=False — иначе googleapiclient пишет предупреждения и лезет в файловый кэш.
    return build("androidpublisher", "v3", credentials=creds, cache_discovery=False)


def verify_purchase(sku: str, purchase_token: str) -> VerifyResult:
    """Спрашивает у Google, действительна ли покупка.

    Возвращает ok=True только если Google подтвердил оплату и покупка ещё не
    была потреблена. Любая неопределённость трактуется как отказ: лучше не
    начислить фото по настоящей покупке (человек напишет, разберёмся вручную),
    чем раздавать платные пакеты по поддельным токенам.
    """
    path = settings.google_service_account_json

    if not path or not os.path.exists(path):
        # Режим разработки: ключа нет, проверять нечем.
        # ВНИМАНИЕ: в этом режиме сервер доверяет клиенту на слово, то есть
        # платные пакеты выдаются любому, кто отправит запрос. Допустимо только
        # на локальной машине. На боевом сервере ключ обязан быть подложен.
        if getattr(settings, "allow_unverified_purchases", False):
            log.warning(
                "Покупка %s принята БЕЗ проверки: ключ сервисного аккаунта не найден (%s)",
                sku, path or "путь не задан",
            )
            return VerifyResult(ok=True, order_id=f"dev_order_{purchase_token[:8]}")
        return VerifyResult(ok=False, reason="Проверка покупок не настроена на сервере")

    try:
        api = _client()
        resp = (
            api.purchases()
            .products()
            .get(
                packageName=settings.google_package_name,
                productId=sku,
                token=purchase_token,
            )
            .execute()
        )
    except Exception as e:  # noqa: BLE001 — наружу отдаём обобщённую причину
        log.exception("Play Developer API вернул ошибку для %s", sku)
        return VerifyResult(ok=False, reason=f"Google API: {type(e).__name__}")

    state = resp.get("purchaseState")
    if state == _PURCHASE_STATE_PENDING:
        return VerifyResult(ok=False, reason="Оплата ещё не завершена")
    if state != _PURCHASE_STATE_PURCHASED:
        return VerifyResult(ok=False, reason="Покупка отменена или возвращена")

    if resp.get("consumptionState") == _CONSUMPTION_STATE_CONSUMED:
        # Повторное начисление по уже израсходованному токену.
        return VerifyResult(ok=False, reason="Покупка уже использована")

    return VerifyResult(ok=True, order_id=resp.get("orderId"))
