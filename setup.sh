#!/bin/bash

# Colores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Instalador de Proyecto ARCA ===${NC}"

# 1. Instalar dependencias del sistema
echo -e "\n${BLUE}[1/5] Instalando dependencias del sistema...${NC}"
sudo apt update
sudo apt install -y python3-venv python3-pip nodejs npm postgresql postgresql-contrib
sudo service postgresql start

# 2. Configuración de Base de Datos
echo -e "\n${BLUE}[2/5] Configuración de Base de Datos PostgreSQL${NC}"
read -p "Ingrese el nombre de la base de datos (default: arca_db): " DB_NAME
DB_NAME=${DB_NAME:-arca_db}

read -p "Ingrese el usuario de la base de datos (default: admin_arca): " DB_USER
DB_USER=${DB_USER:-admin_arca}

while true; do
    read -s -p "Ingrese la contraseña para el usuario $DB_USER: " DB_PASS
    echo ""
    read -s -p "Confirme la contraseña: " DB_PASS_CONFIRM
    echo ""
    
    if [ "$DB_PASS" == "$DB_PASS_CONFIRM" ] && [ -n "$DB_PASS" ]; then
        break
    else
        echo -e "${RED}Las contraseñas no coinciden o están vacías. Intente de nuevo.${NC}"
    fi
done

# Opción para eliminar base de datos existente
read -p "¿Desea eliminar la base de datos '$DB_NAME' existente si existe? (s/n): " DROP_DB
if [[ "$DROP_DB" =~ ^[sS]$ ]]; then
    echo -e "${RED}Eliminando base de datos $DB_NAME...${NC}"
    sudo -u postgres psql -c "DROP DATABASE IF EXISTS $DB_NAME;"
    sudo -u postgres psql -c "DROP USER IF EXISTS $DB_USER;"
fi

# Crear usuario y base de datos
echo -e "${GREEN}Creando usuario y base de datos...${NC}"
sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';" || echo "El usuario ya existe o hubo un error (ignorar si ya existe)"
sudo -u postgres psql -c "ALTER USER $DB_USER WITH SUPERUSER;" 
sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;" || echo "La base de datos ya existe o hubo un error"

# 3. Configuración del Backend
echo -e "\n${BLUE}[3/5] Configurando Backend (Python/FastAPI)...${NC}"
cd backend

# Crear .env
echo -e "${GREEN}Creando archivo .env...${NC}"
cat > .env <<EOF
POSTGRES_USER=$DB_USER
POSTGRES_PASSWORD=$DB_PASS
POSTGRES_SERVER=localhost
POSTGRES_DB=$DB_NAME
SECRET_KEY=$(openssl rand -hex 32)
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
EOF

# Crear entorno virtual
if [ ! -d "venv" ]; then
    echo -e "${GREEN}Creando entorno virtual...${NC}"
    python3 -m venv venv
fi

# Instalar dependencias
echo -e "${GREEN}Instalando dependencias de Python...${NC}"
source venv/bin/activate
pip install -r requirements.txt



deactivate
cd ..

# 4. Configuración del Frontend
echo -e "\n${BLUE}[4/5] Configurando Frontend (Node/React)...${NC}"
cd frontend
echo -e "${GREEN}Instalando dependencias de Node...${NC}"
npm install
cd ..

# 5. Creación de Usuario Administrador de la Aplicación
echo -e "\n${BLUE}[5/5] Creación de Usuario Administrador de la Aplicación${NC}"
cd backend
source venv/bin/activate

read -p "Email del administrador (default: admin@arca.com): " ADMIN_EMAIL
ADMIN_EMAIL=${ADMIN_EMAIL:-admin@arca.com}

while true; do
    read -s -p "Contraseña del administrador: " ADMIN_PASS
    echo ""
    read -s -p "Confirme la contraseña: " ADMIN_PASS_CONFIRM
    echo ""
    
    if [ "$ADMIN_PASS" == "$ADMIN_PASS_CONFIRM" ] && [ -n "$ADMIN_PASS" ]; then
        break
    else
        echo -e "${RED}Las contraseñas no coinciden o están vacías. Intente de nuevo.${NC}"
    fi
done

echo -e "${GREEN}Creando usuario administrador...${NC}"
# Cargar variables de entorno para el script
set -a
source .env
set +a
python create_admin.py "$ADMIN_EMAIL" "$ADMIN_PASS"
deactivate
cd ..

# 6. Finalización
echo -e "\n${GREEN}=== Instalación Completada ===${NC}"
echo -e "Para iniciar el proyecto:"
echo -e "1. Backend: cd backend && source venv/bin/activate && uvicorn app.main:app --reload"
echo -e "2. Frontend: cd frontend && npm run dev"
echo -e "\nO usa el script de inicio si existe."

# Dar permisos de ejecución
chmod +x setup.sh
