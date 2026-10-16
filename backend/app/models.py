from sqlalchemy import (
    Column, Integer, String, Text, Numeric, ForeignKey, TIMESTAMP, Boolean, func
)
from sqlalchemy.orm import relationship
from app.database import Base

class User(Base):
    __tablename__ = "login1"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(String(20), default="customer", nullable=False) # 'customer' or 'admin'
    phone = Column(String(20), nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    orders = relationship("Order", back_populates="user", cascade="all, delete-orphan")
    wishlist_items = relationship("Wishlist", back_populates="user", cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    slug = Column(String(100), unique=True, index=True, nullable=False)
    icon = Column(String(50), default="ShoppingBag")
    description = Column(String(255), nullable=True)


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), index=True, nullable=False)
    brand = Column(String(100), index=True, nullable=False)
    category_slug = Column(String(100), index=True, nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Numeric(10, 2), nullable=False)
    original_price = Column(Numeric(10, 2), nullable=False)
    discount_percent = Column(Integer, default=0)
    image_url = Column(String(500), nullable=False)
    stock = Column(Integer, default=50, nullable=False)
    rating = Column(Numeric(3, 1), default=4.5)
    is_featured = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("login1.id", ondelete="SET NULL"), nullable=True)
    username = Column(String(100), nullable=False)
    full_name = Column(String(150), nullable=False)
    phone = Column(String(15), nullable=False)
    address = Column(Text, nullable=False)
    city = Column(String(100), nullable=False)
    district = Column(String(100), nullable=False)
    pincode = Column(String(10), nullable=False)
    payment_method = Column(String(50), default="Cash on Delivery", nullable=False)
    payment_receipt = Column(String(500), nullable=True) # Screenshot URL of payment receipt
    payment_utr = Column(String(100), nullable=True) # UPI Transaction ID / UTR reference
    subtotal = Column(Numeric(10, 2), nullable=False)
    discount_amount = Column(Numeric(10, 2), default=0.00, nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String(50), default="Pending", nullable=False) # Pending, Processing, Shipped, Delivered, Cancelled
    created_at = Column(TIMESTAMP, server_default=func.now())

    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    product_name = Column(String(255), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    quantity = Column(Integer, nullable=False)
    image = Column(String(500), nullable=True)

    order = relationship("Order", back_populates="items")
    product = relationship("Product")


class Wishlist(Base):
    __tablename__ = "wishlist"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("login1.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    user = relationship("User", back_populates="wishlist_items")
    product = relationship("Product")
