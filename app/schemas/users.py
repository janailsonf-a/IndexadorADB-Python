from typing import Optional, Literal

from pydantic import BaseModel, EmailStr, Field


RoleType = Literal["user", "admin"]


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: RoleType
    is_active: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class UpdateMeRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    current_password: Optional[str] = Field(default=None, min_length=6, max_length=255)
    new_password: Optional[str] = Field(default=None, min_length=6, max_length=255)


class CreateUserRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=255)
    role: RoleType = "user"


class UpdateUserRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(default=None, min_length=6, max_length=255)
    role: Optional[RoleType] = None
    is_active: Optional[bool] = None