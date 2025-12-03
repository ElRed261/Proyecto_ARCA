import React, { useState, useEffect } from 'react';
import api from '../../../shared/api/axiosConfig';
import { TrendingUp, TrendingDown, DollarSign, Activity, Plus, FileText } from 'lucide-react';
import { Link } from 'react-router-dom';

const StatCard = ({ title, value, icon: Icon, color, subtext }) => (
    <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200">
        <div className="flex justify-between items-start">
            <div>
                <p className="text-sm font-medium text-gray-500">{title}</p>
                <h3 className="text-2xl font-bold text-gray-800 mt-2">{value}</h3>
                {subtext && <p className="text-xs text-gray-400 mt-1">{subtext}</p>}
            </div>
            <div className={`p-3 rounded-lg ${color}`}>
                <Icon size={24} className="text-white" />
            </div>
        </div>
    </div>
);

const AccountingDashboardPage = () => {
    const [stats, setStats] = useState({
        assets: 0,
        liabilities: 0,
        equity: 0,
        recentEntries: []
    });
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchDashboardData();
    }, []);

    const fetchDashboardData = async () => {
        try {
            // En un sistema real, esto sería un endpoint dedicado /dashboard/stats
            // Aquí simulamos calculando desde las cuentas y asientos
            const [accountsRes, entriesRes] = await Promise.all([
                api.get('/accounting/accounts'),
                api.get('/accounting/entries')
            ]);

            // Calcular totales aproximados (Nota: Esto es simplificado, 
            // idealmente el backend debe dar los saldos pre-calculados)
            // Como no tenemos endpoint de saldos masivos, mostraremos 0 por ahora o 
            // implementaremos lógica compleja. Para el MVP, mostraremos contadores.

            const assetsCount = accountsRes.data.filter(a => a.account_type === 'ASSET').length;
            const liabilitiesCount = accountsRes.data.filter(a => a.account_type === 'LIABILITY').length;

            setStats({
                assets: assetsCount,
                liabilities: liabilitiesCount,
                equity: accountsRes.data.filter(a => a.account_type === 'EQUITY').length,
                recentEntries: entriesRes.data.slice(0, 5)
            });

        } catch (error) {
            console.error("Error fetching dashboard:", error);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-8">
            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <StatCard
                    title="Cuentas de Activo"
                    value={stats.assets}
                    icon={TrendingUp}
                    color="bg-green-500"
                    subtext="Cuentas registradas"
                />
                <StatCard
                    title="Cuentas de Pasivo"
                    value={stats.liabilities}
                    icon={TrendingDown}
                    color="bg-red-500"
                    subtext="Obligaciones registradas"
                />
                <StatCard
                    title="Patrimonio"
                    value={stats.equity}
                    icon={DollarSign}
                    color="bg-blue-500"
                    subtext="Cuentas de capital"
                />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Recent Activity */}
                <div className="lg:col-span-2 bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                    <div className="p-6 border-b border-gray-200 flex justify-between items-center">
                        <h3 className="font-bold text-gray-800 flex items-center gap-2">
                            <Activity size={20} className="text-gray-400" />
                            Actividad Reciente
                        </h3>
                        <Link to="/accounting/entries" className="text-sm text-blue-600 hover:text-blue-800 font-medium">
                            Ver todo
                        </Link>
                    </div>
                    <div className="divide-y divide-gray-100">
                        {stats.recentEntries.length === 0 ? (
                            <div className="p-8 text-center text-gray-400">No hay actividad reciente</div>
                        ) : (
                            stats.recentEntries.map(entry => (
                                <div key={entry.id} className="p-4 hover:bg-gray-50 flex justify-between items-center">
                                    <div>
                                        <p className="font-medium text-gray-800">{entry.description}</p>
                                        <p className="text-xs text-gray-500">{entry.date} • {entry.state}</p>
                                    </div>
                                    <span className="font-mono text-sm font-bold text-gray-700">
                                        ${entry.items.reduce((sum, item) => sum + Number(item.debit), 0).toFixed(2)}
                                    </span>
                                </div>
                            ))
                        )}
                    </div>
                </div>

                {/* Quick Actions */}
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                    <h3 className="font-bold text-gray-800 mb-4">Acciones Rápidas</h3>
                    <div className="space-y-3">
                        <Link
                            to="/accounting/entries"
                            className="block w-full py-3 px-4 bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 transition font-medium flex items-center gap-3"
                        >
                            <Plus size={20} /> Nuevo Asiento
                        </Link>
                        <Link
                            to="/accounting/accounts"
                            className="block w-full py-3 px-4 bg-gray-50 text-gray-700 rounded-lg hover:bg-gray-100 transition font-medium flex items-center gap-3"
                        >
                            <FileText size={20} /> Gestionar Cuentas
                        </Link>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default AccountingDashboardPage;
