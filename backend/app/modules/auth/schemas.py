from pydantic import BaseModel, EmailStr

# Registro
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    # role_name: str (Opcional si queremos asignar rol al crear)

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    class Config:
        from_attributes = True

# Login
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user_email: str