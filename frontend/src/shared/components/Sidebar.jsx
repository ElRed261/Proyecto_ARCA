import React, { useState, useEffect } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
    LayoutDashboard,
    Activity,
    Calendar,
    ShieldCheck,
    Settings,
    Lock,
    ChevronsLeft,
    ChevronsRight,
    LogOut,
    CloudCheck,
    CloudOff,
} from 'lucide-react';
import { pathsService } from '../../features/maintenance/api/pathsService';
import { hasRole } from '../utils/auth';

const MODULES = [
    { id: 'home', to: '/dashboard', label: 'Inicio', icon: LayoutDashboard, accent: '#3b82f6', roles: null },
    { id: 'synoptic', to: '/synoptic', label: 'Sinóptico', icon: Activity, accent: '#3b82f6', roles: null },
    { id: 'summary', to: '/summary', label: 'Resumen', icon: Calendar, accent: '#a855f7', roles: null },
    { id: 'audit', to: '/audit', label: 'Auditoría', icon: ShieldCheck, accent: '#f97316', roles: ['admin', 'administrador', 'encargado', 'control_calidad'] },
    { id: 'maintenance', to: '/maintenance', label: 'Configuración', icon: Settings, accent: '#0d9488', roles: null },
    { id: 'admin', to: '/admin', label: 'Seguridad', icon: Lock, accent: '#64748b', roles: ['admin', 'administrador'] },
];

/**
 * Sidebar — rail híbrido del OMS (opción elegida por el autor).
 *
 * - 76px iconos ↔ 232px con etiquetas (toggle persistido por el padre).
 * - Indicador activo con el accent del módulo (línea gráfica OMS).
 * - Pill de sincronización abajo (verde al día / ámbar con pendientes).
 * - Filtrado por rol; usuario + salir abajo.
 */
const Sidebar = ({ user, onLogout, collapsed, onToggle }) => {
    const navigate = useNavigate();
    const [sync, setSync] = useState(null);

    useEffect(() => {
        let alive = true;
        pathsService
            .getSyncStatus()
            .then((st) => {
                if (alive) setSync(st);
            })
            .catch(() => {
                if (alive) setSync(null);
            });
        return () => {
            alive = false;
        };
    }, []);

    const visible = MODULES.filter((m) => !m.roles || hasRole(user?.roles, m.roles));
    const pending = sync?.pending ?? 0;

    return (
        <aside
            className={`fixed left-0 top-0 h-screen z-40 bg-white border-r border-slate-200 flex flex-col transition-all duration-300 ${
                collapsed ? 'w-[76px]' : 'w-[76px] lg:w-[232px]'
            }`}
            aria-label="Navegación principal del OMS"
        >
            {/* Marca */}
            <button
                type="button"
                onClick={() => navigate('/dashboard')}
                className="flex items-center gap-2.5 px-4 h-16 border-b border-slate-100 cursor-pointer"
                aria-label="ARCA — ir al inicio"
            >
                <span className="flex-none leading-none" aria-hidden="true">
                    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M12 2L2 7L12 12L22 7L12 2Z" fill="#2563EB" />
                        <path d="M2 17L12 22L22 17" stroke="#2563EB" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                        <path d="M2 12L12 17L22 12" stroke="#60A5FA" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                        <path d="M12 22V12" stroke="#2563EB" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                </span>
                {!collapsed && (
                    <span className="hidden lg:block text-left leading-none">
                        <span className="block font-extrabold text-slate-900 text-[15px]">ARCA</span>
                        <span className="block text-[10px] font-mono text-slate-400 mt-0.5">v2.2.0 OMS</span>
                    </span>
                )}
            </button>

            {/* Módulos */}
            <nav className="flex-1 overflow-y-auto py-3 px-2.5 space-y-1">
                {visible.map((m) => {
                    const Icon = m.icon;
                    return (
                        <NavLink
                            key={m.id}
                            to={m.to}
                            aria-label={m.label}
                            title={collapsed ? m.label : undefined}
                            className={({ isActive }) =>
                                `group flex items-center gap-3 rounded-xl pl-2.5 pr-3 min-h-[44px] transition-all duration-150 border-l-2 ${
                                    isActive
                                        ? 'bg-slate-100 font-semibold text-slate-900'
                                        : 'border-transparent text-slate-500 hover:bg-slate-50 hover:text-slate-800 font-medium'
                                } ${collapsed ? 'justify-center px-0' : ''}`
                            }
                            style={({ isActive }) =>
                                isActive ? { borderLeftColor: m.accent } : undefined
                            }
                        >
                            {({ isActive }) => (
                                <>
                                    <span
                                        className="w-8 h-8 rounded-lg flex items-center justify-center flex-none transition-colors"
                                        style={
                                            isActive
                                                ? { background: m.accent, color: '#fff' }
                                                : { background: `${m.accent}14`, color: m.accent }
                                        }
                                    >
                                        <Icon size={18} />
                                    </span>
                                    {!collapsed && (
                                        <span className="hidden lg:inline text-sm truncate">{m.label}</span>
                                    )}
                                </>
                            )}
                        </NavLink>
                    );
                })}
            </nav>

            {/* Sync pill */}
            {sync && (
                <button
                    type="button"
                    onClick={() => navigate('/maintenance')}
                    title={pending > 0 ? `${pending} observaciones pendientes de envío` : 'Todo sincronizado'}
                    className={`mx-2.5 mb-2 rounded-xl px-3 min-h-[44px] flex items-center gap-2 text-xs font-semibold transition-colors cursor-pointer ${
                        collapsed ? 'justify-center' : ''
                    } ${pending > 0 ? 'bg-amber-50 text-amber-700 hover:bg-amber-100' : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'}`}
                >
                    {pending > 0 ? <CloudOff size={16} /> : <CloudCheck size={16} />}
                    {!collapsed && (
                        <span className="hidden lg:inline truncate">
                            {pending > 0 ? `${pending} pendientes` : 'Al día'}
                        </span>
                    )}
                </button>
            )}

            {/* Usuario + colapsar */}
            <div className="border-t border-slate-100 p-2.5 space-y-1">
                <div
                    className={`flex items-center gap-2.5 px-1 ${collapsed ? 'justify-center' : ''}`}
                    title={user?.email || 'Usuario'}
                >
                    <span className="w-8 h-8 rounded-full bg-blue-600 text-white text-xs font-bold flex items-center justify-center flex-none">
                        {(user?.email || 'U').slice(0, 1).toUpperCase()}
                    </span>
                    {!collapsed && (
                        <span className="hidden lg:block text-xs text-slate-500 truncate flex-1">{user?.email}</span>
                    )}
                </div>
                <div className={`flex gap-1 ${collapsed ? 'flex-col items-center' : ''}`}>
                    <button
                        type="button"
                        onClick={onLogout}
                        title="Salir de la sesión"
                        aria-label="Salir de la sesión"
                        className="flex-1 min-h-[40px] rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50 flex items-center justify-center gap-1.5 text-xs font-semibold cursor-pointer"
                    >
                        <LogOut size={16} />
                        {!collapsed && <span className="hidden lg:inline">Salir</span>}
                    </button>
                    <button
                        type="button"
                        onClick={onToggle}
                        title={collapsed ? 'Expandir menú' : 'Colapsar menú'}
                        aria-label={collapsed ? 'Expandir menú' : 'Colapsar menú'}
                        className="hidden lg:flex min-h-[40px] min-w-[40px] rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 items-center justify-center cursor-pointer"
                    >
                        {collapsed ? <ChevronsRight size={16} /> : <ChevronsLeft size={16} />}
                    </button>
                </div>
            </div>
        </aside>
    );
};

export default Sidebar;
export { MODULES };
