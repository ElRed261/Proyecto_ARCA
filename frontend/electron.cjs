const { app, BrowserWindow } = require('electron');
const path = require('path');

// Determinar si estamos en desarrollo o producción
const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;

function createWindow() {
    const mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        minWidth: 1200,
        minHeight: 700,
        title: 'Proyecto ARCA - Sistema Meteorológico',
        icon: path.join(__dirname, 'public', 'icon.png'),
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js')
        },
        autoHideMenuBar: false,
        show: false
    });

    // Mostrar ventana cuando esté lista para evitar flash blanco
    mainWindow.once('ready-to-show', () => {
        mainWindow.show();
    });

    // Cargar la URL según el entorno
    if (isDev) {
        // En desarrollo, cargar desde el servidor de Vite
        mainWindow.loadURL('http://localhost:5173');
        // Abrir DevTools en desarrollo
        mainWindow.webContents.openDevTools();
    } else {
        // En producción, cargar el archivo HTML compilado
        mainWindow.loadFile(path.join(__dirname, 'dist', 'index.html'));
    }

    // Manejar el título de la ventana
    mainWindow.on('page-title-updated', (event) => {
        event.preventDefault();
    });
}

// Cuando Electron esté listo, crear la ventana
app.whenReady().then(() => {
    createWindow();

    // En macOS, re-crear ventana al hacer clic en el icono del dock
    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

// Cerrar la app cuando todas las ventanas estén cerradas (excepto en macOS)
app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});
