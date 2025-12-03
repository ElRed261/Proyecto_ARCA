from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List
from app.core.database import get_db
from app.core.security import get_password_hash
from app.core.dependencies import get_current_user
from app.modules.auth import models, schemas

router = APIRouter()

# Dependencia para verificar si es admin
def get_current_admin_user(current_user: models.User = Depends(get_current_user)):
    is_admin = any(role.name.lower() in ["admin", "administrador"] for role in current_user.roles)
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos de administrador"
        )
    return current_user

@router.get("/users", response_model=List[schemas.UserResponse])
def list_users(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_admin_user)
):
    users = db.query(models.User).options(joinedload(models.User.roles)).order_by(models.User.id.asc()).offset(skip).limit(limit).all()
    return users

@router.put("/users/{user_id}", response_model=schemas.UserResponse)
def update_user(
    user_id: int, 
    user_update: schemas.UserUpdate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_admin_user)
):
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

@router.put("/users/{user_id}/password")
def change_user_password(
    user_id: int, 
    password_data: schemas.PasswordChange, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_admin_user)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    user.password_hash = get_password_hash(password_data.password)
    db.commit()
    return {"message": "Contraseña actualizada correctamente"}

@router.delete("/users/{user_id}")
def delete_user(
    user_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_admin_user)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    # Soft delete (desactivar) en lugar de borrar físicamente
    user.is_active = False
    db.commit()
    return {"message": "Usuario desactivado correctamente"}
