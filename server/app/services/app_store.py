"""Проверка покупки из App Store (StoreKit 2).

Отличие от Google Play. Там клиент присылает токен, который сам по себе ничего
не значит, и сервер обязан сходить в Play Developer API. Здесь клиент присылает
подписанный Apple документ (JWS), и подпись проверяется локально по цепочке до
корневого сертификата Apple. Сеть нужна только для необязательной перепроверки.

── Что настроить один раз ──

1. App Store Connect → Users and Access → Integrations → In-App Purchase:
   создать ключ, скачать файл .p8 (скачивается РОВНО ОДИН РАЗ), запомнить
   Key ID и Issuer ID.
2. Скачать корневые сертификаты Apple (AppleRootCA-G3.cer и остальные с
   https://www.apple.com/certificateauthority/) и положить в отдельную папку.
3. Прописать в .env:
       APPLE_BUNDLE_ID=ai.proshot.app
       APPLE_ISSUER_ID=...
       APPLE_KEY_ID=...
       APPLE_PRIVATE_KEY_PATH=/root/backend-ios/secrets/AuthKey_XXXX.p8
       APPLE_ROOT_CA_DIR=/root/backend-ios/secrets/apple_roots
4. Установить зависимость:
       pip install app-store-server-library

── Про песочницу ──

Транзакции из песочницы подписаны иначе и живут в другой среде. Проверяющий из
App Store тестирует покупку именно в песочнице, поэтому сервер обязан принимать
обе среды. Мы не угадываем среду заранее: пробуем продакшен, затем песочницу, и
берём ту, чья проверка прошла. Отказ принимать песочницу — типовая причина
отклонения приложения с формулировкой «покупка не начислила товар».
"""

from dataclasses import dataclass
import logging
import os

from app.config import settings

log = logging.getLogger(__name__)


@dataclass
class VerifyResult:
    """Форма ответа совпадает с google_play.VerifyResult — billing.py не различает провайдеров."""
    ok: bool
    reason: str = ""
    order_id: str | None = None          # transactionId, уникален у Apple
    product_id: str | None = None        # должен совпасть с sku пакета
    environment: str | None = None       # Production | Sandbox
    app_account_token: str | None = None # наш device_id, если клиент его передал


def _root_certificates() -> list[bytes]:
    """Корневые сертификаты Apple в DER. Без них проверять подпись нечем."""
    directory = settings.apple_root_ca_dir
    if not directory or not os.path.isdir(directory):
        return []
    certs = []
    for name in sorted(os.listdir(directory)):
        if name.lower().endswith((".cer", ".der")):
            with open(os.path.join(directory, name), "rb") as f:
                certs.append(f.read())
    return certs


def _verifier(environment):
    from appstoreserverlibrary.signed_data_verifier import SignedDataVerifier

    return SignedDataVerifier(
        _root_certificates(),
        settings.apple_online_checks,
        environment,
        settings.apple_bundle_id,
        settings.apple_app_apple_id or None,
    )


def _environments():
    """Порядок проверки: сначала боевая среда, затем песочница."""
    from appstoreserverlibrary.models.Environment import Environment

    return [Environment.PRODUCTION, Environment.SANDBOX]


def decode_transaction(signed_transaction: str):
    """Проверяет подпись транзакции и возвращает (нагрузка, причина отказа).

    Отдельно от verify_purchase, потому что тот же разбор нужен для транзакции,
    вложенной в уведомление App Store Server Notifications.
    """
    try:
        from appstoreserverlibrary.signed_data_verifier import VerificationException
    except ImportError:
        return None, "app-store-server-library не установлена"

    last_reason = ""
    for env in _environments():
        try:
            return _verifier(env).verify_and_decode_signed_transaction(signed_transaction), ""
        except VerificationException as e:
            # Несовпадение среды выглядит как ошибка проверки, поэтому пробуем вторую.
            last_reason = str(e)
        except Exception as e:  # noqa: BLE001
            log.exception("Проверка подписи Apple упала")
            return None, f"Apple verify: {type(e).__name__}"
    return None, last_reason


def verify_purchase(sku: str, signed_transaction: str) -> VerifyResult:
    """Проверяет подписанную транзакцию и сверяет её с ожидаемым пакетом.

    Как и в Google-ветке, любая неопределённость трактуется как отказ: лучше не
    начислить фото по настоящей покупке и разобрать это руками, чем раздавать
    платные пакеты по подделанным запросам.
    """
    if not settings.apple_bundle_id:
        return VerifyResult(ok=False, reason="APPLE_BUNDLE_ID не задан")

    roots = _root_certificates()
    if not roots:
        # Проверять нечем. Ветка «доверять клиенту» существует только для локальной
        # разработки и включается тем же флагом, что и у Google.
        if settings.allow_unverified_purchases:
            log.warning(
                "Покупка %s принята БЕЗ проверки: нет корневых сертификатов Apple (%s)",
                sku, settings.apple_root_ca_dir or "путь не задан",
            )
            return VerifyResult(
                ok=True,
                order_id=f"dev_tx_{signed_transaction[:16]}",
                product_id=sku,
                environment="Dev",
            )
        return VerifyResult(ok=False, reason="Проверка покупок Apple не настроена на сервере")

    payload, last_reason = decode_transaction(signed_transaction)
    if payload is None:
        return VerifyResult(ok=False, reason=f"Подпись не подтверждена: {last_reason}")

    if payload.bundleId != settings.apple_bundle_id:
        return VerifyResult(ok=False, reason="Транзакция от другого приложения")

    if payload.productId != sku:
        # Клиент попросил начислить не тот пакет, за который заплатил.
        return VerifyResult(ok=False, reason="Товар в транзакции не совпадает с пакетом")

    if getattr(payload, "revocationDate", None):
        return VerifyResult(ok=False, reason="Покупка возвращена")

    environment = getattr(payload.environment, "value", None) or str(payload.environment)

    return VerifyResult(
        ok=True,
        order_id=payload.transactionId,
        product_id=payload.productId,
        environment=environment,
        app_account_token=getattr(payload, "appAccountToken", None),
    )


def verify_notification(signed_payload: str):
    """Разбирает уведомление App Store Server Notifications V2.

    Возвращает разобранную нагрузку или None, если подпись не подтвердилась.
    Апстрим шлёт уведомления и из песочницы, поэтому среды перебираются так же.
    """
    if not _root_certificates():
        return None
    try:
        from appstoreserverlibrary.signed_data_verifier import VerificationException
    except ImportError:
        return None

    for env in _environments():
        try:
            return _verifier(env).verify_and_decode_notification(signed_payload)
        except VerificationException:
            continue
        except Exception:  # noqa: BLE001
            log.exception("Разбор уведомления Apple упал")
            return None
    return None


def transaction_info(transaction_id: str):
    """Необязательная перепроверка через App Store Server API.

    Нужна для разбора спорных случаев: подпись говорит, что покупка была, а этот
    вызов показывает её текущее состояние — в том числе возврат.
    """
    from appstoreserverlibrary.api_client import AppStoreServerAPIClient

    if not settings.apple_private_key_path or not os.path.exists(settings.apple_private_key_path):
        return None

    with open(settings.apple_private_key_path, "rb") as f:
        signing_key = f.read()

    for env in _environments():
        try:
            client = AppStoreServerAPIClient(
                signing_key,
                settings.apple_key_id,
                settings.apple_issuer_id,
                settings.apple_bundle_id,
                env,
            )
            return client.get_transaction_info(transaction_id)
        except Exception:  # noqa: BLE001
            continue
    return None

def send_consumption(transaction_id: str, consumption_request) -> bool:
    """Отправляет данные о потреблении в App Store Server API.

    Apple ждёт ответ в течение 12 часов после CONSUMPTION_REQUEST. Если не
    ответить, решение по возврату принимается без наших данных.

    Среда определяется перебором: уведомление могло прийти из песочницы.
    """
    from appstoreserverlibrary.api_client import AppStoreServerAPIClient

    if not settings.apple_private_key_path or not os.path.exists(settings.apple_private_key_path):
        log.warning("Данные о потреблении не отправлены: нет ключа App Store Server API")
        return False

    with open(settings.apple_private_key_path, "rb") as f:
        signing_key = f.read()

    for env in _environments():
        try:
            client = AppStoreServerAPIClient(
                signing_key,
                settings.apple_key_id,
                settings.apple_issuer_id,
                settings.apple_bundle_id,
                env,
            )
            client.send_consumption_data(transaction_id, consumption_request)
            log.info("Данные о потреблении отправлены для %s (%s)", transaction_id, env)
            return True
        except Exception as e:  # noqa: BLE001
            last = e
            continue
    log.warning("Данные о потреблении не отправлены для %s: %s", transaction_id, type(last).__name__)
    return False
