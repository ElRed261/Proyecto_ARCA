# ARCA Frontend

Frontend React 19 + Vite 7 + Tailwind v4 de Proyecto ARCA (app desktop Tauri v2).

## Comandos

```bash
npm install        # instalar dependencias
npm run tauri:dev  # app desktop completa (Tauri + frontend) — el comando principal
npm run dev        # solo frontend en browser (sin backend Tauri)
npm run lint       # eslint
npm test           # vitest (suite de tests)
npm run build      # build de producción del frontend
npm run tauri:build# bundle de escritorio (deb/AppImage)
```

## Stack

- React 19 + Vite 7
- Tailwind CSS v4
- React Router v7
- Recharts (gráficos)
- Tauri v2 (backend Rust en `src-tauri/`)
