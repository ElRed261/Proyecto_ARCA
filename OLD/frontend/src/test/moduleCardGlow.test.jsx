import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ModuleCard from '../features/dashboard/components/ModuleCard';

describe('ModuleCard — glow por color del módulo al hover (Synoptic azul, correcciones naranja…)', () => {
    const renderCard = (accent) =>
        render(
            <ModuleCard
                title="Observación Sinóptica"
                description="x"
                icon={() => null}
                accent={accent}
                onClick={() => {}}
            />
        );

    it('sin hover: sin glow', () => {
        renderCard('#3b82f6');
        const card = screen.getByRole('button');
        expect(card.style.boxShadow).toBe('');
    });

    it('con hover: boxShadow color del módulo (azul para Synoptic)', () => {
        renderCard('#3b82f6');
        const card = screen.getByRole('button');
        fireEvent.mouseEnter(card);
        expect(card.style.boxShadow).toContain('#3b82f6');
    });

    it('cada módulo brilla con SU color (correcciones = naranja)', () => {
        renderCard('#f97316');
        const card = screen.getByRole('button');
        fireEvent.mouseEnter(card);
        expect(card.style.boxShadow).toContain('#f97316');
    });

    it('al salir del hover el glow desaparece', () => {
        renderCard('#0d9488');
        const card = screen.getByRole('button');
        fireEvent.mouseEnter(card);
        fireEvent.mouseLeave(card);
        expect(card.style.boxShadow).toBe('');
    });
});
