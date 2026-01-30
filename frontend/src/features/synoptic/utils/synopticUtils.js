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
