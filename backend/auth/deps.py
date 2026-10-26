"""
FastAPI authentication and role-based access control dependencies.
"""
from typing import Optional, List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.db.models import UserModel
from backend.auth.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/token",
    auto_error=False
)


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Optional[UserModel]:
    """Retrieve the current user from the Bearer token without raising if absent."""
    if not token:
        return None
    
    payload = decode_access_token(token)
    if not payload:
        return None
    
    email: Optional[str] = payload.get("sub")
    if not email:
        return None
    
    user = db.query(UserModel).filter(UserModel.email == email).first()
    if not user or not user.is_active:
        return None
    
    return user


def require_current_user(
    current_user: Optional[UserModel] = Depends(get_current_user)
) -> UserModel:
    """Dependency that enforces a valid authenticated user."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


def require_roles(allowed_roles: List[str]):
    """Enforce role-based access control (RBAC)."""
    def role_checker(current_user: UserModel = Depends(require_current_user)) -> UserModel:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: requires one of roles {allowed_roles}, your role is '{current_user.role}'.",
            )
        return current_user
    return role_checker
