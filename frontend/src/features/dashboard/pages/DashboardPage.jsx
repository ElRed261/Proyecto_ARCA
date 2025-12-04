import React from 'react';
import ModuleCard from '../components/ModuleCard';
import { Activity, Calendar, ShieldCheck, Settings } from 'lucide-react';

import UserMenu from '../../../shared/components/UserMenu';

import Logo from '../../../shared/components/Logo';

const DashboardPage = ({ user, onLogout, onNavigate }) => {

    const modules = [
        {
            id: 'synoptic',
            title: 'Observación Sinóptica',
            description: 'Monitoreo en tiempo real y logs del sistema (CLI).',
            icon: Activity,
            color: 'bg-blue-500 text-blue-600',
            status: 'active'
        },
        {
            id: 'summary',
            title: 'Resumen Mensual',
            description: 'Reportes financieros y operativos mensuales.',
            icon: Calendar,
            color: 'bg-purple-500 text-purple-600',
            status: 'active'
        },
        {
            id: 'audit',
            title: 'Correcciones y Auditoría',
            description: 'Registro de cambios y solicitudes de corrección.',
            icon: ShieldCheck,
            color: 'bg-orange-500 text-orange-600',
            status: 'active'
        },
        {
            id: 'admin',
            title: 'Seguridad & Admin',
            description: 'Gestión de usuarios, roles y permisos.',
            icon: Settings,
            color: 'bg-gray-600 text-gray-700',
            status: 'active'
        },
    ];

    // Filtrar módulos según rol
    const isAdmin = user.roles && user.roles.some(r => ['admin', 'administrador'].includes(r.toLowerCase()));

    const visibleModules = modules.filter(mod => {
        if (mod.id === 'admin') return isAdmin;
        return true;
    });

    return (
        <div className="min-h-screen bg-gray-50">
            {/* Barra Superior */}
            <nav className="bg-white shadow-sm border-b border-gray-200 px-8 py-4 flex justify-between items-center sticky top-0 z-30">
                <div className="flex items-center gap-3">
                    <Logo variant="medium" />
                    <div className="h-6 w-px bg-gray-300 mx-2"></div>
                    <p className="text-xs text-gray-400 font-mono mt-1">v2.0.0 Enterprise</p>
                </div>

                <UserMenu user={user} onLogout={onLogout} />
            </nav>

            {/* Contenido Principal (Mosaicos) */}
            <main className="max-w-7xl mx-auto px-8 py-12 pb-64">
                <div className="mb-10">
                    <h2 className="text-3xl font-bold text-gray-900">Panel de Control</h2>
                    <p className="text-gray-500 mt-2">Seleccione un módulo para comenzar a trabajar.</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                    {visibleModules.map((mod) => (
                        <ModuleCard
                            key={mod.id}
                            {...mod}
                            onClick={() => onNavigate(mod.id)}
                        />
                    ))}
                </div>
            </main>
        </div>
    );
};

export default DashboardPage;