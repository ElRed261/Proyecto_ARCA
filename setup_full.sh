#!/bin/bash

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Iniciando Instalación Completa de Proyecto ARCA ===${NC}"

# Función para verificar errores
check_error() {
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error: $1${NC}"
        exit 1
    fi
}

# 1. Actualizar sistema e instalar dependencias del sistema
echo -e "${YELLOW}[1/5] Instalando dependencias del sistema...${NC}"
sudo apt-get update
check_error "Falló la actualización de repositorios"

# Lista de paquetes necesarios
PACKAGES="python3 python3-venv python3-pip python3-dev nodejs postgresql postgresql-contrib libpq-dev git curl build-essential"

echo "Instalando: $PACKAGES"
sudo apt-get install -y $PACKAGES
check_error "Falló la instalación de paquetes del sistema"

# 2. Configuración de Base de Datos (PostgreSQL)
echo -e "${YELLOW}[2/5] Configurando PostgreSQL...${NC}"

# Iniciar servicio
sudo service postgresql start
check_error "No se pudo iniciar el servicio de PostgreSQL"

# Esperar a que PostgreSQL esté listo
echo "Esperando a que PostgreSQL inicie..."
until sudo -u postgres psql -c '\l' > /dev/null 2>&1; do
  echo "Esperando servicio de base de datos..."
  sleep 2
done

# Solicitar credenciales para la BD
echo -e "${GREEN}Configuración de la Base de Datos${NC}"
while true; do
    read -p "Ingrese el nombre de usuario para la BD [admin_arca]: " DB_USER
    DB_USER=${DB_USER:-admin_arca}
    
    read -s -p "Ingrese la contraseña para el usuario '$DB_USER': " DB_PASS
    echo
    read -s -p "Confirme la contraseña: " DB_PASS_CONFIRM
    echo
    
    if [ "$DB_PASS" == "$DB_PASS_CONFIRM" ] && [ ! -z "$DB_PASS" ]; then
        break
    else
        echo -e "${RED}Las contraseñas no coinciden o están vacías. Intente de nuevo.${NC}"
    fi
done

DB_NAME="arca_db"

# Crear usuario y base de datos en Postgres
echo "Configurando usuario y base de datos..."

# Cambiar a un directorio accesible por todos para evitar errores de permisos con sudo -u postgres
CURRENT_DIR=$(pwd)
cd /tmp

# 1. Crear usuario si no existe
sudo -u postgres psql -c "DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$DB_USER') THEN
        CREATE ROLE $DB_USER LOGIN PASSWORD '$DB_PASS';
    END IF;
END
\$\$;"
check_error "Falló la verificación/creación del usuario"

# 2. Asegurar que la contraseña sea la correcta (por si el usuario ya existía)
echo "Actualizando contraseña del usuario..."
sudo -u postgres psql -c "ALTER ROLE $DB_USER WITH PASSWORD '$DB_PASS';"
check_error "Falló la actualización de la contraseña"

# 3. Eliminar base de datos si existe (SOLICITADO POR EL USUARIO)
echo "Eliminando base de datos anterior si existe..."
sudo -u postgres psql -c "DROP DATABASE IF EXISTS $DB_NAME;"
check_error "Falló la eliminación de la base de datos anterior"

# 4. Crear base de datos
echo "Creando base de datos '$DB_NAME'..."
sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
check_error "Falló la creación de la base de datos"

# 5. Dar privilegios
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
# También dar permisos en el esquema public (necesario en PG 15+)
sudo -u postgres psql -d $DB_NAME -c "GRANT ALL ON SCHEMA public TO $DB_USER;" 2>/dev/null || true

# Volver al directorio original
cd "$CURRENT_DIR"

# 3. Configuración del Backend
echo -e "${YELLOW}[3/5] Configurando Backend (Python/FastAPI)...${NC}"
cd backend

# Crear entorno virtual
if [ ! -d ".venv" ]; then
    echo "Creando entorno virtual..."
    python3 -m venv .venv
    check_error "Falló la creación del entorno virtual"
fi

# Activar entorno e instalar dependencias
echo "Instalando dependencias de Python..."
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
check_error "Falló la instalación de dependencias de Python"

# Crear archivo .env
echo "Generando archivo .env..."
# Usamos 127.0.0.1 para forzar IPv4 y evitar problemas con ::1
cat > .env <<EOF
POSTGRES_USER=$DB_USER
POSTGRES_PASSWORD=$DB_PASS
POSTGRES_SERVER=127.0.0.1
POSTGRES_DB=$DB_NAME
SECRET_KEY=$(openssl rand -hex 32)
EOF

# Exportar variables para que el script de python las vea
export POSTGRES_USER=$DB_USER
export POSTGRES_PASSWORD=$DB_PASS
export POSTGRES_SERVER=127.0.0.1
export POSTGRES_DB=$DB_NAME

# Crear usuario administrador de la aplicación
echo -e "${GREEN}Creación del Usuario Administrador de la Aplicación${NC}"
while true; do
    read -p "Ingrese el email del administrador [admin@arca.com]: " ADMIN_EMAIL
    ADMIN_EMAIL=${ADMIN_EMAIL:-admin@arca.com}
    
    read -s -p "Ingrese la contraseña del administrador: " ADMIN_PASS
    echo
    read -s -p "Confirme la contraseña: " ADMIN_PASS_CONFIRM
    echo
    
    if [ "$ADMIN_PASS" == "$ADMIN_PASS_CONFIRM" ] && [ ! -z "$ADMIN_PASS" ]; then
        break
    else
        echo -e "${RED}Las contraseñas no coinciden o están vacías. Intente de nuevo.${NC}"
    fi
done

echo "Registrando administrador en la base de datos..."
# Asegurarse de estar en el directorio correcto para que los imports funcionen
export PYTHONPATH=$PYTHONPATH:.
python create_admin.py "$ADMIN_EMAIL" "$ADMIN_PASS"
check_error "Falló la creación del usuario administrador"

deactivate
cd ..

# 4. Configuración del Frontend
echo -e "${YELLOW}[4/5] Configurando Frontend (Node.js/React)...${NC}"
cd frontend

echo "Instalando dependencias de Node.js..."
npm install
check_error "Falló la instalación de dependencias de Node.js"

cd ..

# 5. Finalización
echo -e "${GREEN}=== Instalación Completada Exitosamente ===${NC}"
echo -e "Para iniciar el proyecto, ejecute: ${YELLOW}./run_full.sh${NC}"
