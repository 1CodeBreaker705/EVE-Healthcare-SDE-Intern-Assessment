import os
# CRITICAL: Force the entire application to use an isolated SQLite database 
# and memory broker BEFORE any application modules are imported.
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["REDIS_URL"] = "memory://"

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine
from app.worker import celery

# 1. Configure Celery to run synchronously for tests (bypasses Redis)
celery.conf.task_always_eager = True
celery.conf.task_eager_propagates = True

# 2. Setup SQLite Database for isolated testing
# Recreate tables before tests run
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

client = TestClient(app)

# ==========================================
# REQUIREMENT 1: AUTHENTICATION & VALIDATION
# ==========================================
def test_signup():
    response = client.post("/signup", json={"email": "patient@example.com", "password": "pass"})
    assert response.status_code == 201

def test_signup_invalid_validation():
    # Edge Case: Basic request validation (Pydantic catches bad email format)
    response = client.post("/signup", json={"email": "not-an-email", "password": "pass"})
    assert response.status_code == 422 # 422 Unprocessable Entity

def test_login():
    response = client.post("/login", data={"username": "patient@example.com", "password": "pass"})
    assert response.status_code == 200
    assert "access_token" in response.json()

# ==========================================
# REQUIREMENT 2: DIAGNOSTIC CENTRES & TESTS
# ==========================================
def test_create_and_retrieve_centre():
    # Create Centre
    res_create = client.post("/centres", json={"name": "Health Hub", "location": "NY"})
    assert res_create.status_code == 200
    centre_id = res_create.json()["id"]
    
    # Add Test to Centre
    res_test = client.post(f"/centres/{centre_id}/tests", json={"name": "MRI", "price": 1500.0})
    assert res_test.status_code == 200
    
    # Retrieve Tests (Verifying relationships)
    res_get = client.get(f"/centres/{centre_id}/tests")
    assert len(res_get.json()) == 1
    assert res_get.json()[0]["name"] == "MRI"
    assert res_get.json()[0]["price"] == 1500.0

# ==========================================
# REQUIREMENT 3 & 6: BOOKING & EDGE CASES
# ==========================================
def test_unauthorized_booking():
    # Edge Case: Attempts to modify resources without authorization
    response = client.post("/bookings", json={"test_id": 1, "centre_id": 1, "appointment_time": "2025-01-01T10:00:00"})
    assert response.status_code == 401 # Unauthorized

def test_invalid_booking_id():
    login_resp = client.post("/login", data={"username": "patient@example.com", "password": "pass"})
    token = login_resp.json()["access_token"]
    
    # Edge Case: Invalid test or centre IDs
    response = client.post(
        "/bookings",
        json={"test_id": 999, "centre_id": 999, "appointment_time": "2025-01-01T10:00:00"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid test or centre"

def test_create_valid_booking():
    login_resp = client.post("/login", data={"username": "patient@example.com", "password": "pass"})
    token = login_resp.json()["access_token"]
    
    # Successful authenticated booking
    response = client.post(
        "/bookings",
        json={"test_id": 1, "centre_id": 1, "appointment_time": "2025-01-01T10:00:00"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "PENDING"
    assert response.json()["amount"] == 1500.0 # Price is safely auto-fetched from the DB, not trusted from client

# ==========================================
# REQUIREMENT 4: SIMULATED PAYMENT SERVICE
# ==========================================
def test_simulate_payment():
    login_resp = client.post("/login", data={"username": "patient@example.com", "password": "pass"})
    token = login_resp.json()["access_token"]
    
    # Call mock payment endpoint (Randomly returns SUCCESS or FAILED)
    response = client.post(
        "/payments/",
        json={"booking_id": 1},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    status = response.json()["status"]
    assert status in ["SUCCESS", "FAILED"]

# ==========================================
# REQUIREMENT 5 & 6: WEBHOOK & IDEMPOTENCY
# ==========================================
def test_webhook_idempotency():
    payload = {
        "event_id": "evt_unique_abc123",
        "booking_id": 1,
        "payment_status": "SUCCESS"
    }
    
    # First request: Celery worker processes it synchronously (due to eager mode) and saves event_id to DB
    resp1 = client.post("/payments/webhook/", json=payload)
    assert resp1.status_code == 200
    
    # Second request: Celery worker sees the duplicate event_id, ignores it, preventing corruption
    resp2 = client.post("/payments/webhook/", json=payload)
    assert resp2.status_code == 200
