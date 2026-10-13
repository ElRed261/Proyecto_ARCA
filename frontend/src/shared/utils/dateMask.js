/**
 * dateMask — campo de fecha DD/MM/YYYY sin el date-picker nativo del OS.
 * El contrato con el backend no cambia: el estado sigue siendo ISO YYYY-MM-DD.
 */

export function maskDateInput(raw) {
    const digits = String(raw ?? '').replace(/\D/g, '').slice(0, 8);
    if (digits.length <= 2) return digits;
    if (digits.length <= 4) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
    return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
}

export function formatIsoToDisplay(iso) {
    if (!iso || typeof iso !== 'string') return '';
    const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!m) return '';
    return `${m[3]}/${m[2]}/${m[1]}`;
}

export function parseDisplayToIso(display) {
    const fail = { iso: null, valid: false };
    if (typeof display !== 'string') return fail;
    const m = display.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    if (!m) return fail;
    const d = Number(m[1]);
    const mo = Number(m[2]);
    const y = Number(m[3]);
    if (y < 1990 || y > 2250) return fail;
    if (mo < 1 || mo > 12) return fail;
    const leap = (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;
    const dim = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mo - 1];
    if (d < 1 || d > dim) return fail;
    const iso = `${m[3]}-${m[2]}-${m[1]}`;
    return { iso, valid: true };
}
