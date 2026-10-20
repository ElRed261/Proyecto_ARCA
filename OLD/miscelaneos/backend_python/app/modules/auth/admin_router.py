from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.auth import models, schemas, services

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
    return services.get_users(db, skip, limit)

@router.put("/users/{user_id}", response_model=schemas.UserResponse)
def update_user(
    user_id: int, 
    user_update: schemas.UserUpdate, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_admin_user)
):
    return services.update_user(db, user_id, user_update)

@router.put("/users/{user_id}/password")
def change_user_password(
    user_id: int, 
    password_data: schemas.PasswordChange, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_admin_user)
):
    return services.change_password(db, user_id, password_data)

@router.delete("/users/{user_id}")
def delete_user(
    user_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_admin_user)
):
    return services.delete_user(db, user_id)
