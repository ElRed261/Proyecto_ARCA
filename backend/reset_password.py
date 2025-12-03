from app.core.database import SessionLocal
from app.modules.auth.models import User, Role
from app.core.security import get_password_hash

def reset_admin():
    db = SessionLocal()
    email = "test@arca.com"
    password = "123" # User requested 123
    
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        print(f"Usuario {email} no encontrado. Creándolo...")
        user = User(email=email, is_active=True)
        db.add(user)
    
    # Update password
    user.password_hash = get_password_hash(password)
    
    # Ensure admin role
    admin_role = db.query(Role).filter(Role.name == "admin").first()
    if not admin_role:
        admin_role = Role(name="admin")
        db.add(admin_role)
    
    if admin_role not in user.roles:
        user.roles.append(admin_role)
        
    db.commit()
    print(f"✅ Contraseña para {email} establecida a '{password}'")
    print(f"✅ Rol 'admin' asignado.")
    db.close()

if __name__ == "__main__":
    reset_admin()
