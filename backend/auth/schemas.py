"""
Pydantic schemas for authentication and user accounts.
"""
from typing import Optional
from pydantic import BaseModel, EmailStr, Field

class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password with minimum 6 characters")
    full_name: str = Field(..., min_length=2, max_length=128)
    role: Optional[str] = Field(default="operator", description="Role: admin, operator, or student")

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str
