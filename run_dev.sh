#!/bin/bash

# Matar procesos hijos al salir
trap "kill 0" EXIT

echo "🚀 Iniciando Proyecto ARCA..."

# Iniciar Backend
echo "🐍 Iniciando Backend (FastAPI)..."
cd backend
source venv/bin/activate
# Cargar variables de entorno
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Verificar si el puerto 8000 está en uso
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  El puerto 8000 está en uso. Intentando matar el proceso..."
    fuser -k 8000/tcp
    sleep 1
fi
uvicorn app.main:app --reload &
BACKEND_PID=$!
cd ..

# Esperar un momento para que el backend arranque
sleep 2

# Iniciar Frontend
echo "⚛️ Iniciando Frontend (Vite)..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo "✅ Todo listo. Presiona Ctrl+C para detener."
wait
