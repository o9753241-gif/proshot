"""Выдача токена устройства в обмен на заверение App Attest.

Перенесено из Starshot iOS (server/main.py, /device/challenge и /device/token)
на SQLAlchemy. Логика та же:
  - вызов одноразовый, живёт пять минут;
  - заверение проверяется локально, целиком (services/app_attest.py);
  - в боевом режиме (ATTEST_MODE=enforce) без заверения токена нет,
    а отладочное заверение (сборка из Xcode) не принимается;
  - повторная выдача токена тому же device_id — только заверённому:
    переустановка не отрезает от купленного пакета, подмена чужого
    идентификатора не проходит.
"""
import base64
import logging
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AttestChallenge, User
from app.services import app_attest, device_token

router = APIRouter()
log = logging.getLogger("proshot.device")

CHALLENGE_TTL = timedelta(minutes=5)


@router.get("/challenge")
def challenge(db: Session = Depends(get_db)):
    value = secrets.token_hex(24)
    db.add(AttestChallenge(challenge=value, created_at=datetime.utcnow()))
    db.query(AttestChallenge).filter(
        AttestChallenge.created_at < datetime.utcnow() - CHALLENGE_TTL
    ).delete(synchronize_session=False)
    db.commit()
    return {"challenge": value}


def _spend(db: Session, value: str) -> bool:
    """Забирает вызов. Удаление и проверка — одним запросом: второй раз не пройдёт."""
    if not value:
        return False
    row = db.get(AttestChallenge, value)
    if row is None:
        return False
    created = row.created_at
    deleted = db.query(AttestChallenge).filter(
        AttestChallenge.challenge == value
    ).delete(synchronize_session=False)
    db.commit()
    return deleted == 1 and datetime.utcnow() - created <= CHALLENGE_TTL


class TokenIn(BaseModel):
    device_id: str
    # В симуляторе заверения нет, поэтому поля необязательные: в режиме observe
    # токен выдаётся и без них.
    key_id: str | None = None
    attestation: str | None = None
    challenge: str | None = None


@router.post("/token")
def token(body: TokenIn, db: Session = Depends(get_db)):
    device_id = (body.device_id or "").strip()
    if not device_id or len(device_id) > 128 or "." in device_id:
        raise HTTPException(400, "bad device_id")

    attested = False
    development = False
    reason = "no_attestation"
    if body.attestation and body.key_id and body.challenge:
        if not _spend(db, body.challenge):
            reason = "challenge_unknown_or_expired"
        else:
            try:
                key_id = base64.b64decode(body.key_id)
                attestation = base64.b64decode(body.attestation)
            except Exception:  # noqa: BLE001
                reason = "bad_base64"
            else:
                result = app_attest.verify_attestation(
                    key_id, attestation, body.challenge.encode())
                attested, reason = result.ok, result.reason or "ok"
                development = bool(result.development)
                if attested and result.development and app_attest.enforcing_all():
                    attested, reason = False, "development_attestation"

    print(f"[ATTEST] device={device_id[:8]} mode={app_attest.mode()} "
          f"ok={attested} dev={development} reason={reason}", flush=True)

    if not attested and app_attest.enforcing_all():
        raise HTTPException(403, "attestation_required")

    user = db.query(User).filter(User.device_id == device_id).first()
    if user is None:
        user = User(device_id=device_id)
        db.add(user)
        db.flush()

    if user.token_issued and not attested and not device_token.GRACE:
        raise HTTPException(409, "token_already_issued")

    user.token_issued = True
    user.attested = attested
    db.commit()
    return {"token": device_token.make(device_id), "attested": attested}
