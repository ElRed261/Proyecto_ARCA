#!/bin/bash

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== Iniciando Proyecto ARCA (Modo Local + Tauri) ===${NC}"

# Función para verificar errores
check_error() {
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error: $1${NC}"
        exit 1
    fi
}

# 1. Pre-flight Checks
echo -e "${YELLOW}Verificando entorno...${NC}"

if [ ! -d "frontend/node_modules" ]; then
    echo -e "${RED}Error: Parece que no se han instalado las dependencias del frontend.${NC}"
    echo "Por favor, ejecute primero: cd frontend && npm install"
    exit 1
fi

# Verificar Rust
if ! command -v cargo &> /dev/null; then
    echo -e "${RED}Error: Rust/Cargo no está instalado.${NC}"
    echo "Instálelo con: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
    exit 1
fi

# 2. Iniciar Frontend con Tauri
echo -e "${YELLOW}Iniciando App Tauri Nativamente...${NC}"
cd frontend
npm run tauri:dev > ../frontend.log 2>&1 &
FRONTEND_PID=$!
echo -e "${GREEN}Frontend Tauri iniciado (PID: $FRONTEND_PID)${NC}"
cd ..

# Manejo de cierre (Ctrl+C)
cleanup() {
    echo -e "\n${YELLOW}Deteniendo servicios (limpiando zombies)...${NC}"
    kill $FRONTEND_PID 2>/dev/null
    # Matar cualquier proceso huérfano de este entorno
    pkill -f "vite" 2>/dev/null
    pkill -f "tauri" 2>/dev/null
    echo -e "${GREEN}Servicios detenidos completamente.${NC}"
    exit 0
}

trap cleanup SIGINT

echo -e "${GREEN}=== Proyecto ARCA corriendo natiuamente (Sin Servidor) ===${NC}"
echo -e "Frontend: Tauri (ventana nativa)"
echo -e "Base de datos local: ~/.local/share/arca_local.db (SQLite por Tauri)"
echo -e ""
echo -e "${YELLOW}Usuarios disponibles:${NC}"
echo -e "  admin@arca.rd / admin123"
echo -e "  encargado@arca.rd / encargado123"
echo -e "  observador@arca.rd / observador123"
echo -e ""
echo -e "Logs: backend.log, frontend.log"
echo -e "${YELLOW}Presione Ctrl+C para detener.${NC}"

wait
