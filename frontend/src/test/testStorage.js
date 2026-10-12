/* global describe */

/**
 * Asegura un localStorage operable en cualquier entorno de test (jsdom o node).
 * Cuando el runner corre en node puro, localStorage global no existe y Tauri
 * invoke leería el token de una var inexistente; este helper garantiza el
 * contrato (getItem/setItem/removeItem/clear) en ambos casos.
 */
export function ensureLocalStorage() {
    if (typeof globalThis.localStorage === 'undefined' || !globalThis.localStorage) {
        const store = new Map();
        const storage = {
            getItem: (k) => (store.has(k) ? store.get(k) : null),
            setItem: (k, v) => {
                store.set(k, String(v));
            },
            removeItem: (k) => {
                store.delete(k);
            },
            clear: () => {
                store.clear();
            },
        };
        Object.defineProperty(globalThis, 'localStorage', {
            configurable: true,
            value: storage,
        });
    }
    return globalThis.localStorage;
}

export const clearStorage = () => {
    if (globalThis.localStorage) globalThis.localStorage.clear();
};
