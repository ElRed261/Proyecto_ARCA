import React, { useState, useEffect, useCallback } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { ArrowRight, CloudOff, CloudCheck, CalendarDays, Lock } from 'lucide-react';
import { hasRole } from '../../../shared/utils/auth';

const HOURS = ['00Z', '03Z', '06Z', '09Z', '12Z', '15Z', '18Z', '21Z'];

const todayLocal = () => {
    const d = new Date();
    const p = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};

const hourDone = (h) => {
    if (!h || typeof h !== 'object') return false;
    return ['ts', 'th', 'pres_est'].some((k) => h[k] !== undefined && h[k] !== null && String(h[k]).trim() !== '');
};

/**
 * Inicio — centro de operaciones del día (el rail es la navegación;
 * aquí no se duplican los módulos: se muestra el ESTADO accionable).
 */
const DashboardPage = ({ user, onNavigate }) => {
    const [loading, setLoading] = useState(true);
    const [stations, setStations] = useState({});
    const [today, setToday] = useState({});
    const [monthDays, setMonthDays] = useState({});
    const [sync, setSync] = useState(null);
    const [assigned, setAssigned] = useState('');

    const fecha = todayLocal();
    const [year, month] = fecha.split('-').slice(0, 2);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const st = (await invoke('get_stations')) || {};
            setStations(st);
            try {
                const lock = await invoke('get_assigned_station');
                if (lock) setAssigned(lock);
            } catch {
                setAssigned('');
            }
            const codes = Object.keys(st);
            const [obs, days, syncStatus] = await Promise.all([
                Promise.all(
                    codes.map((code) =>
                        invoke('get_observation', { stationCode: code, fecha })
                            .then((o) => [code, o || {}])
                            .catch(() => [code, {}])
                    )
                ).then((pairs) => Object.fromEntries(pairs)),
                Promise.all(
                    codes.map((code) =>
                        invoke('audit_browse_days', { station: code, year, month })
                            .then((d) => [code, Array.isArray(d) ? d.length : 0])
                            .catch(() => [code, 0])
                    )
                ).then((pairs) => Object.fromEntries(pairs)),
                invoke('get_sync_status').catch(() => null),
            ]);
            setToday(obs);
            setMonthDays(days);
            setSync(syncStatus);
        } catch {
            setStations({});
        } finally {
            setLoading(false);
        }
    }, [fecha, year, month]);

    useEffect(() => {
        load();
    }, [load]);

    // Alcance por rol + bloqueo de instancia (misma regla que el Sinóptico):
    // la instancia bloqueada limita a observador/encargado a SU estación;
    // admin y control_calidad ven todo el país.
    const privileged = hasRole(user?.roles, ['admin', 'administrador', 'control_calidad']);
    const allCodes = Object.keys(stations);
    const codes = assigned && !privileged ? allCodes.filter((c) => c === assigned) : allCodes;
    const lockedName = assigned ? stations[assigned]?.name || assigned : '';
    const pending = sync?.pending ?? 0;

    return (
        <div className="min-h-screen bg-gray-50">
            <main className="max-w-6xl mx-auto px-6 lg:px-10 py-8">
                <div className="mb-6">
                    <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">
                        {fecha.split('-').reverse().join('/')}
                    </p>
                    <h2 className="text-3xl font-bold text-gray-900">Centro de operaciones</h2>
                    <p className="text-gray-500 mt-1">Estado de hoy por estación. El rail a la izquierda es la navegación.</p>
                    {assigned && privileged && (
                        <p className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-3 py-1">
                            <Lock size={12} />
                            Instancia bloqueada a {lockedName} ({assigned})
                        </p>
                    )}
                    {assigned && !privileged && stations[assigned] && (
                        <p className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 bg-slate-100 border border-slate-200 rounded-full px-3 py-1">
                            <Lock size={12} />
                            Tu estación: {stations[assigned].name}
                        </p>
                    )}
                </div>

                {loading ? (
                    <p className="text-sm text-gray-500">Cargando estado del día…</p>
                ) : codes.length === 0 ? (
                    <p className="text-sm text-gray-500">Sin estaciones configuradas.</p>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                        {codes.map((code) => {
                            const obs = today[code] || {};
                            const done = HOURS.filter((h) => hourDone(obs[h])).length;
                            const name = stations[code]?.name || code;
                            return (
                                <div key={code} className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
                                    <div className="flex items-center justify-between mb-3">
                                        <div>
                                            <h3 className="text-lg font-bold text-slate-900">{name}</h3>
                                            <p className="text-xs text-slate-400 font-mono">{code}</p>
                                        </div>
                                        <span className={`text-sm font-bold ${done === 8 ? 'text-emerald-600' : 'text-slate-700'}`}>
                                            {done}/8
                                        </span>
                                    </div>
                                    <div className="flex gap-1.5 mb-3" aria-label={`${done} de 8 horas completadas`}>
                                        {HOURS.map((h) => (
                                            <span
                                                key={h}
                                                title={`${h}: ${hourDone(obs[h]) ? 'completa' : 'pendiente'}`}
                                                className={`h-2 flex-1 rounded-full ${hourDone(obs[h]) ? 'bg-blue-500' : 'bg-slate-200'}`}
                                            />
                                        ))}
                                    </div>
                                    <div className="flex items-center justify-between">
                                        <span className="text-xs text-slate-500 flex items-center gap-1">
                                            <CalendarDays size={14} />
                                            {(monthDays[code] ?? 0)} días con datos este mes
                                        </span>
                                        <button
                                            type="button"
                                            onClick={() => onNavigate('synoptic')}
                                            className="flex items-center gap-1 text-sm font-bold text-blue-600 hover:text-blue-800 cursor-pointer"
                                        >
                                            Continuar <ArrowRight size={16} />
                                        </button>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}

                <div className="mt-5 bg-white rounded-2xl border border-slate-200 p-5 shadow-sm flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                        {pending > 0 ? (
                            <CloudOff size={22} className="text-amber-600" />
                        ) : (
                            <CloudCheck size={22} className="text-emerald-600" />
                        )}
                        <div>
                            <p className="text-sm font-bold text-slate-900">
                                {pending > 0 ? `${pending} pendientes de envío` : 'Sincronización al día'}
                            </p>
                            <p className="text-xs text-slate-500">
                                {sync ? `${sync.synced ?? 0} enviadas con éxito` : 'Estado no disponible'}
                            </p>
                        </div>
                    </div>
                    <button
                        type="button"
                        onClick={() => onNavigate('maintenance')}
                        className="text-sm font-bold text-teal-700 hover:text-teal-900 cursor-pointer flex items-center gap-1"
                    >
                        Ver sincronización <ArrowRight size={16} />
                    </button>
                </div>
            </main>
        </div>
    );
};

export default DashboardPage;
