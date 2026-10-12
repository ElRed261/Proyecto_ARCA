import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, useNavigate } from 'react-router-dom';

// mock de useNavigate sin tocar el router real
vi.mock('react-router-dom', async () => {
    const actual = await vi.importActual('react-router-dom');
    return { ...actual, useNavigate: vi.fn() };
});

import BackButton from '../shared/components/BackButton';

describe('BackButton — icono solo, color del módulo, esquina superior izquierda', () => {
    it('NO renderiza texto: solo icono de flecha con aria-label', () => {
        render(
            <MemoryRouter>
                <BackButton to="/dashboard" label="Volver al Panel" />
            </MemoryRouter>
        );
        expect(screen.queryByText(/volver/i)).toBeNull();
        const btn = screen.getByRole('button');
        expect(btn.getAttribute('aria-label')).toBe('Volver al Panel');
    });

    it('usa el color principal del módulo (accent)', () => {
        render(
            <MemoryRouter>
                <BackButton to="/dashboard" accent="#f97316" />
            </MemoryRouter>
        );
        const btn = screen.getByRole('button');
        expect(btn.style.color).toBe('rgb(249, 115, 22)');
        expect(btn.style.borderColor).toContain('249, 115, 22');
    });

    it('target táctil de 44px', () => {
        render(
            <MemoryRouter>
                <BackButton to="/dashboard" />
            </MemoryRouter>
        );
        expect(screen.getByRole('button').className).toContain('min-h-[44px]');
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
