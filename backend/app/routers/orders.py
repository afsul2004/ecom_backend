from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import shutil
import uuid
from app.database import get_db
from app.models import Order, OrderItem, Product, User
from app.schemas import OrderCreate, OrderOut
from app.dependencies import get_current_user_optional, get_current_user
from app.services import order_service

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

router = APIRouter(prefix="/api/orders", tags=["Orders"])

@router.post("", response_model=OrderOut)
def create_order(
    req: OrderCreate,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    # 1. Validation
    if not req.items:
        raise HTTPException(status_code=400, detail="Cart is empty. Please add items before checkout.")

    clean_phone = req.phone.strip()
    if len(clean_phone) != 10 or not clean_phone.isdigit():
        raise HTTPException(status_code=400, detail="Please enter a valid 10-digit mobile number.")

    clean_pincode = req.pincode.strip()
    if len(clean_pincode) != 6 or not clean_pincode.isdigit():
        raise HTTPException(status_code=400, detail="Please enter a valid 6-digit delivery pincode.")

    # 2. Database validation & server-side recalculation
    calculated_subtotal = 0.0
    items_to_create = []

    try:
        # Atomic transaction with consistent lock ordering (ascending product ID)
        # Consolidate quantities per product ID to handle multiple entries for same product
        qty_by_pid = {}
        for item_input in req.items:
            qty_by_pid[item_input.product_id] = qty_by_pid.get(item_input.product_id, 0) + item_input.quantity

        sorted_product_ids = sorted(qty_by_pid.keys())
        products = (
            db.query(Product)
            .filter(Product.id.in_(sorted_product_ids), Product.is_active == True)
            .order_by(Product.id.asc())
            .with_for_update()
            .all()
        )
        product_map = {p.id: p for p in products}

        for pid in sorted_product_ids:
            if pid not in product_map:
                raise HTTPException(status_code=404, detail=f"Product ID {pid} is no longer available.")
            
            product = product_map[pid]
            requested_qty = qty_by_pid[pid]

            if product.stock < requested_qty:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient stock for '{product.name}'. Available: {product.stock}, Requested: {requested_qty}"
                )
            
            # Decrement inventory safely
            product.stock -= requested_qty
            
            unit_price = float(product.price)
            item_total = unit_price * requested_qty
            calculated_subtotal += item_total

            items_to_create.append({
                "product_id": product.id,
                "product_name": product.name,
                "price": unit_price,
                "quantity": requested_qty,
                "image": product.image_url
            })

        # Calculate promotional discount (e.g. ₹1000 off on orders >= ₹2000)
        discount_amount = 1000.0 if calculated_subtotal >= 2000.0 else 0.0
        final_total = max(0.0, calculated_subtotal - discount_amount)

        # 3. Create Order Record
        username = current_user.name if current_user else req.full_name
        user_id = current_user.id if current_user else None

        new_order = Order(
            user_id=user_id,
            username=username,
            full_name=req.full_name.strip(),
            phone=clean_phone,
            address=req.address.strip(),
            city=req.city.strip(),
            district=req.district.strip(),
            pincode=clean_pincode,
            payment_method=req.payment_method,
            payment_receipt=req.payment_receipt,
            payment_utr=req.payment_utr.strip() if req.payment_utr else None,
            subtotal=calculated_subtotal,
            discount_amount=discount_amount,
            total_amount=final_total,
            status="Pending"
        )
        db.add(new_order)
        db.flush() # Flush to generate new_order.id

        # 4. Create Order Items
        for item_data in items_to_create:
            order_item = OrderItem(
                order_id=new_order.id,
                product_id=item_data["product_id"],
                product_name=item_data["product_name"],
                price=item_data["price"],
                quantity=item_data["quantity"],
                image=item_data["image"]
            )
            db.add(order_item)

        db.commit()
        db.refresh(new_order)
        return new_order

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Order placement failed: {str(e)}")

@router.get("", response_model=List[OrderOut])
def list_user_orders(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Returns orders placed by the logged in user
    return db.query(Order).filter(Order.user_id == current_user.id).order_by(Order.id.desc()).all()

@router.get("/{order_id}", response_model=OrderOut)
def get_order_details(order_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Restrict customers from viewing other customers' orders
    if current_user.role != "admin" and order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized access to order details")
    
    return order

@router.put("/{order_id}/cancel", response_model=OrderOut)
def cancel_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return order_service.cancel_customer_order(db, order_id, current_user)

@router.post("/upload-receipt")
async def upload_payment_receipt(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files (JPEG, PNG, WebP) are allowed")
    
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        ext = ".jpg"
    
    unique_filename = f"receipt_{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save payment receipt: {str(e)}")
    
    return {
        "filename": unique_filename,
        "receipt_url": f"/uploads/{unique_filename}"
    }
