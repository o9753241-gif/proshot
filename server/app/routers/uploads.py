from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Purchase, User
from app.schemas import PresignRequest, PresignResponse, PresignedUpload
from app.services.storage import presign_put

router = APIRouter()


@router.post("/photos", response_model=PresignResponse)
def presign_photos(
    req: PresignRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if req.count < 10 or req.count > 30:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "count must be 10..30")

    purchase = db.query(Purchase).filter(
        Purchase.id == req.purchase_id,
        Purchase.user_id == user.id,
        Purchase.status == "paid",
    ).first()
    if not purchase:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paid purchase not found")

    uploads = []
    for i in range(req.count):
        key = f"users/{user.id}/purchases/{purchase.id}/src/{uuid4().hex}.jpg"
        presigned = presign_put(key, content_type="image/jpeg")
        uploads.append(PresignedUpload(key=key, url=presigned["url"], fields=presigned["fields"]))

    return PresignResponse(uploads=uploads)
