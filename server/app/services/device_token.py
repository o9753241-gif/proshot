"""Подписанный токен устройства: device_id + HMAC сервера.

Подделать подпись без секрета нельзя, а секрет в приложение не попадает.
Токен выдаётся в /api/v1/device/token в обмен на заверение App Attest и
дальше идёт с каждым запросом в заголовке X-Device-Token. Тот же приём, что
в Starshot iOS и на Android (Play Integrity + токен).
"""
import hashlib
import hmac
import os
import secrets
import time
from pathlib import Path

# Рядом с базой, в рабочей папке сервиса. Создаётся один раз.
_SECRET_FILE = Path("./.device_secret")


def _secret() -> bytes:
    raw = os.environ.get("DEVICE_TOKEN_SECRET", "").strip()
    if raw:
        return raw.encode()
    # Запасной путь, если секрета нет в .env (deploy.sh его туда кладёт).
    # Сервис запущен в нескольких процессах, и у всех секрет обязан быть один:
    # файл создаётся атомарно (O_EXCL), остальные процессы читают готовый.
    try:
        fd = os.open(_SECRET_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(secrets.token_hex(32))
    for _ in range(50):
        value = _SECRET_FILE.read_text(encoding="utf-8").strip()
        if len(value) == 64:
            return value.encode()
        time.sleep(0.05)
    raise RuntimeError("device secret file is empty or damaged")


SECRET = _secret()

# Переходный режим: пока он включён и ATTEST_MODE не enforce, запросы без
# токена ещё принимаются по X-Device-Id. Нужен, чтобы старые сборки работали,
# пока новая не у всех.
GRACE = os.environ.get("DEVICE_TOKEN_GRACE", "1").strip() == "1"


def make(device_id: str) -> str:
    sig = hmac.new(SECRET, device_id.encode(), hashlib.sha256).hexdigest()[:32]
    return device_id + "." + sig


def owner(token: str | None) -> str | None:
    """device_id из токена, если подпись верна; иначе None."""
    if not token or "." not in token:
        return None
    device_id, _, sig = token.rpartition(".")
    if not device_id:
        return None
    good = hmac.new(SECRET, device_id.encode(), hashlib.sha256).hexdigest()[:32]
    return device_id if hmac.compare_digest(sig, good) else None
