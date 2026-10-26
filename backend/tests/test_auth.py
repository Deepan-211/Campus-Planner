"""
Unit tests for Authentication and RBAC endpoints.
"""
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
