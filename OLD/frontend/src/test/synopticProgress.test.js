import { describe, it, expect } from 'vitest';
import { hourCompletion, parseFieldError, HOUR_META_KEYS } from '../features/synoptic/utils/synopticUtils';

describe('hourCompletion — avance honesto por hora', () => {
    it('hora vacía da 0/total', () => {
        const c = hourCompletion({}, '06Z');
        expect(c.done).toBe(0);
        expect(c.total).toBeGreaterThan(10);
    });

    it('hora par completa da 100%', () => {
        const full = {
            ts: '30', th: '20', pres_est: '1016', p3: '1012', p24: '1010',
            viento_dir: '12', viento_vel: '8', visibilidad: '20', ll: '0',
            t_max: '32', t_min: '25', t_max_24h: '33', t_min_24h: '24',
            meteo_2_1: '12023', meteo_4_irixhvv: '001', meteo_4_1: '31018',
            meteo_4_6: '02', meteo_6_2: '0', meteo_8_1: '56',
            extra_8ns_1: '80201', extra_8ns_2: '',
        };
        const c = hourCompletion(full, '06Z');
        expect(c.done).toBe(c.total - 1);
        expect(c.ratio).toBeCloseTo((c.total - 1) / c.total);
    });

    it('hora impar no exige t_max/t_min en el denominador', () => {
        const odd = hourCompletion({}, '09Z');
        const even = hourCompletion({}, '06Z');
        expect(odd.total).toBeLessThan(even.total);
    });

    it('claves meta (station_id, fecha…) no cuentan', () => {
        expect(HOUR_META_KEYS).toContain('station_id');
        const c = hourCompletion({ station_id: '78486', fecha: '2026-08-15', correc_alt: '1.5' }, '06Z');
        expect(c.done).toBe(0);
    });

    it('cuenta valores con solo espacios como vacíos', () => {
        const c = hourCompletion({ ts: '   ', th: '20' }, '06Z');
        expect(c.done).toBe(1);
    });
});

describe('parseFieldError — del mensaje del backend al campo culpable', () => {
    it('extrae campo y hora del formato SaveErr', () => {
        expect(parseFieldError("el grupo 'meteo_4_irixhvv' en hora 00Z excede 5 caracteres (324661)")).toEqual({
            field: 'meteo_4_irixhvv',
            hour: '00Z',
        });
    });

    it('devuelve null si no hay campo identificable', () => {
        expect(parseFieldError('Error al guardar la observación')).toBeNull();
        expect(parseFieldError('')).toBeNull();
        expect(parseFieldError(null)).toBeNull();
    });
});
