import { describe, it, expect, vi, beforeEach } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('@tauri-apps/api/core', () => ({ invoke: vi.fn() }));
vi.mock('@tauri-apps/plugin-dialog', () => ({ open: vi.fn() }));

import { invoke } from '@tauri-apps/api/core';
import { open } from '@tauri-apps/plugin-dialog';
import { ensureLocalStorage } from './testStorage';
import MaintenancePage from '../features/maintenance/pages/MaintenancePage';

const renderPage = () =>
  render(
    <MemoryRouter>
      <MaintenancePage />
    </MemoryRouter>
  );

const CONFIG = {
  offline_root: '/datos/ARCA',
  online_root: '/drive/ARCA',
  backups_max_age_days: 30,
  summaries_dir: null,
};

const SYNC = {
  pending: 2,
  synced: 12,
  last_attempt: null,
  last_errors: [{ station_code: '78486', relative_path: 'synop/78486/x.json', detail: 'dir online caído' }],
};

describe('Configuración de rutas y sincronización (P4.1 + P4.2)', () => {
  beforeEach(() => {
    const ls = ensureLocalStorage();
    ls.clear();
    ls.setItem('token', 't');
    ls.setItem('user_roles', JSON.stringify(['admin']));
    invoke.mockReset();
    open.mockReset?.();
    invoke.mockImplementation((cmd) => {
      if (cmd === 'get_path_config') return Promise.resolve(CONFIG);
      if (cmd === 'get_sync_status') return Promise.resolve(SYNC);
      return Promise.resolve({});
    });
  });

  it('renderiza la ruta offline y online configuradas', async () => {
    renderPage();
    expect(await screen.findByDisplayValue('/datos/ARCA')).toBeTruthy();
    expect(await screen.findByDisplayValue('/drive/ARCA')).toBeTruthy();
  });

  it('Probar llama probe_path y muestra el error real del backend', async () => {
    invoke.mockImplementation((cmd) => {
      if (cmd === 'get_path_config') return Promise.resolve(CONFIG);
      if (cmd === 'get_sync_status') return Promise.resolve(SYNC);
      if (cmd === 'probe_path') return Promise.resolve({ writable: false, error: 'raíz online caída' });
      return Promise.resolve({});
    });
    renderPage();
    const probarButtons = await screen.findAllByRole('button', { name: /probar/i });
    fireEvent.click(probarButtons[0]);
    expect(await screen.findByText(/raíz online caída/)).toBeTruthy();
  });

  it('Probar OK muestra confirmación de escritura', async () => {
    invoke.mockImplementation((cmd) => {
      if (cmd === 'get_path_config') return Promise.resolve(CONFIG);
      if (cmd === 'get_sync_status') return Promise.resolve(SYNC);
      if (cmd === 'probe_path') return Promise.resolve({ writable: true, error: null });
      return Promise.resolve({});
    });
    renderPage();
    const probarButtons = await screen.findAllByRole('button', { name: /probar/i });
    fireEvent.click(probarButtons[0]);
    expect(await screen.findByText(/escribible/i)).toBeTruthy();
  });

  it('Explorar abre el selector de carpetas y pone la ruta en el campo', async () => {
    open.mockResolvedValue('/nueva/carpeta');
    renderPage();
    const explorarButtons = await screen.findAllByRole('button', { name: /explorar/i });
    fireEvent.click(explorarButtons[0]);
    expect(await screen.findByDisplayValue('/nueva/carpeta')).toBeTruthy();
  });

  it('Guardar llama set_path_config con el perfil completo', async () => {
    renderPage();
    await screen.findByDisplayValue('/datos/ARCA');
    fireEvent.click(screen.getByRole('button', { name: /guardar configuración/i }));
    await waitFor(() => {
      const call = invoke.mock.calls.find(([cmd]) => cmd === 'set_path_config');
      expect(call).toBeTruthy();
      expect(call[1]).toEqual({
        token: 't',
        profile: {
          offline_root: '/datos/ARCA',
          online_root: '/drive/ARCA',
          backups_max_age_days: 30,
          summaries_dir: null,
        },
      });
    });
  });

  it('panel de sync muestra pendientes y Reintentar llama retry_pending_sync con force', async () => {
    renderPage();
    const badge = await screen.findByTestId('pendientes');
    expect(badge.textContent).toBe('2');
    const retryButton = await screen.findByRole('button', { name: /reintentar/i });
    invoke.mockImplementation((cmd) => {
      if (cmd === 'retry_pending_sync') return Promise.resolve({ attempted: 2, uploaded: 1, marked_synced: 2 });
      return Promise.resolve({});
    });
    fireEvent.click(retryButton);
    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith('retry_pending_sync', { token: 't', force: true });
    });
  });

  it('sin rol admin los campos quedan deshabilitados y no guarda', async () => {
    ensureLocalStorage().setItem('user_roles', JSON.stringify(['observador']));
    renderPage();
    const offlineInput = await screen.findByDisplayValue('/datos/ARCA');
    expect(offlineInput).toBeDisabled();
    expect(screen.queryByRole('button', { name: /guardar configuración/i })).toBeNull();
    // el panel de sync sigue visible para cualquier usuario autenticado
    expect(await screen.findByRole('button', { name: /reintentar/i })).toBeTruthy();
  });
});
