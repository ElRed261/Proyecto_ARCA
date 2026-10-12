/* eslint-disable no-import-assign, no-toggle */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import { createRef } from 'react';

// mock de useNavigate sin tocar el router real
vi.mock('react-router-dom', async () => {
    const actual = await vi.importActual('react-router-dom');
    return { ...actual, useNavigate: vi.fn() };
});

import BackButton from '../shared/components/BackButton';

describe('BackButton — botón de volver consistente (icono + texto + a11y)', () => {
    it('siempre muestra el texto "Volver" junto a la flecha (no flecha sola)', () => {
        render(
            <MemoryRouter>
                <BackButton to="/dashboard" />
            </MemoryRouter>
        );
        expect(screen.getByText(/volver/i)).toBeTruthy();
    });

    it('tiene aria-label accesible y target táctil de 44px', () => {
        render(
            <MemoryRouter>
                <BackButton to="/dashboard" label="Volver al Panel" />
            </MemoryRouter>
        );
        const btn = screen.getByRole('button');
        expect(btn.getAttribute('aria-label')).toBe('Volver al Panel');
        const style = getComputedStyle(btn) || btn.currentStyle;
        // min-height 44px vía clase tailwind (min-h-[44px])
        expect(btn.className).toContain('min-h-[44px]');
        void style;
    });

    it('navega a la ruta `to` al hacer click', () => {
        const navigate = vi.fn();
        useNavigate.mockReturnValue(navigate);
        render(
            <MemoryRouter>
                <BackButton to="/dashboard" />
            </MemoryRouter>
        );
        fireEvent.click(screen.getByRole('button'));
        expect(navigate).toHaveBeenCalledWith('/dashboard');
    });

    it('usa el onClick custom si viene (fallback de página)', () => {
        const onBack = vi.fn();
        render(
            <MemoryRouter>
                <BackButton onBack={onBack} />
            </MemoryRouter>
        );
        fireEvent.click(screen.getByRole('button'));
        expect(onBack).toHaveBeenCalledTimes(1);
    });
});
