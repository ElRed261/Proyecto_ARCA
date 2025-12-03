from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.modules.auth import models
from app.core.security import get_password_hash

def fix_roles():
    db = SessionLocal()
    try:
        # 1. Ensure Roles Exist
        admin_role = db.query(models.Role).filter(models.Role.name == "admin").first()
        if not admin_role:
            admin_role = models.Role(name="admin")
            db.add(admin_role)
            print("Created 'admin' role")
            
        user_role = db.query(models.Role).filter(models.Role.name == "user").first()
        if not user_role:
            user_role = models.Role(name="user")
            db.add(user_role)
            print("Created 'user' role")
        
        db.commit()

        # 2. Fix 'test@arca.com' -> ONLY 'user'
        test_user = db.query(models.User).filter(models.User.email == "test@arca.com").first()
        if test_user:
            test_user.roles = [user_role]
            print("Updated 'test@arca.com' to have ONLY 'user' role")
        else:
            # Create test user if not exists
            test_user = models.User(
                email="test@arca.com", 
                password_hash=get_password_hash("123"),
                is_active=True
            )
            test_user.roles = [user_role]
            db.add(test_user)
            print("Created 'test@arca.com' with 'user' role")

        # 3. Ensure 'admin@arca.com' -> 'admin'
        admin_user = db.query(models.User).filter(models.User.email == "admin@arca.com").first()
        if admin_user:
            # Force update password to ensure it matches '123456'
            admin_user.password_hash = get_password_hash("123456")
            
            # Ensure it has admin role
            has_admin = any(r.name == "admin" for r in admin_user.roles)
            if not has_admin:
                admin_user.roles.append(admin_role)
                print("Added 'admin' role to 'admin@arca.com'")
            print("Updated 'admin@arca.com' password and roles")
        else:
            # Create admin user
            admin_user = models.User(
                email="admin@arca.com", 
                password_hash=get_password_hash("admin123"),
                is_active=True
            )
            admin_user.roles = [admin_role]
            db.add(admin_user)
            print("Created 'admin@arca.com' with 'admin' role (Password: admin123)")

        db.commit()
        print("Roles fixed successfully!")

    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_roles()
