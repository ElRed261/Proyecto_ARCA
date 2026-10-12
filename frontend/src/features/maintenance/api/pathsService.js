import { invoke } from '@tauri-apps/api/core';

const token = () => localStorage.getItem('token') || '';

/**
 * Configuración central de rutas (P4) — backend: infrastructure/storage/
 * paths_config.rs + sync_queue.rs. Comandos:
 *  - get_path_config / set_path_config / probe_path (admin para set/probe)
 *  - get_sync_status (autenticado) / retry_pending_sync (admin|encargado)
 *  - audit_migrate_legacy_months (admin, one-shot idempotente)
 */
export const pathsService = {
    getPathConfig: () => invoke('get_path_config', { token: token() }),

    setPathConfig: (profile) => invoke('set_path_config', { token: token(), profile }),

    probePath: (path) => invoke('probe_path', { token: token(), path }),

    getSyncStatus: () => invoke('get_sync_status', { token: token() }),

    retryPendingSync: (force = true) =>
        invoke('retry_pending_sync', { token: token(), force }),

    migrateLegacyMonths: () => invoke('audit_migrate_legacy_months', { token: token() }),
};
