#!/bin/bash

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== Iniciando Proyecto ARCA ===${NC}"

# Función para verificar errores
check_error() {
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error: $1${NC}"
        exit 1
    fi
}

# 1. Pre-flight Checks
echo -e "${YELLOW}Verificando entorno...${NC}"

# Verificar si se ejecutó el setup
if [ ! -d "backend/.venv" ] || [ ! -d "frontend/node_modules" ]; then
    echo -e "${RED}Error: Parece que no se han instalado las dependencias.${NC}"
    echo "Por favor, ejecute primero: ./setup_full.sh"
    exit 1
fi

# Verificar PostgreSQL
if ! systemctl is-active --quiet postgresql && ! service postgresql status > /dev/null; then
    echo -e "${YELLOW}PostgreSQL no está corriendo. Intentando iniciar...${NC}"
    sudo service postgresql start
    check_error "No se pudo iniciar PostgreSQL. Asegúrese de tener permisos."
fi

# 2. Iniciar Backend
echo -e "${YELLOW}Iniciando Backend...${NC}"
cd backend
source .venv/bin/activate

# Cargar variables de entorno
if [ -f ".env" ]; then
    echo "Cargando variables de entorno..."
    export $(cat .env | xargs)
fi

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > ../backend.log 2>&1 &
BACKEND_PID=$!
echo -e "${GREEN}Backend iniciado (PID: $BACKEND_PID)${NC}"
cd ..

# 3. Iniciar Frontend
echo -e "${YELLOW}Iniciando Frontend...${NC}"
cd frontend
npm run dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
echo -e "${GREEN}Frontend iniciado (PID: $FRONTEND_PID)${NC}"
cd ..

# Manejo de cierre (Ctrl+C)
cleanup() {
    echo -e "\n${YELLOW}Deteniendo servicios...${NC}"
    kill $BACKEND_PID
    kill $FRONTEND_PID
    echo -e "${GREEN}Servicios detenidos.${NC}"
    exit 0
}

trap cleanup SIGINT

echo -e "${GREEN}=== Proyecto corriendo ===${NC}"
echo -e "Backend: http://localhost:8000"
echo -e "Frontend: http://localhost:5173 (o puerto asignado por Vite)"
echo -e "Logs disponibles en backend.log y frontend.log"
echo -e "${YELLOW}Presione Ctrl+C para detener.${NC}"

wait
