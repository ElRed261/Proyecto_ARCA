from sqlalchemy.orm import Session, joinedload
from app.modules.auth import models, schemas
from app.core.security import get_password_hash, verify_password, create_access_token
from fastapi import HTTPException, status

def authenticate_user(db: Session, credentials: schemas.LoginRequest):
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

def register_user(db: Session, user: schemas.UserCreate):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="El email ya existe")
    
    hashed_password = get_password_hash(user.password)
    new_user = models.User(email=user.email, password_hash=hashed_password, is_active=True)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).options(joinedload(models.User.roles)).order_by(models.User.id.asc()).offset(skip).limit(limit).all()

def update_user(db: Session, user_id: int, user_update: schemas.UserUpdate):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    if user_update.is_active is not None:
        user.is_active = user_update.is_active
        
    if user_update.role_name:
        # Buscar rol o crearlo si no existe (simplificado)
        role = db.query(models.Role).filter(models.Role.name == user_update.role_name).first()
        if not role:
            role = models.Role(name=user_update.role_name)
            db.add(role)
        
        # Reemplazar roles (asumimos un rol principal por ahora para simplificar UI)
        user.roles = [role]
        
    db.commit()
    db.refresh(user)
    return user

def change_password(db: Session, user_id: int, password_data: schemas.PasswordChange):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    user.password_hash = get_password_hash(password_data.password)
    db.commit()
    return {"message": "Contraseña actualizada correctamente"}

def delete_user(db: Session, user_id: int):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    # Soft delete (desactivar) en lugar de borrar físicamente
    user.is_active = False
    db.commit()
    return {"message": "Usuario desactivado correctamente"}
