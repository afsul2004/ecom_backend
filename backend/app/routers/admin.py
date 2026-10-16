from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import shutil
import uuid
import os
from app.database import get_db
from app.models import Order, Product, User, Category
from app.schemas import (
    OrderOut, OrderStatusUpdate, ProductCreate, ProductUpdate, ProductOut, AdminStatsOut
)
from app.dependencies import get_current_admin
from app.services import order_service

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

router = APIRouter(prefix="/api/admin", tags=["Admin Portal"])

@router.get("/stats", response_model=AdminStatsOut)
def get_admin_stats(admin_user: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    # 1. Status Counts
    pending_orders = db.query(func.count(Order.id)).filter(func.lower(Order.status) == "pending").scalar() or 0
    processing_orders = db.query(func.count(Order.id)).filter(func.lower(Order.status) == "processing").scalar() or 0
    shipped_orders = db.query(func.count(Order.id)).filter(func.lower(Order.status) == "shipped").scalar() or 0
    delivered_orders = db.query(func.count(Order.id)).filter(func.lower(Order.status) == "delivered").scalar() or 0
    cancelled_orders = db.query(func.count(Order.id)).filter(func.lower(Order.status) == "cancelled").scalar() or 0
    total_orders_placed = db.query(func.count(Order.id)).scalar() or 0

    active_orders_count = pending_orders + processing_orders + shipped_orders
    non_cancelled_orders = active_orders_count + delivered_orders

    # 2. Database-side Financial Metrics (direct aggregation on Order to avoid join duplication)
    # Delivered Order Value: final payable totals of orders with status 'Delivered'
    delivered_val = db.query(
        func.coalesce(func.sum(Order.total_amount), 0.0)
    ).filter(func.lower(Order.status) == "delivered").scalar() or 0.0

    # Active Order Value: non-cancelled orders that have not yet been delivered (Pending, Processing, Shipped)
    active_val = db.query(
        func.coalesce(func.sum(Order.total_amount), 0.0)
    ).filter(func.lower(Order.status).in_(["pending", "processing", "shipped"])).scalar() or 0.0

    # Cancelled Order Value: final payable totals of orders with status 'Cancelled'
    cancelled_val = db.query(
        func.coalesce(func.sum(Order.total_amount), 0.0)
    ).filter(func.lower(Order.status) == "cancelled").scalar() or 0.0

    total_products = db.query(func.count(Product.id)).scalar() or 0
    total_users = db.query(func.count(User.id)).scalar() or 0

    return {
        "all_orders": total_orders_placed,
        "total_orders": non_cancelled_orders,
        "active_orders_count": active_orders_count,
        "pending_orders": pending_orders,
        "processing_orders": processing_orders,
        "shipped_orders": shipped_orders,
        "delivered_orders": delivered_orders,
        "cancelled_orders": cancelled_orders,

        "delivered_order_value": round(float(delivered_val), 2),
        "active_order_value": round(float(active_val), 2),
        "cancelled_order_value": round(float(cancelled_val), 2),
        "total_revenue": round(float(delivered_val), 2), # Backward compatibility: reflects actual delivered order value
        "collected_revenue": None, # Unverified receipts & UTRs are not counted as collected revenue
        "collected_revenue_status": "Not Available",
        "collected_revenue_note": "Payment provider verification not configured. Offline receipts and UTRs are unverified.",

        "total_products": total_products,
        "total_users": total_users
    }

@router.get("/orders", response_model=List[OrderOut])
def get_all_orders(
    status: Optional[str] = None,
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    query = db.query(Order)
    if status:
        query = query.filter(Order.status == status)
    return query.order_by(Order.id.desc()).all()

@router.put("/orders/{order_id}/status", response_model=OrderOut)
def update_order_status(
    order_id: int,
    req: OrderStatusUpdate,
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    return order_service.update_order_status_by_admin(db, order_id, req.status, admin_user)

@router.post("/products", response_model=ProductOut)
def create_product(
    req: ProductCreate,
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    # Verify category
    cat = db.query(Category).filter(Category.slug == req.category_slug).first()
    if not cat:
        raise HTTPException(status_code=400, detail=f"Category '{req.category_slug}' does not exist")

    product = Product(
        name=req.name.strip(),
        brand=req.brand.strip(),
        category_slug=req.category_slug,
        description=req.description,
        price=req.price,
        original_price=req.original_price,
        discount_percent=req.discount_percent or int(((req.original_price - req.price) / req.original_price) * 100),
        image_url=req.image_url.strip(),
        stock=req.stock,
        rating=req.rating or 4.5,
        is_featured=req.is_featured or False,
        is_active=True
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product

@router.put("/products/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    req: ProductUpdate,
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = req.dict(exclude_unset=True)
    for field, val in update_data.items():
        setattr(product, field, val)

    db.commit()
    db.refresh(product)
    return product

@router.delete("/products/{product_id}")
def delete_product(
    product_id: int,
    admin_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    db.delete(product)
    db.commit()
    return {"message": "Product deleted successfully"}

@router.post("/upload-image")
async def upload_product_image(
    file: UploadFile = File(...),
    admin_user: User = Depends(get_current_admin)
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files (JPEG, PNG, WebP, GIF, SVG) are allowed")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"]:
        ext = ".jpg"

    unique_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save image file: {str(e)}")

    full_url = f"http://127.0.0.1:8000/uploads/{unique_filename}"
    return {
        "filename": unique_filename,
        "image_url": full_url,
        "relative_url": f"/uploads/{unique_filename}"
    }
