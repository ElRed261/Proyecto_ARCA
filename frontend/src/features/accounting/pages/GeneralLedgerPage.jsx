import React, { useState, useEffect } from 'react';
import api from '../../../shared/api/axiosConfig';
import { Search, Calendar, ArrowRight } from 'lucide-react';

const GeneralLedgerPage = () => {
    const [accounts, setAccounts] = useState([]);
    const [selectedAccount, setSelectedAccount] = useState('');
    const [ledger, setLedger] = useState([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        fetchAccounts();
    }, []);

    useEffect(() => {
        if (selectedAccount) {
            fetchLedger(selectedAccount);
        } else {
            setLedger([]);
        }
    }, [selectedAccount]);

    const fetchAccounts = async () => {
        try {
            const response = await api.get('/accounting/accounts');
            // Solo cuentas imputables pueden tener movimientos
            setAccounts(response.data.filter(a => a.is_imputable).sort((a, b) => a.code.localeCompare(b.code)));
        } catch (error) {
            console.error("Error fetching accounts:", error);
        }
    };

    const fetchLedger = async (accountId) => {
        setLoading(true);
        try {
            const response = await api.get(`/accounting/accounts/${accountId}/ledger`);
            setLedger(response.data);
        } catch (error) {
            console.error("Error fetching ledger:", error);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-xl font-bold text-gray-800">Libro Mayor</h2>
                    <p className="text-sm text-gray-500">Historial de transacciones y saldos por cuenta</p>
                </div>

                <div className="w-96">
                    <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Seleccionar Cuenta</label>
                    <select
                        className="w-full border border-gray-300 rounded-lg px-3 py-2 bg-white shadow-sm"
                        value={selectedAccount}
                        onChange={(e) => setSelectedAccount(e.target.value)}
                    >
                        <option value="">-- Seleccione una cuenta --</option>
                        {accounts.map(acc => (
                            <option key={acc.id} value={acc.id}>{acc.code} - {acc.name}</option>
                        ))}
                    </select>
                </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden min-h-[400px]">
                {!selectedAccount ? (
                    <div className="flex flex-col items-center justify-center h-96 text-gray-400">
                        <Search size={48} className="mb-4 opacity-20" />
                        <p>Seleccione una cuenta para ver sus movimientos</p>
                    </div>
                ) : loading ? (
                    <div className="flex items-center justify-center h-96 text-gray-500">
                        Cargando movimientos...
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm text-left">
                            <thead className="bg-gray-50 text-gray-500 font-semibold border-b border-gray-200">
                                <tr>
                                    <th className="px-6 py-3 w-32">Fecha</th>
                                    <th className="px-6 py-3 w-40">Asiento #</th>
                                    <th className="px-6 py-3">Descripción</th>
                                    <th className="px-6 py-3 text-right w-32">Débito</th>
                                    <th className="px-6 py-3 text-right w-32">Crédito</th>
                                    <th className="px-6 py-3 text-right w-32 bg-gray-100">Saldo</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100">
                                {ledger.length === 0 ? (
                                    <tr>
                                        <td colSpan="6" className="px-6 py-12 text-center text-gray-400">
                                            Esta cuenta no tiene movimientos registrados.
                                        </td>
                                    </tr>
                                ) : (
                                    ledger.map((item, index) => (
                                        <tr key={index} className="hover:bg-gray-50">
                                            <td className="px-6 py-3 font-mono text-gray-600">{item.date}</td>
                                            <td className="px-6 py-3">
                                                <span className="bg-blue-50 text-blue-700 px-2 py-1 rounded text-xs font-mono">
                                                    {item.entry_number || 'N/A'}
                                                </span>
                                            </td>
                                            <td className="px-6 py-3 text-gray-800">{item.description}</td>
                                            <td className="px-6 py-3 text-right font-mono text-gray-600">
                                                {Number(item.debit) > 0 ? Number(item.debit).toFixed(2) : '-'}
                                            </td>
                                            <td className="px-6 py-3 text-right font-mono text-gray-600">
                                                {Number(item.credit) > 0 ? Number(item.credit).toFixed(2) : '-'}
                                            </td>
                                            <td className="px-6 py-3 text-right font-mono font-bold text-gray-800 bg-gray-50">
                                                {Number(item.balance).toFixed(2)}
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
};

export default GeneralLedgerPage;
