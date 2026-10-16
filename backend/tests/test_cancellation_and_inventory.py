import pytest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from app.models import Order, OrderItem, Product
from app.services import order_service

def check_stock(db_session, product_id: int) -> int:
    """Expires session cache and fetches the fresh stock value from the database."""
    db_session.expire_all()
    p = db_session.query(Product).filter(Product.id == product_id).first()
    return p.stock if p else None

def test_eligible_order_cancellation_restores_stock_correctly(client, sample_users, sample_catalog, db_session):
    """1. Eligible order cancellation restores stock correctly."""
    headers = {"Authorization": f"Bearer {sample_users['token_customer1']}"}
    p1 = sample_catalog["p1"]
    initial_stock = p1.stock # 20

    # Place order for 3 items
    order_payload = {
        "full_name": "Alice Green",
        "phone": "9876543210",
        "address": "123 Elm Street",
        "city": "Mumbai",
        "district": "Mumbai",
        "pincode": "400001",
        "items": [{"product_id": p1.id, "quantity": 3}]
    }
    resp = client.post("/api/orders", json=order_payload, headers=headers)
    assert resp.status_code == 200, resp.text
    order_data = resp.json()
    order_id = order_data["id"]

    # Verify stock decremented at checkout
    assert check_stock(db_session, p1.id) == initial_stock - 3 # 17

    # Cancel order
    cancel_resp = client.put(f"/api/orders/{order_id}/cancel", headers=headers)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "Cancelled"

    # Verify stock restored back to 20
    assert check_stock(db_session, p1.id) == initial_stock

def test_second_cancellation_request_does_not_restore_stock_again(client, sample_users, sample_catalog, db_session):
    """2. A second cancellation request does not restore stock again."""
    headers = {"Authorization": f"Bearer {sample_users['token_customer1']}"}
    p1 = sample_catalog["p1"]
    initial_stock = p1.stock

    # Place and cancel order
    resp = client.post("/api/orders", json={
        "full_name": "Alice Green",
        "phone": "9876543210",
        "address": "123 Elm Street",
        "city": "Mumbai",
        "district": "Mumbai",
        "pincode": "400001",
        "items": [{"product_id": p1.id, "quantity": 2}]
    }, headers=headers)
    order_id = resp.json()["id"]

    # First cancel -> 200
    c1 = client.put(f"/api/orders/{order_id}/cancel", headers=headers)
    assert c1.status_code == 200
    assert c1.json()["status"] == "Cancelled"

    assert check_stock(db_session, p1.id) == initial_stock

    # Second cancel -> 400 Bad Request
    c2 = client.put(f"/api/orders/{order_id}/cancel", headers=headers)
    assert c2.status_code == 400
    assert "already cancelled" in c2.json()["detail"].lower()

    # Stock must remain exactly at initial_stock, NOT incremented twice
    assert check_stock(db_session, p1.id) == initial_stock

def test_customer_cannot_cancel_another_customers_order(client, sample_users, sample_catalog):
    """3. A customer cannot cancel another customer's order."""
    alice_headers = {"Authorization": f"Bearer {sample_users['token_customer1']}"}
    bob_headers = {"Authorization": f"Bearer {sample_users['token_customer2']}"}
    p1 = sample_catalog["p1"]

    # Alice places an order
    resp = client.post("/api/orders", json={
        "full_name": "Alice Green",
        "phone": "9876543210",
        "address": "123 Elm Street",
        "city": "Mumbai",
        "district": "Mumbai",
        "pincode": "400001",
        "items": [{"product_id": p1.id, "quantity": 1}]
    }, headers=alice_headers)
    order_id = resp.json()["id"]

    # Bob attempts to cancel Alice's order -> 403 Forbidden
    bob_resp = client.put(f"/api/orders/{order_id}/cancel", headers=bob_headers)
    assert bob_resp.status_code == 403
    assert "only cancel your own orders" in bob_resp.json()["detail"]

def test_shipped_and_delivered_orders_cannot_be_cancelled_by_customers(client, sample_users, sample_catalog, db_session):
    """4. Shipped and delivered orders cannot be cancelled by customers."""
    headers = {"Authorization": f"Bearer {sample_users['token_customer1']}"}
    p1 = sample_catalog["p1"]

    # Place order 1 and set to Shipped
    r1 = client.post("/api/orders", json={
        "full_name": "Alice Green",
        "phone": "9876543210",
        "address": "123 Elm Street",
        "city": "Mumbai",
        "district": "Mumbai",
        "pincode": "400001",
        "items": [{"product_id": p1.id, "quantity": 1}]
    }, headers=headers)
    order1_id = r1.json()["id"]
    order1 = db_session.query(Order).filter(Order.id == order1_id).first()
    order1.status = "Shipped"
    db_session.commit()

    # Customer attempts to cancel shipped order -> 400
    cancel_shipped = client.put(f"/api/orders/{order1_id}/cancel", headers=headers)
    assert cancel_shipped.status_code == 400
    assert "cannot cancel order" in cancel_shipped.json()["detail"].lower()

    # Place order 2 and set to Delivered
    r2 = client.post("/api/orders", json={
        "full_name": "Alice Green",
        "phone": "9876543210",
        "address": "123 Elm Street",
        "city": "Mumbai",
        "district": "Mumbai",
        "pincode": "400001",
        "items": [{"product_id": p1.id, "quantity": 1}]
    }, headers=headers)
    order2_id = r2.json()["id"]
    order2 = db_session.query(Order).filter(Order.id == order2_id).first()
    order2.status = "Delivered"
    db_session.commit()

    # Customer attempts to cancel delivered order -> 400
    cancel_delivered = client.put(f"/api/orders/{order2_id}/cancel", headers=headers)
    assert cancel_delivered.status_code == 400
    assert "cannot cancel order" in cancel_delivered.json()["detail"].lower()

def test_cancelling_multi_product_order_restores_all_quantities_correctly(client, sample_users, sample_catalog, db_session):
    """5. Cancelling a multi-product order restores all item quantities correctly."""
    headers = {"Authorization": f"Bearer {sample_users['token_customer1']}"}
    p1 = sample_catalog["p1"] # stock 20
    p2 = sample_catalog["p2"] # stock 10
    p3 = sample_catalog["p3"] # stock 5

    # Order: 2 of p1, 3 of p2, 1 of p3
    resp = client.post("/api/orders", json={
        "full_name": "Alice Green",
        "phone": "9876543210",
        "address": "123 Elm Street",
        "city": "Mumbai",
        "district": "Mumbai",
        "pincode": "400001",
        "items": [
            {"product_id": p1.id, "quantity": 2},
            {"product_id": p2.id, "quantity": 3},
            {"product_id": p3.id, "quantity": 1}
        ]
    }, headers=headers)
    assert resp.status_code == 200
    order_id = resp.json()["id"]

    # Verify decrements
    assert check_stock(db_session, p1.id) == 18
    assert check_stock(db_session, p2.id) == 7
    assert check_stock(db_session, p3.id) == 4

    # Cancel multi-product order
    cancel_resp = client.put(f"/api/orders/{order_id}/cancel", headers=headers)
    assert cancel_resp.status_code == 200

    # Verify all restored
    assert check_stock(db_session, p1.id) == 20
    assert check_stock(db_session, p2.id) == 10
    assert check_stock(db_session, p3.id) == 5

def test_failed_database_operations_rollback_both_stock_and_order_status(client, sample_users, sample_catalog, db_session):
    """6. Failed database operations roll back both stock and order status."""
    headers = {"Authorization": f"Bearer {sample_users['token_customer1']}"}
    p1 = sample_catalog["p1"]

    resp = client.post("/api/orders", json={
        "full_name": "Alice Green",
        "phone": "9876543210",
        "address": "123 Elm Street",
        "city": "Mumbai",
        "district": "Mumbai",
        "pincode": "400001",
        "items": [{"product_id": p1.id, "quantity": 2}]
    }, headers=headers)
    order_id = resp.json()["id"]

    stock_after_order = check_stock(db_session, p1.id) # 18

    # Simulate unexpected failure during commit in cancel_customer_order
    with patch("sqlalchemy.orm.Session.commit", side_effect=Exception("Database lock acquisition timeout")):
        cancel_resp = client.put(f"/api/orders/{order_id}/cancel", headers=headers)
        assert cancel_resp.status_code == 500

    # Verify rollback: status must still be Pending and stock unchanged
    db_session.expire_all()
    db_order = db_session.query(Order).filter(Order.id == order_id).first()
    assert db_order.status == "Pending"
    assert check_stock(db_session, p1.id) == stock_after_order

def test_concurrent_cancellation_requests_cannot_restore_stock_twice(client, sample_users, sample_catalog, db_session):
    """7. Concurrent cancellation requests cannot restore stock twice."""
    headers = {"Authorization": f"Bearer {sample_users['token_customer1']}"}
    p1 = sample_catalog["p1"]
    initial_stock = p1.stock # 20

    resp = client.post("/api/orders", json={
        "full_name": "Alice Green",
        "phone": "9876543210",
        "address": "123 Elm Street",
        "city": "Mumbai",
        "district": "Mumbai",
        "pincode": "400001",
        "items": [{"product_id": p1.id, "quantity": 4}]
    }, headers=headers)
    order_id = resp.json()["id"]

    assert check_stock(db_session, p1.id) == 16

    # Run two cancellation requests
    r1 = client.put(f"/api/orders/{order_id}/cancel", headers=headers)
    r2 = client.put(f"/api/orders/{order_id}/cancel", headers=headers)

    statuses = [r1.status_code, r2.status_code]
    # Exactly one request must succeed (200), and the other must be rejected (400)
    assert 200 in statuses
    assert 400 in statuses

    # Final stock must be exactly restored ONCE to 20, never 24!
    assert check_stock(db_session, p1.id) == initial_stock

def test_admin_cancellation_restores_stock_exactly_once(client, sample_users, sample_catalog, db_session):
    """8. An admin cancellation restores stock exactly once."""
    cust_headers = {"Authorization": f"Bearer {sample_users['token_customer1']}"}
    admin_headers = {"Authorization": f"Bearer {sample_users['token_admin']}"}
    p1 = sample_catalog["p1"]
    initial_stock = p1.stock

    resp = client.post("/api/orders", json={
        "full_name": "Alice Green",
        "phone": "9876543210",
        "address": "123 Elm Street",
        "city": "Mumbai",
        "district": "Mumbai",
        "pincode": "400001",
        "items": [{"product_id": p1.id, "quantity": 5}]
    }, headers=cust_headers)
    order_id = resp.json()["id"]

    assert check_stock(db_session, p1.id) == initial_stock - 5

    # Admin changes status to Cancelled
    admin_resp = client.put(f"/api/admin/orders/{order_id}/status", json={"status": "Cancelled"}, headers=admin_headers)
    assert admin_resp.status_code == 200
    assert admin_resp.json()["status"] == "Cancelled"

    # Stock restored back to initial_stock
    assert check_stock(db_session, p1.id) == initial_stock

    # Second admin status update to Cancelled should be idempotent and NOT restore stock again
    admin_resp2 = client.put(f"/api/admin/orders/{order_id}/status", json={"status": "Cancelled"}, headers=admin_headers)
    assert admin_resp2.status_code == 200
    assert check_stock(db_session, p1.id) == initial_stock

def test_invalid_status_transitions_are_rejected(client, sample_users, sample_catalog, db_session):
    """9. Invalid status transitions are rejected."""
    admin_headers = {"Authorization": f"Bearer {sample_users['token_admin']}"}
    cust_headers = {"Authorization": f"Bearer {sample_users['token_customer1']}"}
    p1 = sample_catalog["p1"]

    resp = client.post("/api/orders", json={
        "full_name": "Alice Green",
        "phone": "9876543210",
        "address": "123 Elm Street",
        "city": "Mumbai",
        "district": "Mumbai",
        "pincode": "400001",
        "items": [{"product_id": p1.id, "quantity": 1}]
    }, headers=cust_headers)
    order_id = resp.json()["id"]

    # Reject nonexistent status
    r_invalid = client.put(f"/api/admin/orders/{order_id}/status", json={"status": "FlyingToMoon"}, headers=admin_headers)
    assert r_invalid.status_code == 400
    assert "invalid order status" in r_invalid.json()["detail"].lower()

    # Transition order to Delivered
    r_delivered = client.put(f"/api/admin/orders/{order_id}/status", json={"status": "Delivered"}, headers=admin_headers)
    assert r_delivered.status_code == 200

    # Attempt to change delivered order to Cancelled -> 400
    r_cancel_deliv = client.put(f"/api/admin/orders/{order_id}/status", json={"status": "Cancelled"}, headers=admin_headers)
    assert r_cancel_deliv.status_code == 400
    assert "already been delivered" in r_cancel_deliv.json()["detail"].lower()

def test_reactivation_deducts_stock_correctly_and_rejects_insufficient_inventory(client, sample_users, sample_catalog, db_session):
    """10. Reactivation, if supported, deducts stock correctly and rejects insufficient inventory."""
    cust_headers = {"Authorization": f"Bearer {sample_users['token_customer1']}"}
    admin_headers = {"Authorization": f"Bearer {sample_users['token_admin']}"}
    p3 = sample_catalog["p3"] # stock = 5

    # Order all 5 items of p3
    resp = client.post("/api/orders", json={
        "full_name": "Alice Green",
        "phone": "9876543210",
        "address": "123 Elm Street",
        "city": "Mumbai",
        "district": "Mumbai",
        "pincode": "400001",
        "items": [{"product_id": p3.id, "quantity": 5}]
    }, headers=cust_headers)
    order_id = resp.json()["id"]

    # Stock is now 0
    assert check_stock(db_session, p3.id) == 0

    # Cancel order -> stock restored to 5
    client.put(f"/api/orders/{order_id}/cancel", headers=cust_headers)
    assert check_stock(db_session, p3.id) == 5

    # Scenario A: Reduce available stock to 2 (insufficient for 5)
    db_session.expire_all()
    db_p3 = db_session.query(Product).filter(Product.id == p3.id).first()
    db_p3.stock = 2
    db_session.commit()

    # Attempt reactivation to 'Processing' -> must be rejected with 400
    reactivate_fail = client.put(f"/api/admin/orders/{order_id}/status", json={"status": "Processing"}, headers=admin_headers)
    assert reactivate_fail.status_code == 400
    assert "insufficient stock" in reactivate_fail.json()["detail"].lower()

    # Inventory must remain at 2, not deducted into negatives or concealed by max(0, ...)
    assert check_stock(db_session, p3.id) == 2
    db_session.expire_all()
    db_order = db_session.query(Order).filter(Order.id == order_id).first()
    assert db_order.status == "Cancelled"

    # Scenario B: Increase stock to 10 (sufficient for 5)
    db_session.expire_all()
    db_p3 = db_session.query(Product).filter(Product.id == p3.id).first()
    db_p3.stock = 10
    db_session.commit()

    # Attempt reactivation to 'Processing' -> succeeds
    reactivate_ok = client.put(f"/api/admin/orders/{order_id}/status", json={"status": "Processing"}, headers=admin_headers)
    assert reactivate_ok.status_code == 200
    assert reactivate_ok.json()["status"] == "Processing"

    # Stock deducted cleanly: 10 - 5 = 5
    assert check_stock(db_session, p3.id) == 5

def test_stock_never_becomes_negative(client, sample_users, sample_catalog, db_session):
    """11. Stock never becomes negative during checkout or status operations."""
    cust_headers = {"Authorization": f"Bearer {sample_users['token_customer1']}"}
    p3 = sample_catalog["p3"] # stock 5

    # Attempt to order more than available
    resp = client.post("/api/orders", json={
        "full_name": "Alice Green",
        "phone": "9876543210",
        "address": "123 Elm Street",
        "city": "Mumbai",
        "district": "Mumbai",
        "pincode": "400001",
        "items": [{"product_id": p3.id, "quantity": 6}]
    }, headers=cust_headers)
    assert resp.status_code == 400
    assert "insufficient stock" in resp.json()["detail"].lower()

    # Stock unchanged at 5
    assert check_stock(db_session, p3.id) == 5

def test_deleted_or_missing_product_in_order_fails_safely_without_partial_restore(client, sample_users, sample_catalog, db_session):
    """Safely reject cancellation if a product in the order was deleted, without partial restoration."""
    cust_headers = {"Authorization": f"Bearer {sample_users['token_customer1']}"}
    p1 = sample_catalog["p1"] # stock 20
    p2 = sample_catalog["p2"] # stock 10

    resp = client.post("/api/orders", json={
        "full_name": "Alice Green",
        "phone": "9876543210",
        "address": "123 Elm Street",
        "city": "Mumbai",
        "district": "Mumbai",
        "pincode": "400001",
        "items": [
            {"product_id": p1.id, "quantity": 2},
            {"product_id": p2.id, "quantity": 2}
        ]
    }, headers=cust_headers)
    order_id = resp.json()["id"]

    # Stock decremented to 18 and 8
    assert check_stock(db_session, p1.id) == 18
    assert check_stock(db_session, p2.id) == 8

    # Simulate product p2 being deleted from database (e.g. product_id set to null or row removed)
    db_session.expire_all()
    order_item_p2 = db_session.query(OrderItem).filter(OrderItem.order_id == order_id, OrderItem.product_id == p2.id).first()
    order_item_p2.product_id = None
    db_session.commit()

    # Cancellation must fail safely without silently partially restoring p1!
    cancel_resp = client.put(f"/api/orders/{order_id}/cancel", headers=cust_headers)
    assert cancel_resp.status_code == 400

    # Verify p1 was NOT restored partially (transaction rolled back)
    assert check_stock(db_session, p1.id) == 18
    db_session.expire_all()
    order = db_session.query(Order).filter(Order.id == order_id).first()
    assert order.status == "Pending"
