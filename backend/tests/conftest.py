import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
import os
import sys

# Ensure backend root is on sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.database import Base, get_db
from app.main import app
from app.models import User, Product, Category, Order, OrderItem
from app.security import hash_password, create_access_token

# Isolated SQLite in-memory database with StaticPool for fast, non-destructive testing
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(autouse=True)
def clean_db():
    """Wipe and re-initialize tables before each test to guarantee complete isolation."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield

@pytest.fixture
def db_session():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def client():
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def sample_users(db_session):
    """Creates customer1, customer2, and admin users."""
    u1 = User(
        name="Customer Alice",
        email="alice@example.com",
        password=hash_password("password123"),
        role="customer",
        phone="9876543210"
    )
    u2 = User(
        name="Customer Bob",
        email="bob@example.com",
        password=hash_password("password123"),
        role="customer",
        phone="9876543211"
    )
    admin = User(
        name="Admin User",
        email="admin@example.com",
        password=hash_password("adminpass123"),
        role="admin",
        phone="9876543299"
    )
    db_session.add_all([u1, u2, admin])
    db_session.commit()
    db_session.refresh(u1)
    db_session.refresh(u2)
    db_session.refresh(admin)

    return {
        "customer1": u1,
        "customer2": u2,
        "admin": admin,
        "token_customer1": create_access_token({"sub": str(u1.id), "role": u1.role}),
        "token_customer2": create_access_token({"sub": str(u2.id), "role": u2.role}),
        "token_admin": create_access_token({"sub": str(admin.id), "role": admin.role}),
    }

@pytest.fixture
def sample_catalog(db_session):
    """Creates sample category and products."""
    cat = Category(
        name="Electronics",
        slug="electronics",
        icon="Smartphone",
        description="Electronic gadgets"
    )
    db_session.add(cat)
    db_session.flush()

    p1 = Product(
        name="Wireless Earbuds",
        brand="SoundWave",
        category_slug="electronics",
        description="Premium ANC earbuds",
        price=1500.00,
        original_price=2000.00,
        discount_percent=25,
        image_url="https://example.com/earbuds.jpg",
        stock=20,
        rating=4.5,
        is_active=True
    )
    p2 = Product(
        name="Smart Watch",
        brand="TechWear",
        category_slug="electronics",
        description="Fitness tracker smartwatch",
        price=3000.00,
        original_price=4000.00,
        discount_percent=25,
        image_url="https://example.com/watch.jpg",
        stock=10,
        rating=4.7,
        is_active=True
    )
    p3 = Product(
        name="Phone Case",
        brand="ArmorShield",
        category_slug="electronics",
        description="Protective silicone case",
        price=500.00,
        original_price=600.00,
        discount_percent=15,
        image_url="https://example.com/case.jpg",
        stock=5,
        rating=4.2,
        is_active=True
    )
    db_session.add_all([p1, p2, p3])
    db_session.commit()
    db_session.refresh(p1)
    db_session.refresh(p2)
    db_session.refresh(p3)

    return {"category": cat, "p1": p1, "p2": p2, "p3": p3}
