from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import Wishlist, Product, User
from app.schemas import WishlistToggle, ProductOut
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/wishlist", tags=["Wishlist"])

@router.get("", response_model=List[ProductOut])
def get_user_wishlist(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.query(Wishlist).filter(Wishlist.user_id == current_user.id).all()
    product_ids = [item.product_id for item in items]
    if not product_ids:
        return []
    return db.query(Product).filter(Product.id.in_(product_ids), Product.is_active == True).all()

@router.post("/toggle")
def toggle_wishlist_item(req: WishlistToggle, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == req.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    existing = db.query(Wishlist).filter(
        Wishlist.user_id == current_user.id,
        Wishlist.product_id == req.product_id
    ).first()

    if existing:
        db.delete(existing)
        db.commit()
        return {"action": "removed", "message": "Product removed from wishlist"}
    else:
        new_item = Wishlist(user_id=current_user.id, product_id=req.product_id)
        db.add(new_item)
        db.commit()
        return {"action": "added", "message": "Product added to wishlist"}
