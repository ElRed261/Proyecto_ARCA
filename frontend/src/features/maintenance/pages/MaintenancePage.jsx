import React, { useState, useEffect, useCallback } from 'react';
import toast from 'react-hot-toast';
import { useNavigate } from 'react-router-dom';
import { Save, ClipboardCheck, RefreshCw, HardDrive, Cloud, Database, FolderOpen } from 'lucide-react';
import { open as openDialog } from '@tauri-apps/plugin-dialog';

import { pathsService } from '../api/pathsService';
import { hasRole, normalizeRoles } from '../../../shared/utils/auth';

const EMPTY_PROFILE = {
    offline_root: '',
    online_root: '',
    backups_max_age_days: null,
    summaries_dir: null,
};

const PathCard = ({ title, hint, value, onChange, onProbe, onExplore, disabled, probeState }) => {
    const detail = typeof probeState === 'object' ? probeState.detail : null;
    const ok = typeof probeState === 'object' ? probeState.ok : null;
    const probeColor = ok === true ? 'text-green-600' : ok === false ? 'text-red-600' : 'text-gray-400';

    return (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            <div className="flex items-center gap-2 mb-2">
                
                <h3 className="text-sm font-semibold text-gray-800">{title}</h3>
                {!disabled && (
                    <button
                        type="button"
                        onClick={onExplore}
                        className="ml-auto text-xs px-2 py-1 rounded bg-gray-100 hover:bg-gray-200 text-gray-700 flex items-center gap-1"
                    >
                        <FolderOpen className="w-3 h-3" />
                        Explorar
                    </button>
                )}
            </div>
            <p className="text-xs text-gray-400 mb-2">{hint}</p>
            <input
                type="text"
                value={value}
                onChange={(e) => onChange(e.target.value)}
                disabled={disabled}
                placeholder="/ruta/de/guardado"
                className="w-full text-sm font-mono px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400"
            />
            <div className="mt-2 flex items-center justify-between">
                <button
                    type="button"
                    onClick={onProbe}
                    disabled={disabled}
                    className="text-xs px-2 py-1 rounded bg-blue-50 hover:bg-blue-100 text-blue-700 disabled:opacity-40"
                >
                    Probar
                </button>
                {probeState && (
                    <span
                        className={`text-xs ${probeColor}`}
                        data-testid={probeState.ok ? 'probe-ok' : 'probe-error'}
                    >
                        {probeState.ok && '✓ carpeta escribible'}
                        {!probeState.ok && `✗ no escribible${detail ? `: ${detail}` : ''}`}
                    </span>
                )}
            </div>
        </div>
    );
};

/**
 * P4.1 + P4.2 — Configuración real: rutas de guardado (offline / online Drive
 * Desktop / backups / resúmenes) con probe honesto, y panel de estado de la
 * cola de sincronización offline-first. Admin edita; sync visible a todos.
 */
const MaintenancePage = () => {
    const navigate = useNavigate();

    const [loading, setLoading] = useState(true);
    const [profile, setProfile] = useState(EMPTY_PROFILE);
    const [probeStates, setProbeStates] = useState({}); // {ok:boolean, detail?:string}
    const [saveState, setSaveState] = useState(null); // 'ok' | 'error: msg'
    const [sync, setSync] = useState(null);
    const [syncBusy, setSyncBusy] = useState(false);
    const [userRoles] = useState(() => {
        try {
            return normalizeRoles(JSON.parse(localStorage.getItem('user_roles')));
        } catch {
            return [];
        }
    });

    const loadSync = useCallback(async () => {
        try {
            const status = await pathsService.getSyncStatus();
            setSync(status);
        } catch (e) {
            setSync({ pending: 0, synced: 0, last_attempt: null, last_errors: [], load_error: String(e) });
        }
    }, []);

    useEffect(() => {
        let alive = true;
        (async () => {
            try {
                const cfg = await pathsService.getPathConfig();
                if (!alive) return;
                setProfile(cfg || EMPTY_PROFILE);
            } catch {
                if (!alive) return;
                setProfile(EMPTY_PROFILE);
            } finally {
                if (alive) setLoading(false);
            }
            loadSync();
        })();
        return () => {
            alive = false;
        };
    }, [loadSync]);

    const setField = (field, transform = (v) => (v === '' ? null : v)) => (value) =>
        setProfile((p) => ({ ...p, [field]: field === 'offline_root' ? value : transform(value) }));

    const handleProbe = async (field) => {
        const path = profile[field];
        if (!path) {
            toast.error('Elige una ruta primero');
            return;
        }
        try {
            const res = await pathsService.probePath(path);
            const state = res.writable ? { ok: true } : { ok: false, detail: res.error || 'sin detalle' };
            setProbeStates((s) => ({ ...s, [field]: state }));
            if (!res.writable) {
                toast.error(`No escribible: ${state.detail}`);
            }
        } catch (e) {
            setProbeStates((s) => ({ ...s, [field]: { ok: false, detail: String(e) } }));
            toast.error(`Fallo del probe: ${String(e)}`);
        }
    };

    const handleExplore = async (field) => {
        try {
            const picked = await openDialog({ directory: true, multiple: false });
            if (typeof picked === 'string' && picked) {
                setProfile((p) => ({ ...p, [field]: picked }));
                // probe inmediato al explorar (feedback honesto al instante)
                try {
                    const res = await pathsService.probePath(picked);
                    setProbeStates((s) => ({
                        ...s,
                        [field]: res.writable ? { ok: true } : { ok: false, detail: res.error },
                    }));
                } catch (e2) {
                    setProbeStates((s) => ({ ...s, [field]: { ok: false, detail: String(e2) } }));
                }
            }
        } catch {
            toast.error('El selector de carpetas no respondió');
        }
    };

    const handleSave = async () => {
        const normalized = {
            offline_root: profile.offline_root || '',
            online_root: profile.online_root || null,
            backups_max_age_days: profile.backups_max_age_days ?? null,
            summaries_dir: profile.summaries_dir || null,
        };
        try {
            await pathsService.setPathConfig(normalized);
            setSaveState('ok');
            toast.success('Configuración de rutas guardada');
            setProfile(normalized);
        } catch (e) {
            setSaveState(`error: ${String(e)}`);
            toast.error(`No se pudo guardar: ${String(e)}`);
        }
    };

    const handleRetry = async () => {
        setSyncBusy(true);
        try {
            const outcome = await pathsService.retryPendingSync(true);
            if (outcome.marked_synced > 0) {
                toast.success(`Sincronizados: ${outcome.marked_synced}`);
            } else if (outcome.last_error) {
                toast.error(`Sin éxito: ${outcome.last_error}`);
            } else {
                toast('Nada pendiente por reintentar');
            }
            loadSync();
        } catch (e) {
            toast.error(`Fallo del reintento: ${String(e)}`);
        } finally {
            setSyncBusy(false);
        }
    };

    const handleMigrate = async () => {
        try {
            const stats = await pathsService.migrateLegacyMonths();
            toast.success(
                `Migración completa: ${stats.renamed_dirs} carpetas, ${stats.moved_files} archivos`
            );
        } catch (e) {
            toast.error(`No se pudo migrar: ${String(e)}`);
        }
    };

    const canEdit = hasRole(userRoles, ['admin']);

    if (loading) {
        return (
            <div className="min-h-screen bg-gray-50 p-6">
                <div className="max-w-3xl mx-auto p-8 text-sm text-gray-500">Cargando configuración…</div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50">
            <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
                <div>
                    <h1 className="text-lg font-bold text-gray-900">Configuración</h1>
                    <p className="text-xs text-gray-500">
                        Rutas de guardado de la instancia y estado de sincronización
                    </p>
                </div>
                <button
                    onClick={() => navigate('/dashboard')}
                    className="text-sm px-3 py-2 rounded-md bg-gray-100 hover:bg-gray-200 text-gray-700"
                >
                    Volver al Panel
                </button>
            </header>

            <main className="max-w-3xl mx-auto px-4 py-6 space-y-8">
                {/* ---- Rutas (solo admin puede guardar) ---- */}
                <section>
                    <div className="flex items-center justify-between mb-3">
                        <h2 className="text-sm font-bold text-gray-800 uppercase tracking-wide">
                            Rutas de guardado
                        </h2>
                        {canEdit && (
                            <button
                                type="button"
                                onClick={handleSave}
                                className="flex items-center gap-1 text-xs px-3 py-2 rounded-md bg-blue-600 text-white hover:bg-blue-700"
                            >
                                <Save className="w-3 h-3" />
                                Guardar configuración
                            </button>
                        )}
                    </div>

                    <div className="grid gap-4 md:grid-cols-2">
                        <PathCard
                            title="Raíz offline (local)"
                            icon={HardDrive}
                            hint="Carpeta local donde viven las observaciones. Requerida en la práctica."
                            value={profile.offline_root || ''}
                            onChange={setField('offline_root', (v) => v)}
                            onProbe={() => handleProbe('offline_root')}
                            onExplore={() => handleExplore('offline_root')}
                            disabled={!canEdit}
                            probeState={probeStates.offline_root}
                        />
                        <PathCard
                            title="Raíz online (Drive Desktop)"
                            icon={Cloud}
                            hint="Carpeta sincronizada por Google Drive Desktop. Si no está disponible, el dato queda offline y se reintenta."
                            value={profile.online_root || ''}
                            onChange={setField('online_root')}
                            onProbe={() => handleProbe('online_root')}
                            onExplore={() => handleExplore('online_root')}
                            disabled={!canEdit}
                            probeState={probeStates.online_root}
                        />
                        <PathCard
                            title="Carpeta de resúmenes"
                            icon={Database}
                            hint="Opcional: carpeta aparte para Resumen Mensual. Por defecto vive junto a la raíz offline."
                            value={profile.summaries_dir || ''}
                            onChange={setField('summaries_dir')}
                            onProbe={() => handleProbe('summaries_dir')}
                            onExplore={() => handleExplore('summaries_dir')}
                            disabled={!canEdit}
                            probeState={probeStates.summaries_dir}
                        />
                    </div>

                    {saveState && saveState !== 'ok' && (
                        <p className="mt-2 text-xs text-red-600" data-testid="save-error">
                            {saveState}
                        </p>
                    )}
                    {!canEdit && (
                        <p className="mt-2 text-xs text-gray-400">
                            Solo un administrador puede modificar las rutas.
                        </p>
                    )}

                    {canEdit && (
                        <button
                            type="button"
                            onClick={handleMigrate}
                            className="mt-3 text-xs px-3 py-2 rounded-md bg-amber-50 text-amber-700 hover:bg-amber-100"
                        >
                            Migrar carpetas de meses legacy (one-shot)
                        </button>
                    )}
                </section>

                {/* ---- Panel de sincronización (todos los usuarios) ---- */}
                <section>
                    <h2 className="text-sm font-bold text-gray-800 uppercase tracking-wide mb-3">
                        Sincronización
                    </h2>
                    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <p className="text-sm text-gray-700">
                                    Pendientes de enviar:{' '}
                                    <span className="font-bold text-gray-900" data-testid="pendientes">
                                        {sync ? sync.pending : '…'}
                                    </span>
                                    {' · '}
                                    Enviadas con éxito: <strong>{sync ? sync.synced : '…'}</strong>
                                </p>
                                {sync?.load_error && (
                                    <p className="text-xs text-red-600 mt-1">
                                        No se pudo leer el estado: {sync.load_error}
                                    </p>
                                )}
                            </div>
                            <button
                                type="button"
                                onClick={handleRetry}
                                disabled={syncBusy}
                                className="flex items-center gap-1 text-xs px-3 py-2 rounded-md bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
                            >
                                <RefreshCw className="w-3 h-3" />
                                Reintentar ahora
                            </button>
                        </div>

                        {(sync?.last_errors || []).length > 0 && (
                            <ul className="mt-3 space-y-1">
                                {sync.last_errors.slice(0, 5).map((e, i) => (
                                    <li key={i} className="text-xs text-red-600" data-testid="sync-error">
                                        <span className="font-mono">{e.station_code}</span> — {e.relative_path}: {e.detail}
                                    </li>
                                ))}
                            </ul>
                        )}
                        <p className="mt-2 text-xs text-gray-400">
                            Si no hay internet, las observaciones se quedan guardadas offline y se
                            reintentan automáticamente.
                        </p>
                    </div>
                </section>
            </main>
        </div>
    );
};

export default MaintenancePage;
