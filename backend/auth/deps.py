"""
FastAPI authentication and role-based access control dependencies.
"""
from typing import Optional
from fastapi import Depends
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
