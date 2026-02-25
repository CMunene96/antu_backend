from __future__ import annotations
from typing import Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr
    phone: str
    full_name: str
    role: str
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    updated_at: Optional[datetime] = None

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    
    model_config = {"from_attributes": True}

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: Optional[int] = None
    role: Optional[str] = None


