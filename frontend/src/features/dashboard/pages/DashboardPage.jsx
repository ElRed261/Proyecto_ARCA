import React from 'react';
import ModuleCard from '../components/ModuleCard';
import { Users, Package, ShoppingBag, ShieldCheck, PieChart, Settings } from 'lucide-react';

import UserMenu from '../../../shared/components/UserMenu';

const DashboardPage = ({ user, onLogout, onNavigate }) => {

    const modules = [
        {
            id: 'hrm',
            title: 'Recursos Humanos',
            description: 'Gestión de empleados, nómina, contratos y control de asistencia del personal.',
            icon: Users,
            color: 'bg-blue-500 text-blue-600',
            status: 'active'
        },
        {
            id: 'scm',
            title: 'Inventario & SCM',
            description: 'Control de stock, almacenes, proveedores y cadena de suministro.',
            icon: Package,
            color: 'bg-purple-500 text-purple-600',
            status: 'active'
        },
        {
            id: 'crm',
            title: 'Ventas & CRM',
            description: 'Gestión de clientes, oportunidades de venta, pedidos y facturación.',
            icon: ShoppingBag,
            color: 'bg-green-500 text-green-600',
            status: 'active'
        },
        {
            id: 'accounting',
            title: 'Contabilidad',
            description: 'Libro mayor, reportes financieros e impuestos (Próximamente).',
            icon: PieChart,
            color: 'bg-red-500 text-red-600',
            status: 'active'
        },
        {
            id: 'admin',
            title: 'Seguridad & Admin',
            description: 'Gestión de usuarios, roles, permisos y auditoría del sistema.',
            icon: ShieldCheck,
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
                    <div className="bg-blue-600 p-2 rounded-lg">
                        <Settings className="text-white" size={20} />
                    </div>
                    <div>
                        <h1 className="text-xl font-bold text-gray-800 tracking-tight">Proyecto ARCA</h1>
                        <p className="text-xs text-gray-400 font-mono">v1.0.0 Enterprise Edition</p>
                    </div>
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