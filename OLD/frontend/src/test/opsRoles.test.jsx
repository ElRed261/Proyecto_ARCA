import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ensureLocalStorage } from './testStorage';

vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn() }));

import { invoke } from '@tauri-apps/api/core';
import DashboardPage from '../features/dashboard/pages/DashboardPage';

const STATIONS = {
    '78486': { name: 'Jimaní' },
    '78484': { name: 'Río San Juan' },
    '78577': { name: 'Punta Cana' },
};

const setup = (assigned) => {
    invoke.mockReset();
    invoke.mockImplementation((cmd) => {
        if (cmd === 'get_stations') return Promise.resolve(STATIONS);
        if (cmd === 'get_assigned_station') return Promise.resolve(assigned);
        if (cmd === 'get_observation') return Promise.resolve({});
        if (cmd === 'get_sync_status') return Promise.resolve({ pending: 0, synced: 0, last_errors: [] });
        if (cmd === 'audit_browse_days') return Promise.resolve([]);
        return Promise.resolve(null);
    });
};

const renderOps = (roles) =>
    render(
        <MemoryRouter>
            <DashboardPage user={{ email: 'u@arca.rd', roles }} onNavigate={() => {}} />
        </MemoryRouter>
    );

describe('Centro de operaciones — alcance por rol y bloqueo de instancia', () => {
    beforeEach(() => {
        ensureLocalStorage().clear();
    });

    it('admin con instancia bloqueada VE TODAS las estaciones', async () => {
        setup('78486');
        renderOps(['admin']);
        expect(await screen.findByText('Jimaní')).toBeTruthy();
        expect(await screen.findByText('Río San Juan')).toBeTruthy();
        expect(await screen.findByText('Punta Cana')).toBeTruthy();
    });

    it('control_calidad con instancia bloqueada VE TODAS (audita todo el país)', async () => {
        setup('78486');
        renderOps(['control_calidad']);
        expect(await screen.findByText('Jimaní')).toBeTruthy();
        expect(await screen.findByText('Punta Cana')).toBeTruthy();
    });

    it('observador con instancia bloqueada ve SOLO su estación', async () => {
        setup('78486');
        renderOps(['observador']);
        expect(await screen.findByText('Jimaní')).toBeTruthy();
        expect(screen.queryByText('Río San Juan')).toBeNull();
        expect(screen.queryByText('Punta Cana')).toBeNull();
    });

    it('encargado con instancia bloqueada ve SOLO su estación', async () => {
        setup('78486');
        renderOps(['encargado']);
        expect(await screen.findByText('Jimaní')).toBeTruthy();
        expect(screen.queryByText('Río San Juan')).toBeNull();
    });

    it('observador SIN bloqueo ve todas (instancia libre, elige)', async () => {
        setup('');
        renderOps(['observador']);
        expect(await screen.findByText('Jimaní')).toBeTruthy();
        expect(await screen.findByText('Río San Juan')).toBeTruthy();
    });

    it('admin ve el aviso de a qué estación está bloqueada la instancia', async () => {
        setup('78486');
        renderOps(['admin']);
        expect(await screen.findByText(/bloqueada a Jimaní/i)).toBeTruthy();
    });
});
