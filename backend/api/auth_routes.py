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

from fastapi import Depends, HTTPException, status
from backend.db.session import get_db
from backend.auth.schemas import UserRegisterRequest, UserOut, AuthTokenResponse
from backend.auth.security import create_access_token

@auth_router.post(
    "/register",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account"
)
def register(
    req: UserRegisterRequest,
    db: Session = Depends(get_db)
):
    """Create a new user account and return a signed JWT token."""
    existing = db.query(UserModel).filter(UserModel.email == req.email.lower().strip()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )
    
    valid_roles = {"admin", "operator", "student"}
    assigned_role = req.role.lower().strip() if req.role else "operator"
    if assigned_role not in valid_roles:
        assigned_role = "operator"

    user = UserModel(
        email=req.email.lower().strip(),
        full_name=req.full_name.strip(),
        hashed_password=get_password_hash(req.password),
        role=assigned_role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(data={"sub": user.email, "role": user.role, "name": user.full_name})
    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserOut.model_validate(user),
    )
