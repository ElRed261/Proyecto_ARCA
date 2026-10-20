"""
Script de inicialización de la base de datos SQLite.
Crea las tablas y los usuarios/roles por defecto.

Ejecutar: python -m app.modules.auth.init_db
"""
import sys
from pathlib import Path

# Añadir el directorio backend al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from app.core.database import Base, engine, SessionLocal, create_tables
from app.core.security import get_password_hash
from app.modules.auth.models import User, Role, user_roles


def init_database():
    """Inicializa la base de datos con usuarios y roles por defecto."""
    print("🔧 Inicializando base de datos SQLite...")
    
    # Crear todas las tablas
    create_tables()
    print("✓ Tablas creadas")
    
    db = SessionLocal()
    
    try:
        # Crear roles si no existen
        roles_data = [
            {"name": "admin", "description": "Administrador del sistema"},
            {"name": "encargado", "description": "Supervisor de estación"},
            {"name": "observador", "description": "Operador de observaciones"},
        ]
        
        created_roles = {}
        for role_data in roles_data:
            existing = db.query(Role).filter(Role.name == role_data["name"]).first()
            if not existing:
                role = Role(**role_data)
                db.add(role)
                db.flush()
                created_roles[role_data["name"]] = role
                print(f"  ✓ Rol creado: {role_data['name']}")
            else:
                created_roles[role_data["name"]] = existing
                print(f"  - Rol existente: {role_data['name']}")
        
        # Crear usuarios por defecto si no existen
        users_data = [
            {
                "email": "admin@arca.rd",
                "password": "admin123",
                "role": "admin"
            },
            {
                "email": "encargado@arca.rd",
                "password": "encargado123",
                "role": "encargado"
            },
            {
                "email": "observador@arca.rd",
                "password": "observador123",
                "role": "observador"
            },
        ]
        
        for user_data in users_data:
            existing = db.query(User).filter(User.email == user_data["email"]).first()
            if not existing:
                user = User(
                    email=user_data["email"],
                    password_hash=get_password_hash(user_data["password"]),
                    is_active=True
                )
                # Asignar rol
                role = created_roles.get(user_data["role"])
                if role:
                    user.roles = [role]
                
                db.add(user)
                print(f"  ✓ Usuario creado: {user_data['email']} (rol: {user_data['role']})")
            else:
                print(f"  - Usuario existente: {user_data['email']}")
        
        db.commit()
        print("\n✅ Base de datos inicializada correctamente")
        print("\n📋 Usuarios disponibles:")
        print("   Email                    | Contraseña     | Rol")
        print("   ─────────────────────────┼────────────────┼────────────")
        print("   admin@arca.rd            | admin123       | admin")
        print("   encargado@arca.rd        | encargado123   | encargado")
        print("   observador@arca.rd       | observador123  | observador")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error al inicializar: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_database()
