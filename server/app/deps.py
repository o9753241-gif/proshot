"""Простейшая device-id аутентификация. Позже заменим на JWT."""
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User


def get_current_user(
    x_device_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not x_device_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "X-Device-Id header required")
    user = db.query(User).filter(User.device_id == x_device_id).first()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not registered")
    return user
