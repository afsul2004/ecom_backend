import pytest
from app.models import Order, OrderItem, Product, User
from sqlalchemy import func

def test_empty_database_returns_safe_zero_values(client, sample_users):
    """4. Empty databases return safe zero values for applicable metrics."""
    admin_headers = {"Authorization": f"Bearer {sample_users['token_admin']}"}
    
    resp = client.get("/api/admin/stats", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["delivered_order_value"] == 0.0
    assert data["active_order_value"] == 0.0
    assert data["cancelled_order_value"] == 0.0
    assert data["total_revenue"] == 0.0
    assert data["all_orders"] == 0
    assert data["total_orders"] == 0
    assert data["active_orders_count"] == 0
    assert data["pending_orders"] == 0
    assert data["processing_orders"] == 0
    assert data["shipped_orders"] == 0
    assert data["delivered_orders"] == 0
    assert data["cancelled_orders"] == 0
    assert data["collected_revenue"] is None
    assert data["collected_revenue_status"] == "Not Available"

def test_delivered_order_value_includes_only_delivered_orders(client, sample_users, db_session):
    """1. Delivered order value includes only delivered orders."""
    admin_headers = {"Authorization": f"Bearer {sample_users['token_admin']}"}
    alice = sample_users["customer1"]

    # Seed orders with different statuses and totals
    o_delivered_1 = Order(
        user_id=alice.id, username=alice.name, full_name="Alice", phone="9876543210",
        address="123 St", city="City", district="Dist", pincode="400001",
        subtotal=2500.0, discount_amount=1000.0, total_amount=1500.0, status="Delivered"
    )
    o_delivered_2 = Order(
        user_id=alice.id, username=alice.name, full_name="Alice", phone="9876543210",
        address="123 St", city="City", district="Dist", pincode="400001",
        subtotal=3000.0, discount_amount=1000.0, total_amount=2000.0, status="Delivered"
    )
    o_pending = Order(
        user_id=alice.id, username=alice.name, full_name="Alice", phone="9876543210",
        address="123 St", city="City", district="Dist", pincode="400001",
        subtotal=1000.0, discount_amount=0.0, total_amount=1000.0, status="Pending"
    )
    o_shipped = Order(
        user_id=alice.id, username=alice.name, full_name="Alice", phone="9876543210",
        address="123 St", city="City", district="Dist", pincode="400001",
        subtotal=800.0, discount_amount=0.0, total_amount=800.0, status="Shipped"
    )
    o_cancelled = Order(
        user_id=alice.id, username=alice.name, full_name="Alice", phone="9876543210",
        address="123 St", city="City", district="Dist", pincode="400001",
        subtotal=1500.0, discount_amount=0.0, total_amount=1500.0, status="Cancelled"
    )
    db_session.add_all([o_delivered_1, o_delivered_2, o_pending, o_shipped, o_cancelled])
    db_session.commit()

    resp = client.get("/api/admin/stats", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    # Delivered order value: 1500 + 2000 = 3500
    assert data["delivered_order_value"] == 3500.0
    assert data["delivered_orders"] == 2

def test_active_order_value_excludes_delivered_and_cancelled_orders(client, sample_users, db_session):
    """2. Active order value excludes delivered and cancelled orders."""
    admin_headers = {"Authorization": f"Bearer {sample_users['token_admin']}"}
    alice = sample_users["customer1"]

    o_pending = Order(
        user_id=alice.id, username=alice.name, full_name="Alice", phone="9876543210",
        address="123 St", city="City", district="Dist", pincode="400001",
        subtotal=500.0, discount_amount=0.0, total_amount=500.0, status="Pending"
    )
    o_processing = Order(
        user_id=alice.id, username=alice.name, full_name="Alice", phone="9876543210",
        address="123 St", city="City", district="Dist", pincode="400001",
        subtotal=1200.0, discount_amount=0.0, total_amount=1200.0, status="Processing"
    )
    o_shipped = Order(
        user_id=alice.id, username=alice.name, full_name="Alice", phone="9876543210",
        address="123 St", city="City", district="Dist", pincode="400001",
        subtotal=800.0, discount_amount=0.0, total_amount=800.0, status="Shipped"
    )
    o_delivered = Order(
        user_id=alice.id, username=alice.name, full_name="Alice", phone="9876543210",
        address="123 St", city="City", district="Dist", pincode="400001",
        subtotal=2000.0, discount_amount=0.0, total_amount=2000.0, status="Delivered"
    )
    o_cancelled = Order(
        user_id=alice.id, username=alice.name, full_name="Alice", phone="9876543210",
        address="123 St", city="City", district="Dist", pincode="400001",
        subtotal=900.0, discount_amount=0.0, total_amount=900.0, status="Cancelled"
    )
    db_session.add_all([o_pending, o_processing, o_shipped, o_delivered, o_cancelled])
    db_session.commit()

    resp = client.get("/api/admin/stats", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    # Active order value: Pending (500) + Processing (1200) + Shipped (800) = 2500
    # Must NOT include delivered (2000) or cancelled (900)
    assert data["active_order_value"] == 2500.0
    assert data["active_orders_count"] == 3
    assert data["pending_orders"] == 1
    assert data["processing_orders"] == 1
    assert data["shipped_orders"] == 1

def test_cancelled_order_value_includes_only_cancelled_orders(client, sample_users, db_session):
    """3. Cancelled order value includes only cancelled orders."""
    admin_headers = {"Authorization": f"Bearer {sample_users['token_admin']}"}
    alice = sample_users["customer1"]

    o_c1 = Order(
        user_id=alice.id, username=alice.name, full_name="Alice", phone="9876543210",
        address="123 St", city="City", district="Dist", pincode="400001",
        subtotal=1000.0, discount_amount=0.0, total_amount=1000.0, status="Cancelled"
    )
    o_c2 = Order(
        user_id=alice.id, username=alice.name, full_name="Alice", phone="9876543210",
        address="123 St", city="City", district="Dist", pincode="400001",
        subtotal=1500.0, discount_amount=0.0, total_amount=1500.0, status="Cancelled"
    )
    o_delivered = Order(
        user_id=alice.id, username=alice.name, full_name="Alice", phone="9876543210",
        address="123 St", city="City", district="Dist", pincode="400001",
        subtotal=3000.0, discount_amount=0.0, total_amount=3000.0, status="Delivered"
    )
    db_session.add_all([o_c1, o_c2, o_delivered])
    db_session.commit()

    resp = client.get("/api/admin/stats", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    # Cancelled order value: 1000 + 1500 = 2500
    assert data["cancelled_order_value"] == 2500.0
    assert data["cancelled_orders"] == 2

def test_discounts_and_final_order_totals_are_handled_correctly(client, sample_users, sample_catalog, db_session):
    """5. Discounts and final order totals are handled correctly."""
    cust_headers = {"Authorization": f"Bearer {sample_users['token_customer1']}"}
    admin_headers = {"Authorization": f"Bearer {sample_users['token_admin']}"}
    p2 = sample_catalog["p2"] # price = 3000

    # Place order for 1 of p2 -> subtotal 3000 >= 2000 triggers 1000 discount -> total_amount = 2000
    resp = client.post("/api/orders", json={
        "full_name": "Alice Green",
        "phone": "9876543210",
        "address": "123 Elm Street",
        "city": "Mumbai",
        "district": "Mumbai",
        "pincode": "400001",
        "items": [{"product_id": p2.id, "quantity": 1}]
    }, headers=cust_headers)
    assert resp.status_code == 200
    order_data = resp.json()
    assert order_data["subtotal"] == 3000.0
    assert order_data["discount_amount"] == 1000.0
    assert order_data["total_amount"] == 2000.0

    # Deliver order
    client.put(f"/api/admin/orders/{order_data['id']}/status", json={"status": "Delivered"}, headers=admin_headers)

    # Verify admin stats uses final payable total (2000.0), NOT original undiscounted price (3000.0)
    stats = client.get("/api/admin/stats", headers=admin_headers).json()
    assert stats["delivered_order_value"] == 2000.0

def test_joins_do_not_duplicate_order_totals(client, sample_users, sample_catalog, db_session):
    """6. Joins do not duplicate order totals when an order contains multiple order items."""
    admin_headers = {"Authorization": f"Bearer {sample_users['token_admin']}"}
    alice = sample_users["customer1"]
    p1 = sample_catalog["p1"]
    p2 = sample_catalog["p2"]
    p3 = sample_catalog["p3"]

    # Create 1 Delivered order with total_amount = 5000 and 3 items
    order = Order(
        user_id=alice.id, username=alice.name, full_name="Alice", phone="9876543210",
        address="123 St", city="City", district="Dist", pincode="400001",
        subtotal=5000.0, discount_amount=0.0, total_amount=5000.0, status="Delivered"
    )
    db_session.add(order)
    db_session.flush()

    item1 = OrderItem(order_id=order.id, product_id=p1.id, product_name="P1", price=1500.0, quantity=1)
    item2 = OrderItem(order_id=order.id, product_id=p2.id, product_name="P2", price=3000.0, quantity=1)
    item3 = OrderItem(order_id=order.id, product_id=p3.id, product_name="P3", price=500.0, quantity=1)
    db_session.add_all([item1, item2, item3])
    db_session.commit()

    stats = client.get("/api/admin/stats", headers=admin_headers).json()
    # If a buggy join on order_items had been used, total would have been multiplied by 3 (15000)!
    # Must strictly equal 5000.0
    assert stats["delivered_order_value"] == 5000.0

def test_unverified_payments_are_not_counted_as_collected_revenue(client, sample_users, db_session):
    """7. Unverified payments (receipt image, UTR string, COD) are not counted as collected revenue."""
    admin_headers = {"Authorization": f"Bearer {sample_users['token_admin']}"}
    alice = sample_users["customer1"]

    # Order with uploaded receipt & UTR text
    o_upi = Order(
        user_id=alice.id, username=alice.name, full_name="Alice", phone="9876543210",
        address="123 St", city="City", district="Dist", pincode="400001",
        payment_method="UPI / QR Code",
        payment_receipt="/uploads/receipt_xyz.jpg",
        payment_utr="UPI123456789012",
        subtotal=2000.0, discount_amount=0.0, total_amount=2000.0, status="Delivered"
    )
    # Order with COD
    o_cod = Order(
        user_id=alice.id, username=alice.name, full_name="Alice", phone="9876543210",
        address="123 St", city="City", district="Dist", pincode="400001",
        payment_method="Cash on Delivery",
        subtotal=1000.0, discount_amount=0.0, total_amount=1000.0, status="Delivered"
    )
    db_session.add_all([o_upi, o_cod])
    db_session.commit()

    stats = client.get("/api/admin/stats", headers=admin_headers).json()
    assert stats["collected_revenue"] is None
    assert stats["collected_revenue_status"] == "Not Available"
    assert "unverified" in stats["collected_revenue_note"].lower()

def test_existing_dashboard_response_fields_remain_compatible(client, sample_users):
    """8. Existing dashboard response fields remain compatible with the frontend."""
    admin_headers = {"Authorization": f"Bearer {sample_users['token_admin']}"}
    
    resp = client.get("/api/admin/stats", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()

    # Legacy fields expected by React frontend
    assert "total_revenue" in data
    assert "total_orders" in data
    assert "all_orders" in data
    assert "pending_orders" in data
    assert "cancelled_orders" in data
    assert "delivered_orders" in data
    assert "total_products" in data
    assert "total_users" in data

    # New accurate metrics
    assert "delivered_order_value" in data
    assert "active_order_value" in data
    assert "cancelled_order_value" in data
    assert "collected_revenue" in data
    assert "collected_revenue_status" in data
    assert "collected_revenue_note" in data
