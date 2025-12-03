import React from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import { LayoutDashboard, BookOpen, FileText, PieChart, Calendar, Layers } from 'lucide-react';

import UserMenu from '../../../shared/components/UserMenu';

import Logo from '../../../shared/components/Logo';

const AccountingLayout = ({ user, onLogout }) => {
    const location = useLocation();

    const isActive = (path) => location.pathname === path;

    const navItems = [
        { path: '/accounting', label: 'Dashboard', icon: LayoutDashboard },
        { path: '/accounting/accounts', label: 'Plan de Cuentas', icon: BookOpen },
        { path: '/accounting/entries', label: 'Libro Diario', icon: FileText },
        { path: '/accounting/ledger', label: 'Libro Mayor', icon: BookOpen },
        { path: '/accounting/periods', label: 'Periodos Fiscales', icon: Calendar },
        { path: '/accounting/cost-centers', label: 'Centros de Costos', icon: Layers },
        { path: '/accounting/reports', label: 'Reportes', icon: PieChart },
    ];

    return (
        <div className="flex h-screen bg-gray-100">
            {/* Sidebar */}
            <div className="w-64 bg-white border-r border-gray-200 flex flex-col">
                <div className="p-6 border-b border-gray-200">
                    <div className="mb-4">
                        <Logo variant="medium" />
                    </div>
                    <div className="flex items-center gap-2 text-red-600 font-semibold text-sm">
                        <PieChart size={16} />
                        <span>Contabilidad</span>
                    </div>
                </div>

                <nav className="flex-1 p-4 space-y-1">
                    {navItems.map((item) => (
                        <Link
                            key={item.path}
                            to={item.path}
                            className={`flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors ${isActive(item.path)
                                ? 'bg-red-50 text-red-700'
                                : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                                }`}
                        >
                            <item.icon size={20} />
                            {item.label}
                        </Link>
                    ))}
                </nav>

                <div className="p-4 border-t border-gray-200">
                    <Link to="/dashboard" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700">
                        <span>←</span> Volver al Sistema
                    </Link>
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 overflow-auto">
                <header className="bg-white border-b border-gray-200 px-8 py-4 flex justify-between items-center">
                    <h1 className="text-2xl font-bold text-gray-800">
                        {navItems.find(i => isActive(i.path))?.label || 'Contabilidad'}
                    </h1>
                    <UserMenu user={user} onLogout={onLogout} />
                </header>
                <main className="p-8">
                    <Outlet />
                </main>
            </div>
        </div>
    );
};

export default AccountingLayout;
