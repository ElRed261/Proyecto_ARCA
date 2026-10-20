import { describe, it, expect } from 'vitest';
import { applyCliFieldUpdate, enforceOneDecimal } from '../features/synoptic/cli3074/utils/rowUpdate';

const base = {
    2: {
        pres_est: '1012.0',
        fenomenos: { tiempo_presente: '', granizo: false, trueno: false },
    },
};

describe('applyCliFieldUpdate — fenómenos y robustez del path booleano', () => {
    it('alternar un check a true lo guarda sin pasar por el formateador', () => {
        const next = applyCliFieldUpdate(base, 2, 'fenomenos.granizo', true);
        expect(next[2].fenomenos.granizo).toBe(true);
    });

    it('desmarcar vuelve a false', () => {
        const on = applyCliFieldUpdate(base, 2, 'fenomenos.granizo', true);
        const off = applyCliFieldUpdate(on, 2, 'fenomenos.granizo', false);
        expect(off[2].fenomenos.granizo).toBe(false);
    });

    it('alternar un check conserva a sus hermanos', () => {
        const next = applyCliFieldUpdate(base, 2, 'fenomenos.trueno', true);
        expect(next[2].fenomenos.granizo).toBe(false);
        expect(next[2].fenomenos.trueno).toBe(true);
        expect(next[2].fenomenos.tiempo_presente).toBe('');
    });

    it('no muta el mapa de entrada', () => {
        const before = JSON.stringify(base);
        applyCliFieldUpdate(base, 2, 'fenomenos.granizo', true);
        expect(JSON.stringify(base)).toBe(before);
    });

    it('tiempo_presente (texto) sigue su camino normal', () => {
        const next = applyCliFieldUpdate(base, 2, 'fenomenos.tiempo_presente', '02');
        expect(next[2].fenomenos.tiempo_presente).toBe('02');
    });

    it('campos numéricos se siguen formateando a un decimal', () => {
        const next = applyCliFieldUpdate(base, 2, 'pres_est', '1012.05');
        expect(next[2].pres_est).toBe('1012.1');
        expect(enforceOneDecimal(true, 'pres_est')).toBe(true);
    });

    it('fila inexistente se crea con fenomenos por defecto parcial', () => {
        const next = applyCliFieldUpdate({}, 5, 'fenomenos.niebla', true);
        expect(next[5].fenomenos.niebla).toBe(true);
    });
});
