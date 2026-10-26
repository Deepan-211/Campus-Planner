"""
FastAPI routing endpoints for authentication, registration, and user profiles.
"""
from fastapi import APIRouter
from sqlalchemy.orm import Session
from backend.db.models import UserModel
from backend.auth.security import get_password_hash

auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"])

def seed_default_users(db: Session):
    """Seed initial demo accounts if database has no users."""
    user_count = db.query(UserModel).count()
    if user_count == 0:
        demo_users = [
            UserModel(
                email="admin@campusride.edu",
                full_name="Admin Deepan",
                hashed_password=get_password_hash("Admin@123"),
                role="admin",
                is_active=True,
            ),
            UserModel(
                email="operator@campusride.edu",
                full_name="Fleet Dispatcher",
                hashed_password=get_password_hash("Operator@123"),
                role="operator",
                is_active=True,
            ),
            UserModel(
                email="student@campusride.edu",
                full_name="Student Rider",
                hashed_password=get_password_hash("Student@123"),
                role="student",
                is_active=True,
            ),
        ]
        db.add_all(demo_users)
        db.commit()
