#!/usr/bin/env bash
# ARCA — lanzador de un solo comando: ./run.sh
#
# Verifica prerequisitos, instala dependencias si hacen falta y arranca la
# app de escritorio (Vite + Tauri/Rust) en modo desarrollo con recarga en vivo.
set -euo pipefail
cd "$(dirname "$0")/frontend"

fail() {
    echo "✗ $1" >&2
    echo "  ↳ $2" >&2
    exit 1
}

# 1) Prerequisitos básicos
command -v node >/dev/null 2>&1 || fail "Node.js no encontrado" "instalalo de https://nodejs.org (v18+)"
command -v cargo >/dev/null 2>&1 || fail "Rust/cargo no encontrado" "instalalo con: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
command -v npm >/dev/null 2>&1 || fail "npm no encontrado" "viene con Node.js"

# 2) Librerías del sistema de Tauri (Linux/v2: webkit2gtk-4.1, etc.)
if command -v pkg-config >/dev/null 2>&1; then
    for lib in glib-2.0 gtk+-3.0 webkit2gtk-4.1; do
        pkg-config --exists "$lib" || fail "falta la librería del sistema '$lib'" \
            "Ubuntu/Debian: sudo apt install libglib2.0-dev pkg-config libgdk-pixbuf-2.0-dev libpango1.0-dev libgtk-3-dev webkit2gtk-4.1 libappindicator3-dev librsvg2-dev"
    done
fi

# 3) Dependencias de Node (instala solo si faltan)
[ -d node_modules ] || npm install

# 4) Arrancar: Vite + Tauri (ventana nativa)
echo ""
echo "════════════════════════════════════════════"
echo "  ARCA — iniciando app de escritorio"
echo "════════════════════════════════════════════"
echo "  Login inicial: ver usuarios de primer arranque"
echo "  (el backend vuelca los usuarios de arranque a primer_inicio.txt"
echo "   en app_data si la DB se creó en blanco)"
echo ""
echo "  La primera compilación de Rust puede tardar varios minutos."
echo "════════════════════════════════════════════"
echo ""

npm run tauri:dev
