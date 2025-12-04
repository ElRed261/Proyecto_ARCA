import os
import sys
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine, Base
from app.modules.auth.models import User, Role
from app.core.security import get_password_hash

def create_admin_user(email, password):
    # Asegurar que las tablas existan
    print("Verificando/Creando tablas de base de datos...")
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()
    try:
        # 1. Asegurar que existe el rol de admin
        admin_role = db.query(Role).filter(Role.name == "admin").first()
        if not admin_role:
            print("Creando rol 'admin'...")
            admin_role = Role(name="admin", description="Administrador del sistema")
            db.add(admin_role)
            db.commit()
            db.refresh(admin_role)
        
        # 2. Verificar si el usuario ya existe
        user = db.query(User).filter(User.email == email).first()
        if user:
            print(f"El usuario {email} ya existe.")
            return

        # 3. Crear usuario admin
        print(f"Creando usuario admin: {email}")
        hashed_password = get_password_hash(password)
        new_user = User(
            email=email,
            password_hash=hashed_password,
            is_active=True
        )
        new_user.roles.append(admin_role)
        
        db.add(new_user)
        db.commit()
        print("Usuario admin creado exitosamente.")
        
    except Exception as e:
        print(f"Error al crear usuario admin: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python create_admin.py <email> <password>")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    
    create_admin_user(email, password)
