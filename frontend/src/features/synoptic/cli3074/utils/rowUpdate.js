/**
 * rowUpdate — actualización pura de una fila de la planilla CLI 3074.
 *
 * Separa la lógica testeable del componente:
 * - los booleanos de fenómenos NUNCA pasan por el formateador numérico
 *   (ese era el camino frágil: funcionaba solo porque el formateador los
 *   devolvía intactos por accidente);
 * - los hermanos del objeto `fenomenos` se conservan al alternar un check.
 */

export const decimalFields3074 = [
    'pres_est', 'pres_nmm', 'pres_alti', 'tend_dif',
    'temp_seco', 'temp_humedo', 'hum_ptor', 'hum_tvap',
    'viento_vel', 'visibilidad',
];

export const enforceOneDecimal = (val, field) => {
    if (val === undefined || val === null || val === '') return '';

    if (field === 'hum_hr') {
        const num = parseFloat(val);
        if (!isNaN(num)) {
            return Math.ceil(num).toString();
        }
        return val;
    }

    if (decimalFields3074.includes(field)) {
        if (typeof val === 'number') val = val.toString();
        if (typeof val === 'string' && val.trim() !== '') {
            const parts = val.split('.');
            if (parts.length > 1 && parts[1].length > 1) {
                const num = parseFloat(val);
                if (!isNaN(num)) {
                    const rounded = num >= 0
                        ? Math.ceil(num * 10) / 10
                        : Math.floor(num * 10) / 10;
                    return rounded.toFixed(1);
                }
            }
        }
    }
    return val;
};

/**
 * Aplica un cambio de campo sobre el mapa de filas (inmutable).
 * Devuelve el NUEVO mapa; nunca muta el de entrada.
 */
export function applyCliFieldUpdate(rows, rowNum, fieldPath, value) {
    const next = { ...rows };
    const row = { ...(next[rowNum] || {}), fenomenos: { ...((next[rowNum] || {}).fenomenos || {}) } };

    if (fieldPath.startsWith('fenomenos.')) {
        const subField = fieldPath.split('.')[1];
        // booleanos: se guardan tal cual, sin formateo numérico
        row.fenomenos[subField] = typeof value === 'boolean' ? value : enforceOneDecimal(value, fieldPath);
    } else {
        row[fieldPath] = enforceOneDecimal(value, fieldPath);
    }
    next[rowNum] = row;
    return next;
}
