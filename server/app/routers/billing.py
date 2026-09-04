from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Package, Purchase, User
from app.schemas import PurchaseOut, VerifyPurchaseRequest
from app.services.google_play import verify_purchase

router = APIRouter()


@router.post("/verify", response_model=PurchaseOut)
def verify(
    req: VerifyPurchaseRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    pkg = db.query(Package).filter(Package.sku == req.sku).first()
    if not pkg:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown SKU")

    n = len(req.scenes_selected)
    if n < 1 or n > pkg.max_scenes:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"В пакете '{pkg.title}' можно выбрать от 1 до {pkg.max_scenes} сцен, получено {n}"
        )

    existing = db.query(Purchase).filter(
        Purchase.provider == "google_play",
        Purchase.provider_token == req.purchase_token,
    ).first()
    if existing:
        return PurchaseOut(
            id=existing.id, sku=pkg.sku,
            status=existing.status,
            scenes_selected=existing.scenes_selected or [],
            photos_remaining=existing.photos_remaining
        )

    result = verify_purchase(req.sku, req.purchase_token)
    if not result.ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Purchase verify failed: {result.reason}")

    purchase = Purchase(
        user_id=user.id,
        package_id=pkg.id,
        provider="google_play",
        provider_token=req.purchase_token,
        status="paid",
        scenes_selected=req.scenes_selected,
        photos_remaining=pkg.total_photos,
    )
    db.add(purchase)
    db.commit()
    db.refresh(purchase)

    return PurchaseOut(
        id=purchase.id, sku=pkg.sku,
        status=purchase.status,
        scenes_selected=purchase.scenes_selected or [],
        photos_remaining=purchase.photos_remaining
    )


@router.get("/purchases", response_model=list[PurchaseOut])
def my_purchases(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (
        db.query(Purchase, Package)
        .join(Package, Package.id == Purchase.package_id)
        .filter(Purchase.user_id == user.id)
        .all()
    )
    return [
        PurchaseOut(
            id=p.id, sku=pkg.sku, status=p.status,
            scenes_selected=p.scenes_selected or [],
            photos_remaining=p.photos_remaining
        )
        for p, pkg in rows
    ]
