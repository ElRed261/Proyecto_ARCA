#!/bin/bash

# Matar procesos hijos al salir
trap "kill 0" EXIT

echo "🚀 Iniciando Proyecto ARCA..."

# Iniciar Backend
echo "🐍 Iniciando Backend (FastAPI)..."
cd backend
source .venv/bin/activate
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
