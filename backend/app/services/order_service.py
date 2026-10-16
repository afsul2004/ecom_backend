from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import Dict, List, Optional
from app.models import Order, OrderItem, Product, User

# Canonical order statuses
VALID_ORDER_STATUSES = ["Pending", "Processing", "Shipped", "Delivered", "Cancelled"]
STATUS_LOOKUP = {s.lower(): s for s in VALID_ORDER_STATUSES}
CUSTOMER_CANCELLABLE_STATUSES = {"pending", "processing"}

def normalize_status(raw_status: str) -> str:
    """
    Validates and converts status string to canonical casing.
    Raises HTTPException 400 if invalid.
    """
    if not raw_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order status cannot be empty."
        )
    cleaned = raw_status.strip().lower()
    if cleaned not in STATUS_LOOKUP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid order status '{raw_status}'. Allowed statuses: {', '.join(VALID_ORDER_STATUSES)}"
        )
    return STATUS_LOOKUP[cleaned]

def get_order_item_quantities(order: Order) -> Dict[int, int]:
    """
    Aggregates required quantities by product_id across all items in the order.
    Ensures safe handling if any item has null product_id (deleted product).
    """
    quantities: Dict[int, int] = {}
    for item in order.items:
        if item.product_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot adjust inventory: Order #{order.id} contains item '{item.product_name}' whose product record has been removed."
            )
        if item.quantity <= 0:
            continue
        quantities[item.product_id] = quantities.get(item.product_id, 0) + item.quantity
    return quantities

def lock_and_fetch_products(db: Session, product_ids: List[int]) -> Dict[int, Product]:
    """
    Safely locks product inventory records in consistent ascending ID order
    to prevent deadlocks between concurrent checkouts, cancellations, and status updates.
    Ensures all requested products exist; raises 400 if any is missing.
    """
    if not product_ids:
        return {}

    # Consistent lock ordering: ascending order by ID
    sorted_ids = sorted(set(product_ids))
    products = (
        db.query(Product)
        .filter(Product.id.in_(sorted_ids))
        .order_by(Product.id.asc())
        .with_for_update()
        .all()
    )

    product_map = {p.id: p for p in products}
    missing_ids = [pid for pid in sorted_ids if pid not in product_map]
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Inventory error: Product IDs {missing_ids} no longer exist in the catalog."
        )
    return product_map

def cancel_order_internal(db: Session, order: Order) -> Order:
    """
    Internal helper to transition an order to Cancelled and restore stock exactly once.
    Must be called when the Order row is already locked.
    """
    if order.status.lower() == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order #{order.id} is already cancelled."
        )

    if order.status.lower() == "delivered":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel Order #{order.id}: Delivered orders cannot be cancelled."
        )

    # Calculate item quantities to restore
    item_quantities = get_order_item_quantities(order)
    
    # Lock products in ascending order
    product_map = lock_and_fetch_products(db, list(item_quantities.keys()))

    # Restore stock for each product
    for pid, qty in item_quantities.items():
        product_map[pid].stock += qty

    order.status = "Cancelled"
    return order

def reactivate_order_internal(db: Session, order: Order, target_status: str) -> Order:
    """
    Internal helper to transition an order from Cancelled back to an active status.
    Verifies every product has sufficient stock before deducting atomically.
    Never uses max(0, stock - qty) and never produces negative stock.
    """
    item_quantities = get_order_item_quantities(order)
    product_map = lock_and_fetch_products(db, list(item_quantities.keys()))

    # 1. Verification phase: verify sufficient stock for ALL products before deducting
    for pid, qty in item_quantities.items():
        product = product_map[pid]
        if product.stock < qty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot reactivate order: Insufficient stock for '{product.name}'. "
                    f"Available: {product.stock}, Required: {qty}."
                )
            )

    # 2. Atomic deduction phase
    for pid, qty in item_quantities.items():
        product_map[pid].stock -= qty

    order.status = target_status
    return order

def cancel_customer_order(db: Session, order_id: int, current_user: User) -> Order:
    """
    Handles customer cancellation:
    - Ownership verification (only owner can cancel, or admin)
    - Eligibility verification (only Pending or Processing)
    - Rejection of shipped, delivered, or already cancelled orders
    - Atomic stock restoration exactly once inside a database transaction
    - Thread/process safe row locking
    """
    try:
        # Lock the order row to serialize concurrent cancellation requests
        order = db.query(Order).filter(Order.id == order_id).with_for_update().first()
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

        # Restrict customers to their own orders
        if current_user.role != "admin" and order.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: You can only cancel your own orders"
            )

        # Check current status
        current_status_lower = order.status.lower()
        if current_status_lower == "cancelled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Order is already cancelled."
            )

        if current_status_lower in ["shipped", "delivered"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel order with status '{order.status}'. Customers can only cancel Pending or Processing orders."
            )

        if current_status_lower not in CUSTOMER_CANCELLABLE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel order with status '{order.status}'."
            )

        # Restore stock and update status
        cancel_order_internal(db, order)
        db.commit()
        db.refresh(order)
        return order

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Order cancellation failed: {str(e)}"
        )

def update_order_status_by_admin(db: Session, order_id: int, new_status_raw: str, admin_user: User) -> Order:
    """
    Handles admin order status transition:
    - Validates target status
    - Row locks order record
    - Enforces transition constraints (e.g. Delivered cannot be modified)
    - Restores stock exactly once when transitioning to Cancelled
    - Verifies sufficient stock and deducts atomically when reactivating from Cancelled
    - Preserves inventory unchanged for active-to-active transitions
    """
    target_status = normalize_status(new_status_raw)

    try:
        order = db.query(Order).filter(Order.id == order_id).with_for_update().first()
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

        current_status_lower = order.status.lower()
        target_status_lower = target_status.lower()

        # Idempotent: If target status matches current status
        if current_status_lower == target_status_lower:
            return order

        # Delivered orders cannot be cancelled or retroactively altered
        if current_status_lower == "delivered":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot change status of Order #{order.id}: Order has already been delivered."
            )

        # Transitioning to Cancelled: restore stock exactly once
        if target_status_lower == "cancelled":
            cancel_order_internal(db, order)

        # Transitioning from Cancelled to active status: reactivation with stock verification
        elif current_status_lower == "cancelled":
            reactivate_order_internal(db, order, target_status)

        # Active-to-active status transition (e.g. Pending -> Processing -> Shipped -> Delivered)
        else:
            order.status = target_status

        db.commit()
        db.refresh(order)
        return order

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update order status: {str(e)}"
        )
