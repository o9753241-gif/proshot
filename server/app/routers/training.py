from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Purchase, TrainingJob, TrainingStatus, User
from app.schemas import StartTrainingRequest, TrainingOut
from app.services.provod import start_training

router = APIRouter()


@router.post("", response_model=TrainingOut)
def create_training(
    req: StartTrainingRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    purchase = db.query(Purchase).filter(
        Purchase.id == req.purchase_id,
        Purchase.user_id == user.id,
        Purchase.status == "paid",
    ).first()
    if not purchase:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paid purchase not found")

    if len(req.photo_keys) < 10:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "at least 10 photos required")

    job = TrainingJob(
        user_id=user.id,
        purchase_id=purchase.id,
        status=TrainingStatus.training,
        photo_keys=req.photo_keys,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Отправляем в provod.ai (пока заглушка)
    model_id = start_training(user_id=user.id, photo_keys=req.photo_keys)
    job.provod_model_id = model_id
    db.commit()

    return TrainingOut(id=job.id, status=job.status.value, provod_model_id=job.provod_model_id)


@router.get("/{training_id}", response_model=TrainingOut)
def get_training(
    training_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = db.query(TrainingJob).filter(
        TrainingJob.id == training_id, TrainingJob.user_id == user.id
    ).first()
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return TrainingOut(id=job.id, status=job.status.value, provod_model_id=job.provod_model_id)
