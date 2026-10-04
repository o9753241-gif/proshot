"""Кто делает запрос.

Раньше личностью был заголовок X-Device-Id — строка, которую клиент мог
подставить любую. Теперь основное — X-Device-Token: device_id с подписью
сервера, выданный в обмен на заверение App Attest (routers/device.py).

Переходный режим: пока ATTEST_MODE не enforce и DEVICE_TOKEN_GRACE=1,
запрос без токена ещё принимается по X-Device-Id — чтобы сборки без токена
не сломались в момент выкладки сервера. В боевом режиме — только токен.
"""
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.services import app_attest, device_token


def get_current_user(
    x_device_token: str | None = Header(default=None),
    x_device_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    owner = device_token.owner(x_device_token)
    if owner is not None:
        # Идентификатор из подписанного токена главнее заголовка. Если они
        # расходятся, кто-то подставил чужой X-Device-Id — отказ.
        if x_device_id and x_device_id != owner:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "device_mismatch")
        device_id = owner
    # Токен с неверной подписью считается отсутствующим: в переходном режиме
    # запрос пройдёт по X-Device-Id (как и вовсе без токена), в боевом — отказ.
    elif device_token.GRACE and not app_attest.enforcing_all():
        if not x_device_id:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "X-Device-Id header required")
        device_id = x_device_id
    else:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "device_token_required")

    user = db.query(User).filter(User.device_id == device_id).first()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not registered")
    return user
