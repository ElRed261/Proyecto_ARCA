import { describe, it, expect } from 'vitest';
import { formatIsoToDisplay, parseDisplayToIso, maskDateInput } from '../shared/utils/dateMask';

describe('dateMask — campo de fecha DD/MM/YYYY sin date-picker nativo', () => {
    it('formatea ISO a display', () => {
        expect(formatIsoToDisplay('2026-08-15')).toBe('15/08/2026');
        expect(formatIsoToDisplay('')).toBe('');
        expect(formatIsoToDisplay(null)).toBe('');
    });

    it('parsea display válido a ISO', () => {
        expect(parseDisplayToIso('15/08/2026')).toEqual({ iso: '2026-08-15', valid: true });
    });

    it('rechaza fechas calendario imposibles (31/02, día 00, mes 13)', () => {
        expect(parseDisplayToIso('31/02/2026').valid).toBe(false);
        expect(parseDisplayToIso('00/08/2026').valid).toBe(false);
        expect(parseDisplayToIso('15/13/2026').valid).toBe(false);
        expect(parseDisplayToIso('29/02/2026').valid).toBe(false);
    });

    it('acepta 29/02 solo en bisiesto y respeta el rango 1990-2250', () => {
        expect(parseDisplayToIso('29/02/2024')).toEqual({ iso: '2024-02-29', valid: true });
        expect(parseDisplayToIso('15/08/1990').valid).toBe(true);
        expect(parseDisplayToIso('15/08/1989').valid).toBe(false);
        expect(parseDisplayToIso('15/08/2251').valid).toBe(false);
    });

    it('maskDateInput: solo dígitos con slashes automáticos, tope 8 dígitos', () => {
        expect(maskDateInput('')).toBe('');
        expect(maskDateInput('1')).toBe('1');
        expect(maskDateInput('15')).toBe('15');
        expect(maskDateInput('1508')).toBe('15/08');
        expect(maskDateInput('15082026')).toBe('15/08/2026');
        expect(maskDateInput('150820260000')).toBe('15/08/2026');
        expect(maskDateInput('1a5b08')).toBe('15/08');
    });
});

