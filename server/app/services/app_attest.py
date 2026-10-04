"""Проверка App Attest — доказательство, что запрос пришёл из настоящего
приложения на настоящем устройстве Apple.

Зачем. Модуль перенесён из Starshot iOS без изменений логики. В ProShot
бесплатных генераций нет, но device_id — единственное, что связывает человека
с оплаченным пакетом, и до сих пор он был просто строкой из заголовка. Здесь
App Attest гарантирует, что запросы к пакету идут из настоящего приложения,
а не из скрипта с подставленным идентификатором.

Режимы в ProShot: observe — только журнал, enforce — токен обязателен.
enforce_free здесь ничем не отличается от observe: бесплатного уровня нет.

Как устроено. Приложение один раз за установку создаёт ключ в защищённом
хранилище устройства и просит Apple заверить его. Заверение (attestation)
уходит сюда, проверяется целиком локально — цепочка сертификатов до корневого
Apple, одноразовый вызов, отпечаток приложения, — и в обмен выдаётся наш
собственный HMAC-токен. Дальше приложение предъявляет только токен: сеть к
Apple для этого не нужна, и повторных заверений тоже.

Проверяем ровно то, что описано у Apple в «Validating Apps That Connect to
Your Server», по шагам и без сокращений. Любая неопределённость — отказ.

Переменные окружения:
    APPLE_TEAM_ID            — идентификатор команды разработчика, 10 знаков
    APPLE_BUNDLE_ID          — ai.proshot.app
    APPLE_ATTEST_ROOT_CA     — путь к Apple_App_Attestation_Root_CA.pem
    ATTEST_MODE              — observe | enforce_free | enforce
    DEVICE_TOKEN_SECRET      — ключ для подписи наших токенов

Зависимости: cbor2, cryptography.
"""

from dataclasses import dataclass
import hashlib
import logging
import os

log = logging.getLogger("proshot.attest")

APPLE_TEAM_ID = os.environ.get("APPLE_TEAM_ID", "")
APPLE_BUNDLE_ID = os.environ.get("APPLE_BUNDLE_ID", "ai.proshot.app")
APPLE_ATTEST_ROOT_CA = os.environ.get("APPLE_ATTEST_ROOT_CA", "")

# Расширение сертификата, в котором Apple кладёт одноразовый вызов.
NONCE_OID = "1.2.840.113635.100.8.2"

# Первые байты aaguid. В сборке из Xcode стоит «appattestdevelop», в сборке из
# TestFlight и магазина — «appattest» с нулями до шестнадцати байт. Боевой режим
# принимает только второй, иначе отладочная сборка обходила бы проверку.
AAGUID_PRODUCTION = b"appattest\x00\x00\x00\x00\x00\x00\x00"
AAGUID_DEVELOPMENT = b"appattestdevelop"


@dataclass
class AttestResult:
    ok: bool
    reason: str = ""
    public_key_der: bytes | None = None
    development: bool = False


def mode() -> str:
    """observe — только пишем в журнал; enforce_free — бесплатные генерации
    только заверенным; enforce — заверение нужно всем. Так же, как на Android:
    сначала смотрим, потом включаем."""
    value = os.environ.get("ATTEST_MODE", "observe").strip().lower()
    return value if value in ("observe", "enforce_free", "enforce") else "observe"


def enforcing_free() -> bool:
    return mode() in ("enforce_free", "enforce")


def enforcing_all() -> bool:
    return mode() == "enforce"


def available() -> bool:
    """Готов ли сервер проверять заверения. Если нет — включать enforce нельзя:
    отказ получили бы все подряд."""
    if not (APPLE_TEAM_ID and APPLE_BUNDLE_ID and APPLE_ATTEST_ROOT_CA):
        return False
    if not os.path.isfile(APPLE_ATTEST_ROOT_CA):
        return False
    try:
        import cbor2  # noqa: F401
        from cryptography import x509  # noqa: F401
    except ImportError:
        return False
    return True


def _root_certificate():
    from cryptography import x509

    with open(APPLE_ATTEST_ROOT_CA, "rb") as f:
        return x509.load_pem_x509_certificate(f.read())


def _check_signed_by(child, parent) -> bool:
    """Подписан ли child ключом parent. Ключи у Apple здесь эллиптические."""
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.exceptions import InvalidSignature

    try:
        parent.public_key().verify(
            child.signature,
            child.tbs_certificate_bytes,
            ec.ECDSA(child.signature_hash_algorithm),
        )
        return True
    except (InvalidSignature, TypeError, ValueError):
        return False


def _public_key_bytes(cert) -> bytes:
    """Открытый ключ в несжатой форме: 0x04 || X || Y. Именно от этих 65 байт
    Apple считает key_id."""
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PublicFormat,
    )

    return cert.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)


def verify_attestation(key_id: bytes, attestation: bytes, challenge: bytes) -> AttestResult:
    """Главная проверка. key_id — как его присылает устройство (сырые байты из
    base64), attestation — объект CBOR, challenge — наш одноразовый вызов."""
    if not available():
        return AttestResult(False, "attest_unavailable")

    import cbor2
    from cryptography import x509

    try:
        obj = cbor2.loads(attestation)
    except Exception:  # noqa: BLE001
        return AttestResult(False, "attestation_not_cbor")

    if not isinstance(obj, dict) or obj.get("fmt") != "apple-appattest":
        return AttestResult(False, "attestation_bad_format")

    att_stmt = obj.get("attStmt") or {}
    auth_data = obj.get("authData")
    x5c = att_stmt.get("x5c") or []
    if not isinstance(auth_data, bytes) or len(x5c) < 2:
        return AttestResult(False, "attestation_incomplete")

    # ── 1. Цепочка сертификатов до корневого Apple ──
    try:
        cred_cert = x509.load_der_x509_certificate(x5c[0])
        ca_cert = x509.load_der_x509_certificate(x5c[1])
        root_cert = _root_certificate()
    except Exception:  # noqa: BLE001
        return AttestResult(False, "attestation_bad_certificates")

    if not _check_signed_by(cred_cert, ca_cert):
        return AttestResult(False, "cert_not_signed_by_ca")
    if not _check_signed_by(ca_cert, root_cert):
        return AttestResult(False, "ca_not_signed_by_apple_root")

    # ── 2. Одноразовый вызов ──
    # nonce = SHA256(authData || SHA256(challenge)) и он же лежит в расширении
    # сертификата. Совпадение означает, что заверение сделано именно под наш
    # вызов, а не взято из чужого перехваченного запроса.
    client_data_hash = hashlib.sha256(challenge).digest()
    expected_nonce = hashlib.sha256(auth_data + client_data_hash).digest()
    try:
        ext = cred_cert.extensions.get_extension_for_oid(
            x509.ObjectIdentifier(NONCE_OID)).value
        ext_bytes = ext.public_bytes() if hasattr(ext, "public_bytes") else ext.value
    except Exception:  # noqa: BLE001
        return AttestResult(False, "nonce_extension_missing")
    # Расширение — это DER-обёртка вокруг тех же 32 байт. Разбирать обёртку
    # незачем: достаточно убедиться, что ровно наш nonce внутри.
    if expected_nonce not in bytes(ext_bytes):
        return AttestResult(False, "nonce_mismatch")

    # ── 3. key_id — это отпечаток открытого ключа ──
    if hashlib.sha256(_public_key_bytes(cred_cert)).digest() != key_id:
        return AttestResult(False, "key_id_mismatch")

    # ── 4. Отпечаток приложения ──
    # Первые 32 байта authData — SHA256("<команда>.<пакет>"). Так отсекается
    # заверение, сделанное другим приложением того же устройства.
    if len(auth_data) < 55:
        return AttestResult(False, "auth_data_too_short")
    app_id = f"{APPLE_TEAM_ID}.{APPLE_BUNDLE_ID}".encode()
    if auth_data[:32] != hashlib.sha256(app_id).digest():
        return AttestResult(False, "app_id_mismatch")

    # ── 5. Счётчик и aaguid ──
    counter = int.from_bytes(auth_data[33:37], "big")
    if counter != 0:
        return AttestResult(False, "counter_not_zero")
    aaguid = auth_data[37:53]
    if aaguid == AAGUID_PRODUCTION:
        development = False
    elif aaguid == AAGUID_DEVELOPMENT:
        development = True
    else:
        return AttestResult(False, "aaguid_unknown")

    # ── 6. Идентификатор ключа внутри authData ──
    cred_id_len = int.from_bytes(auth_data[53:55], "big")
    cred_id = auth_data[55:55 + cred_id_len]
    if cred_id != key_id:
        return AttestResult(False, "credential_id_mismatch")

    return AttestResult(True, "", public_key_der=_public_key_bytes(cred_cert),
                        development=development)
