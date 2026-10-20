import { describe, it, expect } from 'vitest';
import { sanitizeSynopGroup } from '../features/synoptic/utils/synopticUtils';

describe('sanitizeSynopGroup — grupos SYNOP: max 5 dígitos/domain "/"', () => {
    it('acepta 5 dígitos exactos', () => {
        expect(sanitizeSynopGroup('32466')).toBe('32466');
        expect(sanitizeSynopGroup('00000')).toBe('00000');
    });

    it('acepta dígitos con "/" de datos ausentes', () => {
        expect(sanitizeSynopGroup('120//')).toBe('120//');
        expect(sanitizeSynopGroup('/////')).toBe('/////');
        expect(sanitizeSynopGroup('32///')).toBe('32///');
    });

    it('trunca a 5 caracteres (IrIxHVV no puede ser 324661)', () => {
        expect(sanitizeSynopGroup('324661')).toBe('32466');
        expect(sanitizeSynopGroup('120//8')).toBe('120//');
    });

    it('elimina caracteres no válidos (letras, punto, espacios, signos)', () => {
        expect(sanitizeSynopGroup('32a')).toBe('32');
        expect(sanitizeSynopGroup('12.5')).toBe('125');
        expect(sanitizeSynopGroup(' 123')).toBe('123');
        expect(sanitizeSynopGroup('3-2/~')).toBe('32/');
    });

    it('vacío se conserva vacío', () => {
        expect(sanitizeSynopGroup('')).toBe('');
    });
});
