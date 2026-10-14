/**
 * Constantes y utilidades para el módulo sinóptico
 */

// =============================================================================
// CONSTANTES SYNOP
// =============================================================================

export const AAXX = "AAXX";           // Identificador de mensaje superficie
export const CONST_333 = "333";       // Sección 3
export const CONST_555 = "555";       // Sección 5

// Horas de observación
export const HOURS = ["06Z", "09Z", "12Z", "15Z", "18Z", "21Z", "00Z", "03Z"];

// Horas pares (tienen T_max/T_min y grupos 1snTx/2snTn)
export const EVEN_HOURS = ["00Z", "06Z", "12Z", "18Z"];

// Horas impares (NO tienen T_max/T_min)
export const ODD_HOURS = ["03Z", "09Z", "15Z", "21Z"];

// =============================================================================
// FUNCIONES DE NORMALIZACIÓN
// =============================================================================

/**
 * Normaliza la entrada de presión.
 * Si el valor es menor a 100, asume que es formato corto (15.3 → 1015.3)
 * @param {string} input - Valor ingresado
 * @returns {string} - Valor normalizado con 1000 añadido si es necesario
 */
export const normalizePressure = (input) => {
    if (!input || input.trim() === '') return '';
    const num = parseFloat(input);
    if (isNaN(num)) return input;
    if (num < 100) {
        return (1000 + num).toFixed(1);
    }
    return input;
};

/**
 * Formatea fecha de YYYY-MM-DD a dd/mm/aaaa
 * @param {string} dateStr - Fecha en formato YYYY-MM-DD o DDMMYYYY
 * @returns {string} - Fecha formateada como dd/mm/aaaa
 */
export const formatDateDisplay = (dateStr) => {
    if (!dateStr) return '';

    // Formato YYYY-MM-DD
    if (dateStr.includes('-')) {
        const [yyyy, mm, dd] = dateStr.split('-');
        return `${dd}/${mm}/${yyyy}`;
    }

    // Formato DDMMYYYY
    if (dateStr.length === 8) {
        return `${dateStr.substring(0, 2)}/${dateStr.substring(2, 4)}/${dateStr.substring(4, 8)}`;
    }

    return dateStr;
};

/**
 * Convierte fecha de dd/mm/aaaa o DDMMYYYY a YYYY-MM-DD
 * @param {string} dateStr - Fecha en formato dd/mm/aaaa o DDMMYYYY
 * @returns {string} - Fecha en formato YYYY-MM-DD
 */
export const toISODate = (dateStr) => {
    if (!dateStr) return '';

    // Ya es formato ISO
    if (dateStr.includes('-')) return dateStr;

    // Formato DDMMYYYY
    if (dateStr.length === 8) {
        const dd = dateStr.substring(0, 2);
        const mm = dateStr.substring(2, 4);
        const yyyy = dateStr.substring(4, 8);
        return `${yyyy}-${mm}-${dd}`;
    }

    return dateStr;
};

/**
 * Obtiene la fecha de hoy en formato YYYY-MM-DD
 * @returns {string}
 */
export const getTodayISO = () => {
    const today = new Date();
    const yyyy = today.getFullYear();
    const mm = String(today.getMonth() + 1).padStart(2, '0');
    const dd = String(today.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
};

/**
 * Crea estado inicial de observaciones para todas las horas
 * @returns {Object}
 */
export const createInitialObservations = () => {
    return HOURS.reduce((acc, hour) => ({ ...acc, [hour]: {} }), {});
};

/**
 * Verifica si hay datos de temperatura en alguna hora
 * @param {Object} observations - Objeto de observaciones por hora
 * @returns {boolean}
 */
export const hasTemperatureData = (observations) => {
    if (!observations || typeof observations !== 'object') return false;
    for (const hora of HOURS) {
        const data = observations[hora] || {};
        if (data.ts && data.ts.trim() !== '') return true;
        if (data.th && data.th.trim() !== '') return true;
    }
    return false;
};

/**
 * Convierte valor a string seguro (sin undefined/null)
 * @param {any} val - Valor a convertir
 * @returns {string}
 */
export const safeValue = (val) => {
    if (val === undefined || val === null) return '';
    return String(val);
};

/**
 * Sanitizador de grupos SYNOP ( Campo met_* / extra_*):
 * - máximo 5 caracteres (todo grupo OMM FM 12 es de 5)
 * - solo dígitos y "/" (ausencia de datos)
 */
export const sanitizeSynopGroup = (value) => {
    if (value === null || value === undefined) return '';
    return String(value)
        .replace(/[^0-9/]/g, '')
        .slice(0, 5);
};

/**
 * Claves por hora que NO son datos (no cuentan para el avance).
 */
export const HOUR_META_KEYS = ['station_id', 'fecha', 'correc_alt', 'nombre_observador'];

/**
 * Campos de dato esperados por hora (denominador honesto del avance).
 * Las pares llevan T_max/T_min y sus grupos; las impares no.
 */
const BASE_DATA_KEYS = [
    'ts', 'th', 'pres_est', 'p3', 'p24', 'viento_dir', 'viento_vel', 'visibilidad', 'll',
    'meteo_2_1', 'meteo_4_irixhvv', 'meteo_4_1', 'meteo_4_6',
    'meteo_6_2', 'meteo_8_1', 'extra_8ns_1', 'extra_8ns_2',
];
const EVEN_EXTRA_KEYS = ['t_max', 't_min', 't_max_24h', 't_min_24h'];

/**
 * Avance de una hora: { done, total, ratio }.
 * Heurística de ORIENTACIÓN (no validación): done = campos con valor real.
 */
export function hourCompletion(hourData, hora) {
    const expected = EVEN_HOURS.includes(hora)
        ? [...BASE_DATA_KEYS, ...EVEN_EXTRA_KEYS]
        : BASE_DATA_KEYS;
    let done = 0;
    const data = hourData && typeof hourData === 'object' ? hourData : {};
    for (const key of expected) {
        const v = data[key];
        if (v !== undefined && v !== null && String(v).trim() !== '') done += 1;
    }
    return { done, total: expected.length, ratio: expected.length ? done / expected.length : 0 };
}

/**
 * Del mensaje SaveErr del backend ("el grupo 'X' en hora Y ...") al campo.
 * Devuelve { field, hour } o null si no hay culpable identificable.
 */
export function parseFieldError(message) {
    if (typeof message !== 'string' || !message) return null;
    const m = message.match(/el grupo '([A-Za-z0-9_]+)' en hora ([0-9]{2}Z)/);
    if (!m) return null;
    return { field: m[1], hour: m[2] };
}
