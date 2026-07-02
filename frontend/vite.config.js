import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Tauri espera un puerto fijo; clearScreen false para no borrar logs de Tauri
  clearScreen: false,
  base: './', // Rutas relativas para build
  server: {
    host: true,
    port: 1420,
    strictPort: true,
    watch: {
      usePolling: true,
    },
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'chart-vendor': ['recharts'],
          'jspdf-vendor': ['jspdf'],
          'html2canvas-vendor': ['html2canvas'],
          'excel-vendor': ['xlsx'],
        },
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
    css: true,
  },
})

