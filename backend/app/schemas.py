from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime

# ================= AUTH SCHEMAS =================
class UserRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=100)
    phone: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class ForgotPasswordReq(BaseModel):
    email: EmailStr
    new_password: str = Field(..., min_length=6)

class DeleteAccountReq(BaseModel):
    password: str

class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    phone: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

# ================= CATEGORY SCHEMAS =================
class CategoryOut(BaseModel):
    id: int
    name: str
    slug: str
    icon: Optional[str] = "ShoppingBag"
    description: Optional[str] = None

    class Config:
        from_attributes = True

# ================= PRODUCT SCHEMAS =================
class ProductOut(BaseModel):
    id: int
    name: str
    brand: str
    category_slug: str
    description: Optional[str] = None
    price: float
    original_price: float
    discount_percent: int
    image_url: str
    stock: int
    rating: float
    is_featured: bool
    is_active: bool

    class Config:
        from_attributes = True

class ProductCreate(BaseModel):
    name: str
    brand: str
    category_slug: str
    description: Optional[str] = None
    price: float = Field(..., gt=0)
    original_price: float = Field(..., gt=0)
    discount_percent: Optional[int] = 0
    image_url: str
    stock: int = Field(50, ge=0)
    rating: Optional[float] = 4.5
    is_featured: Optional[bool] = False

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    brand: Optional[str] = None
    category_slug: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    original_price: Optional[float] = None
    discount_percent: Optional[int] = None
    image_url: Optional[str] = None
    stock: Optional[int] = None
    rating: Optional[float] = None
    is_featured: Optional[bool] = None
    is_active: Optional[bool] = None

# ================= ORDER SCHEMAS =================
class CartItemInput(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)

class OrderCreate(BaseModel):
    full_name: str
    phone: str
    address: str
    city: str
    district: str
    pincode: str
    payment_method: str = "Cash on Delivery"
    payment_receipt: Optional[str] = None
    payment_utr: Optional[str] = None
    items: List[CartItemInput]

class OrderItemOut(BaseModel):
    id: int
    product_id: Optional[int] = None
    product_name: str
    price: float
    quantity: int
    image: Optional[str] = None

    class Config:
        from_attributes = True

class OrderOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    username: str
    full_name: str
    phone: str
    address: str
    city: str
    district: str
    pincode: str
    payment_method: str
    payment_receipt: Optional[str] = None
    payment_utr: Optional[str] = None
    subtotal: float
    discount_amount: float
    total_amount: float
    status: str
    created_at: Optional[datetime] = None
    items: List[OrderItemOut] = []

    class Config:
        from_attributes = True

class OrderStatusUpdate(BaseModel):
    status: str # Pending, Processing, Shipped, Delivered, Cancelled

class AdminStatsOut(BaseModel):
    all_orders: int
    total_orders: int # Count of non-cancelled orders (for backward compatibility)
    active_orders_count: int # Count of orders in pipeline (Pending, Processing, Shipped)
    pending_orders: int
    processing_orders: int
    shipped_orders: int
    delivered_orders: int
    cancelled_orders: int

    # Financial metrics
    delivered_order_value: float
    active_order_value: float
    cancelled_order_value: float
    total_revenue: float # Backward-compatible alias for delivered_order_value
    collected_revenue: Optional[float] = None
    collected_revenue_status: str = "Not Available"
    collected_revenue_note: str

    total_products: int
    total_users: int

    class Config:
        from_attributes = True

# ================= WISHLIST SCHEMAS =================
class WishlistToggle(BaseModel):
    product_id: int

class WishlistOut(BaseModel):
    id: int
    product: ProductOut

    class Config:
        from_attributes = True
