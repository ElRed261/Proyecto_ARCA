#!/bin/bash

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== Iniciando Proyecto ARCA (Modo Local) ===${NC}"

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

# 2. Inicializar Base de Datos SQLite (si no existe)
cd backend
source .venv/bin/activate

DB_FILE="arca_local.db"
if [ ! -f "$DB_FILE" ]; then
    echo -e "${YELLOW}Primera ejecución: Inicializando base de datos...${NC}"
    python -m app.modules.auth.init_db
    check_error "No se pudo inicializar la base de datos"
else
    echo -e "${GREEN}Base de datos local: $DB_FILE${NC}"
fi

# 3. Cargar variables de entorno
if [ -f ".env" ]; then
    echo "Cargando variables de entorno..."
    export $(cat .env | xargs)
fi

# 4. Iniciar Backend
echo -e "${YELLOW}Iniciando Backend...${NC}"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > ../backend.log 2>&1 &
BACKEND_PID=$!
echo -e "${GREEN}Backend iniciado (PID: $BACKEND_PID)${NC}"
cd ..

# 5. Iniciar Frontend
echo -e "${YELLOW}Iniciando Frontend...${NC}"
cd frontend
npm run dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
echo -e "${GREEN}Frontend iniciado (PID: $FRONTEND_PID)${NC}"
cd ..

# Manejo de cierre (Ctrl+C)
cleanup() {
    echo -e "\n${YELLOW}Deteniendo servicios...${NC}"
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo -e "${GREEN}Servicios detenidos.${NC}"
    exit 0
}

trap cleanup SIGINT

echo -e "${GREEN}=== Proyecto ARCA corriendo (Modo Offline) ===${NC}"
echo -e "Backend: http://localhost:8000"
echo -e "Frontend: http://localhost:5173"
echo -e "Base de datos: backend/arca_local.db (SQLite)"
echo -e ""
echo -e "${YELLOW}Usuarios disponibles:${NC}"
echo -e "  admin@arca.rd / admin123"
echo -e "  encargado@arca.rd / encargado123"
echo -e "  observador@arca.rd / observador123"
echo -e ""
echo -e "Logs: backend.log, frontend.log"
echo -e "${YELLOW}Presione Ctrl+C para detener.${NC}"

wait
