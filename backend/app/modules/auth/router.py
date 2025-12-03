from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_password_hash, verify_password, create_access_token
from app.modules.auth import models, schemas

router = APIRouter()

@router.post("/login", response_model=schemas.TokenResponse)
def login(credentials: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Credenciales incorrectas")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Usuario inactivo")
    
    access_token = create_access_token(data={"sub": user.email})
    role_names = [role.name for role in user.roles]
    return {
        "access_token": access_token, 
        "token_type": "bearer", 
        "user_email": user.email,
        "roles": role_names
    }

@router.post("/register", response_model=schemas.UserResponse)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="El email ya existe")
    
    hashed_password = get_password_hash(user.password)
    new_user = models.User(email=user.email, password_hash=hashed_password, is_active=True)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user