import React, { useState, useEffect } from 'react';
import api from '../../../shared/api/axiosConfig';
import { FileText, Download, Printer } from 'lucide-react';
import * as XLSX from 'xlsx';

const ReportsPage = () => {
    const [reportData, setReportData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState('trial-balance');

    useEffect(() => {
        if (activeTab === 'trial-balance') {
            fetchTrialBalance();
        } else if (activeTab === 'income-statement') {
            fetchIncomeStatement();
        } else if (activeTab === 'balance-sheet') {
            fetchBalanceSheet();
        }
    }, [activeTab]);

    const fetchTrialBalance = async () => {
        setLoading(true);
        try {
            const response = await api.get('/accounting/reports/trial-balance');
            setReportData(response.data);
        } catch (error) {
            console.error("Error fetching report:", error);
        } finally {
            setLoading(false);
        }
    };

    const fetchIncomeStatement = async () => {
        setLoading(true);
        try {
            const response = await api.get('/accounting/reports/income-statement');
            setReportData(response.data);
        } catch (error) {
            console.error("Error fetching report:", error);
        } finally {
            setLoading(false);
        }
    };

    const fetchBalanceSheet = async () => {
        setLoading(true);
        try {
            const response = await api.get('/accounting/reports/balance-sheet');
            setReportData(response.data);
        } catch (error) {
            console.error("Error fetching report:", error);
        } finally {
            setLoading(false);
        }
    };

    const handlePrint = () => {
        window.print();
    };

    const handleExportExcel = () => {
        let wb = XLSX.utils.book_new();
        let ws;

        if (activeTab === 'trial-balance') {
            ws = XLSX.utils.json_to_sheet(reportData);
        } else if (activeTab === 'income-statement') {
            // Flatten data for export
            let data = [];
            data.push({ A: "Ingresos Operativos" });
            reportData.revenues.forEach(r => data.push({ A: r.code, B: r.name, C: r.amount }));
            data.push({ A: "Total Ingresos", C: reportData.total_revenue });
            data.push({ A: "" });
            data.push({ A: "Gastos Operativos" });
            reportData.expenses.forEach(e => data.push({ A: e.code, B: e.name, C: e.amount }));
            data.push({ A: "Total Gastos", C: reportData.total_expenses });
            data.push({ A: "" });
            data.push({ A: "Utilidad Neta", C: reportData.net_income });
            ws = XLSX.utils.json_to_sheet(data, { skipHeader: true });
        } else if (activeTab === 'balance-sheet') {
            let data = [];
            data.push({ A: "ACTIVOS" });
            reportData.assets.forEach(a => data.push({ A: a.code, B: a.name, C: a.amount }));
            data.push({ A: "Total Activos", C: reportData.total_assets });
            data.push({ A: "" });
            data.push({ A: "PASIVOS" });
            reportData.liabilities.forEach(l => data.push({ A: l.code, B: l.name, C: l.amount }));
            data.push({ A: "Total Pasivos", C: reportData.total_liabilities });
            data.push({ A: "" });
            data.push({ A: "PATRIMONIO" });
            reportData.equity.forEach(e => data.push({ A: e.code, B: e.name, C: e.amount }));
            data.push({ A: "Total Patrimonio", C: reportData.total_equity });
            data.push({ A: "" });
            data.push({ A: "Total Pasivo + Patrimonio", C: reportData.total_liabilities_equity });
            ws = XLSX.utils.json_to_sheet(data, { skipHeader: true });
        }

        XLSX.utils.book_append_sheet(wb, ws, "Reporte");
        XLSX.writeFile(wb, `Reporte_${activeTab}_${new Date().toISOString().split('T')[0]}.xlsx`);
    };

    const calculateTotals = () => {
        if (activeTab === 'trial-balance') {
            return reportData.reduce((acc, item) => ({
                debit: acc.debit + Number(item.debit),
                credit: acc.credit + Number(item.credit),
                balance: acc.balance + Number(item.balance)
            }), { debit: 0, credit: 0, balance: 0 });
        }
        return { debit: 0, credit: 0, balance: 0 };
    };

    const totals = calculateTotals();

    const renderTrialBalance = () => (
        <table className="w-full text-sm text-left">
            <thead className="bg-gray-50 text-gray-500 font-semibold border-b border-gray-200">
                <tr>
                    <th className="px-6 py-3 w-24">Código</th>
                    <th className="px-6 py-3">Cuenta</th>
                    <th className="px-6 py-3 text-right w-32">Débito</th>
                    <th className="px-6 py-3 text-right w-32">Crédito</th>
                    <th className="px-6 py-3 text-right w-32 bg-gray-100">Saldo</th>
                </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
                {reportData.length === 0 ? (
                    <tr>
                        <td colSpan="5" className="px-6 py-12 text-center text-gray-400">
                            No hay datos para mostrar en este periodo.
                        </td>
                    </tr>
                ) : (
                    <>
                        {reportData.map((item, index) => (
                            <tr key={index} className="hover:bg-gray-50">
                                <td className="px-6 py-3 font-mono text-gray-600">{item.account_code}</td>
                                <td className="px-6 py-3 font-medium text-gray-800">{item.account_name}</td>
                                <td className="px-6 py-3 text-right font-mono text-gray-600">
                                    {Number(item.debit).toFixed(2)}
                                </td>
                                <td className="px-6 py-3 text-right font-mono text-gray-600">
                                    {Number(item.credit).toFixed(2)}
                                </td>
                                <td className="px-6 py-3 text-right font-mono font-bold text-gray-800 bg-gray-50">
                                    {Number(item.balance).toFixed(2)}
                                </td>
                            </tr>
                        ))}
                        <tr className="bg-gray-50 font-bold border-t-2 border-gray-200">
                            <td colSpan="2" className="px-6 py-4 text-right text-gray-700 uppercase tracking-wider">Totales</td>
                            <td className="px-6 py-4 text-right font-mono text-gray-900">{totals.debit.toFixed(2)}</td>
                            <td className="px-6 py-4 text-right font-mono text-gray-900">{totals.credit.toFixed(2)}</td>
                            <td className="px-6 py-4 text-right font-mono text-blue-700 bg-blue-50">{totals.balance.toFixed(2)}</td>
                        </tr>
                    </>
                )}
            </tbody>
        </table>
    );

    const renderIncomeStatement = () => {
        if (!reportData.revenues) return null;
        return (
            <div className="p-8 max-w-4xl mx-auto print:p-0">
                <div className="text-center mb-8">
                    <h3 className="text-2xl font-bold text-gray-800">Estado de Resultados</h3>
                    <p className="text-gray-500">Expresado en Moneda Local</p>
                </div>

                <div className="space-y-6">
                    {/* Revenues */}
                    <div>
                        <h4 className="font-bold text-gray-700 border-b border-gray-200 pb-2 mb-3">Ingresos Operativos</h4>
                        <div className="space-y-2">
                            {reportData.revenues.map((item, i) => (
                                <div key={i} className="flex justify-between text-sm">
                                    <span className="text-gray-600">{item.code} - {item.name}</span>
                                    <span className="font-mono">{Number(item.amount).toFixed(2)}</span>
                                </div>
                            ))}
                            <div className="flex justify-between font-bold text-gray-800 pt-2 border-t border-gray-100">
                                <span>Total Ingresos</span>
                                <span>{Number(reportData.total_revenue).toFixed(2)}</span>
                            </div>
                        </div>
                    </div>

                    {/* Expenses */}
                    <div>
                        <h4 className="font-bold text-gray-700 border-b border-gray-200 pb-2 mb-3">Gastos Operativos</h4>
                        <div className="space-y-2">
                            {reportData.expenses.map((item, i) => (
                                <div key={i} className="flex justify-between text-sm">
                                    <span className="text-gray-600">{item.code} - {item.name}</span>
                                    <span className="font-mono">{Number(item.amount).toFixed(2)}</span>
                                </div>
                            ))}
                            <div className="flex justify-between font-bold text-gray-800 pt-2 border-t border-gray-100">
                                <span>Total Gastos</span>
                                <span>{Number(reportData.total_expenses).toFixed(2)}</span>
                            </div>
                        </div>
                    </div>

                    {/* Net Income */}
                    <div className="bg-gray-50 p-4 rounded-lg flex justify-between items-center border border-gray-200 mt-8 print:bg-transparent print:border-black">
                        <span className="text-lg font-bold text-gray-800">Utilidad (Pérdida) Neta</span>
                        <span className={`text-xl font-mono font-bold ${reportData.net_income >= 0 ? 'text-green-600' : 'text-red-600'} print:text-black`}>
                            {Number(reportData.net_income).toFixed(2)}
                        </span>
                    </div>
                </div>
            </div>
        );
    };

    const renderBalanceSheet = () => {
        if (!reportData.assets) return null;
        return (
            <div className="p-8 max-w-4xl mx-auto print:p-0">
                <div className="text-center mb-8">
                    <h3 className="text-2xl font-bold text-gray-800">Balance General</h3>
                    <p className="text-gray-500">Al cierre del periodo</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-12 print:block print:space-y-8">
                    {/* Assets */}
                    <div>
                        <h4 className="font-bold text-lg text-gray-800 border-b-2 border-gray-800 pb-2 mb-4">Activos</h4>
                        <div className="space-y-2">
                            {reportData.assets.map((item, i) => (
                                <div key={i} className="flex justify-between text-sm">
                                    <span className="text-gray-600">{item.name}</span>
                                    <span className="font-mono">{Number(item.amount).toFixed(2)}</span>
                                </div>
                            ))}
                            <div className="flex justify-between font-bold text-gray-800 pt-4 border-t border-gray-200 mt-4 text-lg">
                                <span>Total Activos</span>
                                <span>{Number(reportData.total_assets).toFixed(2)}</span>
                            </div>
                        </div>
                    </div>

                    {/* Liabilities & Equity */}
                    <div className="space-y-8">
                        {/* Liabilities */}
                        <div>
                            <h4 className="font-bold text-lg text-gray-800 border-b-2 border-gray-800 pb-2 mb-4">Pasivos</h4>
                            <div className="space-y-2">
                                {reportData.liabilities.map((item, i) => (
                                    <div key={i} className="flex justify-between text-sm">
                                        <span className="text-gray-600">{item.name}</span>
                                        <span className="font-mono">{Number(item.amount).toFixed(2)}</span>
                                    </div>
                                ))}
                                <div className="flex justify-between font-bold text-gray-800 pt-2 border-t border-gray-200">
                                    <span>Total Pasivos</span>
                                    <span>{Number(reportData.total_liabilities).toFixed(2)}</span>
                                </div>
                            </div>
                        </div>

                        {/* Equity */}
                        <div>
                            <h4 className="font-bold text-lg text-gray-800 border-b-2 border-gray-800 pb-2 mb-4">Patrimonio</h4>
                            <div className="space-y-2">
                                {reportData.equity.map((item, i) => (
                                    <div key={i} className="flex justify-between text-sm">
                                        <span className={`text-gray-600 ${item.code === 'RESULT' ? 'font-bold' : ''}`}>{item.name}</span>
                                        <span className="font-mono">{Number(item.amount).toFixed(2)}</span>
                                    </div>
                                ))}
                                <div className="flex justify-between font-bold text-gray-800 pt-2 border-t border-gray-200">
                                    <span>Total Patrimonio</span>
                                    <span>{Number(reportData.total_equity).toFixed(2)}</span>
                                </div>
                            </div>
                        </div>

                        <div className="bg-gray-100 p-4 rounded-lg flex justify-between items-center font-bold text-gray-900 border border-gray-200 print:bg-transparent print:border-black">
                            <span>Total Pasivo + Patrimonio</span>
                            <span className="font-mono">{Number(reportData.total_liabilities_equity).toFixed(2)}</span>
                        </div>
                    </div>
                </div>
            </div>
        );
    };

    return (
        <div className="space-y-6">
            <style>
                {`
                    @media print {
                        @page { margin: 2cm; }
                        body * { visibility: hidden; }
                        #report-content, #report-content * { visibility: visible; }
                        #report-content { position: absolute; left: 0; top: 0; width: 100%; }
                        .no-print { display: none !important; }
                    }
                `}
            </style>
            <div className="flex justify-between items-center no-print">
                <div>
                    <h2 className="text-xl font-bold text-gray-800">Reportes Financieros</h2>
                    <p className="text-sm text-gray-500">Estados financieros y balances</p>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={handlePrint}
                        className="px-3 py-2 border border-gray-300 rounded-lg text-gray-600 hover:bg-gray-50 flex items-center gap-2 text-sm"
                    >
                        <Printer size={16} /> Imprimir
                    </button>
                    <button
                        onClick={handleExportExcel}
                        className="px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2 text-sm"
                    >
                        <Download size={16} /> Exportar Excel
                    </button>
                </div>
            </div>

            {/* Tabs */}
            <div className="border-b border-gray-200 no-print">
                <nav className="-mb-px flex space-x-8">
                    <button
                        onClick={() => setActiveTab('trial-balance')}
                        className={`py-4 px-1 border-b-2 font-medium text-sm ${activeTab === 'trial-balance' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}`}
                    >
                        Balance de Comprobación
                    </button>
                    <button
                        onClick={() => setActiveTab('income-statement')}
                        className={`py-4 px-1 border-b-2 font-medium text-sm ${activeTab === 'income-statement' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}`}
                    >
                        Estado de Resultados
                    </button>
                    <button
                        onClick={() => setActiveTab('balance-sheet')}
                        className={`py-4 px-1 border-b-2 font-medium text-sm ${activeTab === 'balance-sheet' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}`}
                    >
                        Balance General
                    </button>
                </nav>
            </div>

            {/* Content */}
            <div id="report-content" className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden min-h-[400px] print:shadow-none print:border-none">
                {loading ? (
                    <div className="flex items-center justify-center h-96 text-gray-500">
                        Generando reporte...
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        {activeTab === 'trial-balance' && renderTrialBalance()}
                        {activeTab === 'income-statement' && renderIncomeStatement()}
                        {activeTab === 'balance-sheet' && renderBalanceSheet()}
                    </div>
                )}
            </div>
        </div>
    );
};

export default ReportsPage;
