from pydantic import BaseModel, EmailStr
from typing import Optional

# Registro
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    # role_name: str (Opcional si queremos asignar rol al crear)

class RoleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    class Config:
        from_attributes = True

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    roles: list[RoleResponse] = []
    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    is_active: Optional[bool] = None
    role_name: Optional[str] = None

class PasswordChange(BaseModel):
    password: str

# Login
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user_email: str
    roles: list[str] = []