import { describe, test, expect, vi, beforeEach } from 'vitest';

// mock del módulo core de Tauri ANTES de importar el service
vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(),
}));

import { invoke } from '@tauri-apps/api/core';
import { ensureLocalStorage } from './testStorage';
import { pathsService } from '../features/maintenance/api/pathsService';

describe('pathsService — contrato directo con los comandos de rutas/sync', () => {
  beforeEach(() => {
    ensureLocalStorage().setItem('token', 'token-de-prueba');
    invoke.mockClear();
  });

  test('getPathConfig llama get_path_config con el token de sesión', async () => {
    invoke.mockResolvedValue(null);
    await pathsService.getPathConfig();
    expect(invoke).toHaveBeenCalledWith('get_path_config', { token: 'token-de-prueba' });
  });

  test('setPathConfig envía el perfil construido por la UI', async () => {
    invoke.mockResolvedValue(undefined);
    const profile = { offline_root: '/datos/arca', online_root: '/drive/arca', backups_max_age_days: 30, summaries_dir: null };
    await pathsService.setPathConfig(profile);
    expect(invoke).toHaveBeenCalledWith('set_path_config', {
      token: 'token-de-prueba',
      profile,
    });
  });

  test('probePath manda la ruta a comprobar', async () => {
    invoke.mockResolvedValue({ writable: true, error: null });
    await pathsService.probePath('/una/ruta');
    expect(invoke).toHaveBeenCalledWith('probe_path', { token: 'token-de-prueba', path: '/una/ruta' });
  });

  test('getSyncStatus pide el estado de la cola', async () => {
    invoke.mockResolvedValue({ pending: 0, synced: 0, last_attempt: null, last_errors: [] });
    await pathsService.getSyncStatus();
    expect(invoke).toHaveBeenCalledWith('get_sync_status', { token: 'token-de-prueba' });
  });

  test('retryPendingSync pide reintento forzado (botón manual)', async () => {
    invoke.mockResolvedValue({ attempted: 0, uploaded: 0, marked_synced: 0 });
    await pathsService.retryPendingSync(true);
    expect(invoke).toHaveBeenCalledWith('retry_pending_sync', {
      token: 'token-de-prueba',
      force: true,
    });
  });

  test('migrateLegacyMonths llama al comando one-shot de migración', async () => {
    invoke.mockResolvedValue({ renamed_dirs: 2, moved_files: 7 });
    await pathsService.migrateLegacyMonths();
    expect(invoke).toHaveBeenCalledWith('audit_migrate_legacy_months', { token: 'token-de-prueba' });
  });
});
