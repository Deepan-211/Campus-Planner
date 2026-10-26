"""
Unit tests for Authentication and RBAC endpoints.
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)


def test_login_demo_admin():
    """Verify built-in seeded admin account can log in and retrieve a JWT."""
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@campusride.edu", "password": "Admin@123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "admin@campusride.edu"
    assert data["user"]["role"] == "admin"


def test_login_invalid_credentials():
    """Verify rejected login with wrong password."""
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@campusride.edu", "password": "WrongPassword999!"}
    )
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]


def test_register_new_user():
    """Verify user registration flow returns a valid JWT and creates user profile."""
    unique_email = f"rider_{uuid.uuid4().hex[:8]}@campus.edu"
    response = client.post(
        "/api/auth/register",
        json={
            "email": unique_email,
            "password": "SecurePassword123!",
            "full_name": "Test Runner",
            "role": "student"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == unique_email
    assert data["user"]["role"] == "student"

    # Verify logging in with newly registered credentials
    login_resp = client.post(
        "/api/auth/login",
        json={"email": unique_email, "password": "SecurePassword123!"}
    )
    assert login_resp.status_code == 200


def test_register_duplicate_email():
    """Verify duplicate registration fails with 400 Bad Request."""
    response = client.post(
        "/api/auth/register",
        json={
            "email": "admin@campusride.edu",
            "password": "AnotherPassword123",
            "full_name": "Duplicate Admin",
            "role": "admin"
        }
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_get_me_endpoint():
    """Verify /api/auth/me returns current user when Bearer token is provided."""
    # Login as operator
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "operator@campusride.edu", "password": "Operator@123"}
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    # Call /api/auth/me with Bearer token
    me_resp = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["email"] == "operator@campusride.edu"
    assert me_data["role"] == "operator"

    # Call /api/auth/me without token -> 401
    unauth_resp = client.get("/api/auth/me")
    assert unauth_resp.status_code == 401
