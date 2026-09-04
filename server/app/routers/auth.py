from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas import AuthRequest, AuthResponse

router = APIRouter()


@router.post("/device", response_model=AuthResponse)
def auth_by_device(req: AuthRequest, db: Session = Depends(get_db)):
    """Простая регистрация/логин по device_id. Клиент шлёт стабильный ID устройства."""
    user = db.query(User).filter(User.device_id == req.device_id).first()
    if not user:
        user = User(device_id=req.device_id)
        db.add(user)
        db.commit()
        db.refresh(user)
    # Пока token = device_id, потом заменим на JWT
    return AuthResponse(token=user.device_id, user_id=user.id)
