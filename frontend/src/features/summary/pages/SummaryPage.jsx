import React, { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/core';

const SummaryPage = () => {
    const [summaries, setSummaries] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchSummaries();
    }, []);

    const fetchSummaries = async () => {
        try {
            const data = await invoke('get_monthly_summaries', { skip: 0, limit: 12 });
            setSummaries(data);
        } catch (error) {
            console.error("Error fetching summaries:", error);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="p-6">
            <h1 className="text-2xl font-bold mb-4">Resumen Mensual</h1>
            <div className="bg-white shadow rounded-lg p-4">
                <h2 className="text-xl font-semibold mb-2">Histórico de Resúmenes</h2>
                {loading ? (
                    <p>Cargando...</p>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {summaries.map((summary) => (
                            <div key={summary.id} className="border rounded-lg p-4 hover:shadow-md transition-shadow">
                                <h3 className="text-lg font-bold text-gray-800">
                                    {new Date(0, summary.month - 1).toLocaleString('es-ES', { month: 'long' })} {summary.year}
                                </h3>
                                <div className="mt-2 space-y-1">
                                    <div className="flex justify-between">
                                        <span className="text-gray-600">Ingresos:</span>
                                        <span className="text-green-600 font-semibold">${summary.total_revenue.toFixed(2)}</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-gray-600">Gastos:</span>
                                        <span className="text-red-600 font-semibold">${summary.total_expenses.toFixed(2)}</span>
                                    </div>
                                    <div className="border-t pt-1 mt-1 flex justify-between">
                                        <span className="font-bold">Neto:</span>
                                        <span className={`font-bold ${summary.net_profit >= 0 ? 'text-blue-600' : 'text-red-600'}`}>
                                            ${summary.net_profit.toFixed(2)}
                                        </span>
                                    </div>
                                </div>
                                <p className="text-xs text-gray-400 mt-3 text-right">
                                    Generado: {new Date(summary.generated_at).toLocaleDateString()}
                                </p>
                            </div>
                        ))}
                        {summaries.length === 0 && (
                            <p className="text-gray-500 col-span-full text-center py-4">No hay resúmenes disponibles.</p>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};

export default SummaryPage;
