/* global vi, describe, it, expect */
import { describe, it, expect } from 'vitest';
import {
    bindDraft,
    isDraftValidFor,
    DRAFT_KEY,
} from '../features/synoptic/utils/synopticDraft';

describe('synopticDraft — borradores ligados a (estación, fecha) y autosave', () => {
    it('DRAFT_KEY es estable para wiring', () => {
        expect(DRAFT_KEY).toBe('synoptic_draft');
    });

    it('bindDraft adjunta estación y fecha al payload', () => {
        const payload = bindDraft({ observations: { '06Z': { ts: '30' } }, activeHour: '06Z' }, '78486', '2026-08-15');
        expect(payload.station).toBe('78486');
        expect(payload.fecha).toBe('2026-08-15');
        expect(payload.activeHour).toBe('06Z');
        expect(payload.observations['06Z'].ts).toBe('30');
    });

    it('isDraftValidFor: válido con estación y fecha idénticas', () => {
        const draft = bindDraft({}, '78486', '2026-08-15');
        expect(isDraftValidFor(draft, '78486', '2026-08-15')).toBe(true);
    });

    it('isDraftValidFor: rechaza borrador de otra estación (contaminación cruzada)', () => {
        const draft = bindDraft({}, '78486', '2026-08-15');
        expect(isDraftValidFor(draft, '78451', '2026-08-15')).toBe(false);
    });

    it('isDraftValidFor: rechaza borrador de otra fecha', () => {
        const draft = bindDraft({}, '78486', '2026-08-15');
        expect(isDraftValidFor(draft, '78486', '2026-08-16')).toBe(false);
    });

    it('isDraftValidFor: rechaza borrador sin metadatos (legacy/DRAFT viejo sin liga)', () => {
        // está oldera format — sin station/fecha debe invalidarse, no resucitarse
        expect(isDraftValidFor({ observations: { x: 1 } }, '78486', '2026-08-15')).toBe(false);
        expect(isDraftValidFor(null, '78486', '2026-08-15')).toBe(false);
    });
});
