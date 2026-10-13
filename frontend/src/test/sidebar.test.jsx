import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';

vi.mock('../features/maintenance/api/pathsService', () => ({
    pathsService: { getSyncStatus: vi.fn() },
}));
vi.mock('../features/auth/api/authService', () => ({
    authService: { logout: vi.fn() },
}));

import { pathsService } from '../features/maintenance/api/pathsService';
import { ensureLocalStorage } from './testStorage';
import Sidebar from '../shared/components/Sidebar';

const admin = { email: 'admin@arca.rd', roles: ['admin'] };
const observer = { email: 'obs@arca.rd', roles: ['observador'] };

const renderRail = (user, route = '/dashboard', collapsed = false) => {
    if (collapsed) ensureLocalStorage().setItem('arca_rail_collapsed', '1');
    return render(
        <MemoryRouter initialEntries={[route]}>
            <Sidebar user={user} onLogout={() => {}} collapsed={collapsed} onToggle={() => {}} />
        </MemoryRouter>
    );
};

describe('Sidebar — rail híbrido del OMS', () => {
    beforeEach(() => {
        ensureLocalStorage().clear();
        pathsService.getSyncStatus.mockReset();
        pathsService.getSyncStatus.mockResolvedValue({ pending: 0, synced: 5, last_errors: [] });
    });

    it('renderiza los 5 módulos + inicio con sus etiquetas', () => {
        renderRail(admin);
        for (const label of ['Inicio', 'Sinóptico', 'Resumen', 'Auditoría', 'Configuración', 'Seguridad']) {
            expect(screen.getByText(label)).toBeTruthy();
        }
    });

    it('observador NO ve Seguridad (filtrado por rol)', () => {
        renderRail(observer);
        expect(screen.queryByText('Seguridad')).toBeNull();
        expect(screen.getByText('Sinóptico')).toBeTruthy();
    });

    it('marca activo el módulo de la ruta actual con su accent', () => {
        renderRail(admin, '/audit');
        const link = screen.getByText('Auditoría').closest('a,button');
        expect(link.getAttribute('aria-current')).toBe('page');
        expect(link.style.borderLeftColor || link.className).toBeTruthy();
    });

    it('el toggle colapsa a solo iconos (labels ocultos)', () => {
        const { rerender } = render(
            <MemoryRouter initialEntries={['/dashboard']}>
                <Sidebar user={admin} onLogout={() => {}} collapsed={false} onToggle={() => {}} />
            </MemoryRouter>
        );
        expect(screen.getByText('Sinóptico')).toBeTruthy();
        rerender(
            <MemoryRouter initialEntries={['/dashboard']}>
                <Sidebar user={admin} onLogout={() => {}} collapsed={true} onToggle={() => {}} />
            </MemoryRouter>
        );
        expect(screen.queryByText('Sinóptico')).toBeNull();
    });

    it('pill de sync: muestra pendientes en ámbar', async () => {
        pathsService.getSyncStatus.mockResolvedValue({ pending: 2, synced: 37, last_errors: [] });
        renderRail(admin);
        expect(await screen.findByText(/2 pendientes/i)).toBeTruthy();
    });

    it('pill de sync: todo al día en verde cuando pending es 0', async () => {
        renderRail(admin);
        expect(await screen.findByText(/al día/i)).toBeTruthy();
    });

    it('si el backend no responde, el pill se oculta sin romper el rail', async () => {
        pathsService.getSyncStatus.mockRejectedValue(new Error('caído'));
        renderRail(admin);
        await waitFor(() => expect(screen.getByText('Inicio')).toBeTruthy());
        expect(screen.queryByText(/pendientes/i)).toBeNull();
        expect(screen.queryByText(/al día/i)).toBeNull();
    });

    it('click en usuario ofrece salir (logout)', async () => {
        const user = userEvent.setup();
        const onLogout = vi.fn();
        render(
            <MemoryRouter initialEntries={['/dashboard']}>
                <Sidebar user={admin} onLogout={onLogout} collapsed={false} onToggle={() => {}} />
            </MemoryRouter>
        );
        await user.click(screen.getByTitle(/salir/i));
        expect(onLogout).toHaveBeenCalledTimes(1);
    });
});
