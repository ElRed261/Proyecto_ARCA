/**
 * P4.4 — borrador sinóptico ligado a (estación, fecha).
 *
 * Antes el draft vivía suelto: una pestaña vieja o un cambio de estación
 * restauraban datos del día/estación anterior como si fueran actuales.
 * Ahora todo draft lleva metadata y se invalida si no coincide.
 */

export const DRAFT_KEY = 'synoptic_draft';

/** Adjunta estación/fecha al payload del draft. */
export function bindDraft(state, station, fecha) {
    return {
        ...state,
        station: station ?? null,
        fecha: fecha ?? null,
    };
}

/** El draft solo es usable si pertenece a ESTA estación + ESTA fecha. */
export function isDraftValidFor(draft, station, fecha) {
    if (!draft || typeof draft !== 'object') return false;
    if (!draft.station || !draft.fecha) return false;
    return draft.station === station && draft.fecha === fecha;
}
