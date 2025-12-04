const { contextBridge, ipcRenderer } = require('electron');

// Exponer APIs seguras al proceso de renderizado
contextBridge.exposeInMainWorld('electronAPI', {
    // Información de la plataforma
    platform: process.platform,

    // Verificar si estamos en Electron
    isElectron: true,

    // Métodos para comunicación con el proceso principal (si se necesitan en el futuro)
    send: (channel, data) => {
        const validChannels = ['app-message'];
        if (validChannels.includes(channel)) {
            ipcRenderer.send(channel, data);
        }
    },
    receive: (channel, func) => {
        const validChannels = ['app-response'];
        if (validChannels.includes(channel)) {
            ipcRenderer.on(channel, (event, ...args) => func(...args));
        }
    }
});
