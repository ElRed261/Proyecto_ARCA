import { describe, it, expect } from 'vitest';
import { publishHour, subscribeHour, getCurrentHour, resetHourBus } from '../shared/utils/hourThemeBus';

describe('hourThemeBus — el rail sigue la hora del sinóptico', () => {
    it('publicar y leer la hora actual', () => {
        resetHourBus();
        expect(getCurrentHour()).toBe('06Z');
        publishHour('12Z');
        expect(getCurrentHour()).toBe('12Z');
    });

    it('suscriptores reciben cada cambio', () => {
        resetHourBus();
        const seen = [];
        const unsub = subscribeHour((h) => seen.push(h));
        publishHour('15Z');
        publishHour('00Z');
        expect(seen).toEqual(['15Z', '00Z']);
        unsub();
    });

    it('darse de baja deja de recibir', () => {
        resetHourBus();
        const seen = [];
        const unsub = subscribeHour((h) => seen.push(h));
        unsub();
        publishHour('18Z');
        expect(seen).toEqual([]);
    });

    it('ignora horas desconocidas sin romper el estado', () => {
        resetHourBus();
        publishHour('12Z');
        publishHour('99Z');
        expect(getCurrentHour()).toBe('12Z');
    });
});
