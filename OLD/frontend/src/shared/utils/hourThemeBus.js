/**
 * hourThemeBus — la barra lateral sigue el tema de la hora sinóptica.
 *
 * SynopticPage publica su hora activa; el Sidebar se suscribe y, solo en la
 * ruta /synoptic, tiñe el rail con el accent de esa hora (misma línea
 * gráfica que el fondo del formulario).
 */

import { HOURS } from '../../features/synoptic/utils/synopticUtils';

let current = '06Z';
const listeners = new Set();

export function publishHour(hour) {
    if (!HOURS.includes(hour)) return;
    if (hour === current) return;
    current = hour;
    listeners.forEach((fn) => {
        try {
            fn(hour);
        } catch {
            // un suscriptor roto no tumba a los demás
        }
    });
}

export function subscribeHour(fn) {
    listeners.add(fn);
    return () => {
        listeners.delete(fn);
    };
}

export function getCurrentHour() {
    return current;
}

export function resetHourBus() {
    current = '06Z';
    listeners.clear();
}
