import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ensureLocalStorage } from './testStorage';

vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn() }));

import { invoke } from '@tauri-apps/api/core';
import DashboardPage from '../features/dashboard/pages/DashboardPage';

const STATIONS = { '78486': { name: 'Jimaní' }, '78484': { name: 'Río San Juan' } };
const fullDay = () => {
    const o = {};
    for (const h of ['00Z', '03Z', '06Z', '09Z', '12Z', '15Z', '18Z', '21Z']) {
        o[h] = { ts: '28.0', pres_est: '1012.0' };
    }
    return o;
};

describe('Inicio — centro de operaciones del día (sin módulos duplicados)', () => {
    beforeEach(() => {
        ensureLocalStorage().clear();
        invoke.mockReset();
        invoke.mockImplementation((cmd) => {
            if (cmd === 'get_stations') return Promise.resolve(STATIONS);
            if (cmd === 'get_observation') return Promise.resolve(fullDay());
            if (cmd === 'get_sync_status') return Promise.resolve({ pending: 2, synced: 10, last_errors: [] });
            if (cmd === 'audit_browse_days') return Promise.resolve([{ fecha: '2026-08-01' }, { fecha: '2026-08-02' }]);
            return Promise.resolve(null);
        });
    });

    it('NO renderiza las tarjetas de módulos (viven en el rail)', () => {
        render(
            <MemoryRouter>
                <DashboardPage user={{ email: 'a@b.c', roles: ['admin'] }} onNavigate={() => {}} />
            </MemoryRouter>
        );
        expect(screen.queryByText('Observación Sinóptica')).toBeNull();
        expect(screen.queryByText('Acceder al Módulo')).toBeNull();
    });

    it('muestra el estado de hoy por estación con horas completadas', async () => {
        render(
            <MemoryRouter>
                <DashboardPage user={{ email: 'a@b.c', roles: ['admin'] }} onNavigate={() => {}} />
            </MemoryRouter>
        );
        expect(await screen.findByText('Jimaní')).toBeTruthy();
        expect(await screen.findByText('Río San Juan')).toBeTruthy();
        const done = await screen.findAllByText('8/8');
        expect(done.length).toBe(2);
    });

    it('botón Continuar navega al sinóptico', async () => {
        const onNavigate = vi.fn();
        render(
            <MemoryRouter>
                <DashboardPage user={{ email: 'a@b.c', roles: ['admin'] }} onNavigate={onNavigate} />
            </MemoryRouter>
        );
        const btns = await screen.findAllByRole('button', { name: /continuar/i });
        fireEvent.click(btns[0]);
        expect(onNavigate).toHaveBeenCalledWith('synoptic');
    });

    it('panel de sincronización con pendientes y link a configuración', async () => {
        const onNavigate = vi.fn();
        render(
            <MemoryRouter>
                <DashboardPage user={{ email: 'a@b.c', roles: ['admin'] }} onNavigate={onNavigate} />
            </MemoryRouter>
        );
        expect(await screen.findByText(/2 pendientes/i)).toBeTruthy();
        fireEvent.click(screen.getByRole('button', { name: /ver sincronización/i }));
        expect(onNavigate).toHaveBeenCalledWith('maintenance');
    });

    it('días con datos del mes por estación', async () => {
        render(
            <MemoryRouter>
                <DashboardPage user={{ email: 'a@b.c', roles: ['admin'] }} onNavigate={() => {}} />
            </MemoryRouter>
        );
        const dias = await screen.findAllByText(/2 días/i);
        expect(dias.length).toBe(2);
    });
});
