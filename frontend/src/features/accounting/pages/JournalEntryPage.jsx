import React, { useState, useEffect } from 'react';
import api from '../../../shared/api/axiosConfig';
import { Plus, Trash2, Save, FileText, AlertTriangle, CheckCircle, AlertCircle, Send } from 'lucide-react';
import { isAdmin } from '../../../shared/utils/auth';

const JournalEntryPage = ({ addLog }) => {
    const [entries, setEntries] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [accounts, setAccounts] = useState([]);
    const [costCenters, setCostCenters] = useState([]);

    // Form State
    const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
    const [reference, setReference] = useState('');
    const [description, setDescription] = useState('');
    const [lines, setLines] = useState([
        { account_id: '', debit: 0, credit: 0, cost_center_id: null },
        { account_id: '', debit: 0, credit: 0, cost_center_id: null }
    ]);

    useEffect(() => {
        fetchEntries();
        fetchAccounts();
        fetchCostCenters();
    }, []);

    const fetchEntries = async () => {
        try {
            const response = await api.get('/accounting/entries');
            setEntries(response.data);
        } catch (error) {
            console.error("Error fetching entries:", error);
            if (addLog) addLog("Error cargando asientos", "error");
        } finally {
            setLoading(false);
        }
    };

    const fetchAccounts = async () => {
        try {
            const response = await api.get('/accounting/accounts');
            const flatten = (accs) => {
                let res = [];
                accs.forEach(a => {
                    if (a.is_imputable) {
                        res.push(a);
                    }
                    if (a.children) res = res.concat(flatten(a.children));
                });
                return res;
            };
            setAccounts(flatten(response.data));
        } catch (error) {
            console.error("Error fetching accounts:", error);
            if (addLog) addLog("Error cargando cuentas", "error");
        }
    };

    const fetchCostCenters = async () => {
        try {
            const response = await api.get('/accounting/cost-centers');
            setCostCenters(response.data);
        } catch (error) {
            console.error(error);
            if (addLog) addLog("Error cargando centros de costo", "error");
        }
    };

    const handleAddLine = () => {
        setLines([...lines, { account_id: '', debit: 0, credit: 0, cost_center_id: null }]);
    };

    const handleRemoveLine = (index) => {
        if (lines.length <= 2) return;
        const newLines = lines.filter((_, i) => i !== index);
        setLines(newLines);
    };

    const handleLineChange = (index, field, value) => {
        const newLines = [...lines];
        newLines[index][field] = value;
        setLines(newLines);
    };

    const calculateTotals = () => {
        const totalDebit = lines.reduce((sum, line) => sum + Number(line.debit || 0), 0);
        const totalCredit = lines.reduce((sum, line) => sum + Number(line.credit || 0), 0);
        return { totalDebit, totalCredit, balanced: Math.abs(totalDebit - totalCredit) < 0.01 };
    };

    const handleSave = async (e) => {
        e.preventDefault();
        const totals = calculateTotals();
        if (!totals.balanced) {
            alert(`El asiento no está balanceado.\nDébito: ${totals.totalDebit.toFixed(2)}\nCrédito: ${totals.totalCredit.toFixed(2)}\nDiferencia: ${(totals.totalDebit - totals.totalCredit).toFixed(2)}`);
            return;
        }

        const payload = {
            date,
            description,
            items: lines.map(l => ({
                account_id: parseInt(l.account_id),
                debit: Number(l.debit),
                credit: Number(l.credit),
                cost_center_id: l.cost_center_id ? parseInt(l.cost_center_id) : null
            }))
        };

        try {
            const response = await api.post('/accounting/entries', payload);
            if (addLog) addLog("Borrador guardado", 'info');
            setShowModal(false);
            setDate(new Date().toISOString().split('T')[0]);
            setReference('');
            setDescription('');
            setLines([{ account_id: '', debit: 0, credit: 0, cost_center_id: null }, { account_id: '', debit: 0, credit: 0, cost_center_id: null }]);
            fetchEntries();
        } catch (error) {
            console.error(error);
            if (addLog) addLog("Error al guardar: " + (error.response?.data?.detail || error.message), 'error');
        }
    };

    const handlePost = async (id) => {
        try {
            await api.post(`/accounting/entries/${id}/post`);
            if (addLog) addLog("Asiento posteado exitosamente", 'success');
            fetchEntries();
        } catch (error) {
            console.error(error);
            if (addLog) addLog("Error al postear: " + (error.response?.data?.detail || error.message), 'error');
        }
    };

    const handleDeleteEntry = async (id) => {
        if (!window.confirm("¿Está seguro de eliminar este asiento? Esta acción es irreversible.")) return;
        try {
            await api.delete(`/accounting/entries/${id}`);
            fetchEntries();
            if (addLog) addLog("Asiento eliminado por administrador", 'warning');
        } catch (error) {
            console.error(error);
            if (addLog) addLog("Error al eliminar asiento: " + (error.response?.data?.detail || error.message), 'error');
        }
    };

    const { totalDebit, totalCredit, balanced } = calculateTotals();

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-xl font-bold text-gray-800">Libro Diario</h2>
                    <p className="text-sm text-gray-500">Registro de transacciones y asientos</p>
                </div>
                <button
                    onClick={() => setShowModal(true)}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2"
                >
                    <Plus size={18} /> Nuevo Asiento
                </button>
            </div>

            {/* Modal de Creación */}
            {showModal && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 overflow-y-auto py-10">
                    <div className="bg-white rounded-xl shadow-xl w-full max-w-4xl p-6">
                        <h3 className="text-lg font-bold text-gray-800 mb-4">Nuevo Asiento Contable</h3>
                        <form onSubmit={handleSave} className="space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Fecha</label>
                                    <input
                                        type="date"
                                        required
                                        className="w-full border border-gray-300 rounded-lg px-3 py-2"
                                        value={date}
                                        onChange={e => setDate(e.target.value)}
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Descripción</label>
                                    <input
                                        type="text"
                                        required
                                        className="w-full border border-gray-300 rounded-lg px-3 py-2"
                                        value={description}
                                        onChange={e => setDescription(e.target.value)}
                                        placeholder="Ej: Pago de nómina Enero"
                                    />
                                </div>
                            </div>

                            <div className="border-t border-gray-100 pt-4">
                                <h4 className="text-sm font-bold text-gray-700 mb-2">Detalle de Movimientos</h4>
                                <div className="space-y-2">
                                    {lines.map((line, index) => (
                                        <div key={index} className="flex gap-3 items-center">
                                            <select
                                                required
                                                className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm"
                                                value={line.account_id}
                                                onChange={e => handleLineChange(index, 'account_id', e.target.value)}
                                            >
                                                <option value="">Seleccionar Cuenta...</option>
                                                {accounts.map(acc => (
                                                    <option key={acc.id} value={acc.id}>{acc.code} - {acc.name}</option>
                                                ))}
                                            </select>
                                            <input
                                                type="number"
                                                min="0"
                                                step="0.01"
                                                placeholder="Débito"
                                                className="w-32 border border-gray-300 rounded-lg px-3 py-2 text-right text-sm"
                                                value={line.debit}
                                                onChange={e => handleLineChange(index, 'debit', e.target.value)}
                                            />
                                            <input
                                                type="number"
                                                min="0"
                                                step="0.01"
                                                placeholder="Crédito"
                                                className="w-32 border border-gray-300 rounded-lg px-3 py-2 text-right text-sm"
                                                value={line.credit}
                                                onChange={e => handleLineChange(index, 'credit', e.target.value)}
                                            />
                                            <button
                                                type="button"
                                                onClick={() => handleRemoveLine(index)}
                                                className="text-gray-400 hover:text-red-500"
                                                disabled={lines.length <= 2}
                                            >
                                                <Trash2 size={18} />
                                            </button>
                                        </div>
                                    ))}
                                </div>
                                <button
                                    type="button"
                                    onClick={handleAddLine}
                                    className="text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1 mt-2"
                                >
                                    <Plus size={14} /> Agregar Línea
                                </button>
                            </div>

                            <div className="flex justify-between items-center border-t border-gray-100 pt-4">
                                <div className="flex gap-6 text-sm">
                                    <div className="flex flex-col">
                                        <span className="text-gray-500">Total Débito</span>
                                        <span className="font-mono font-bold text-gray-800">{totals.totalDebit.toFixed(2)}</span>
                                    </div>
                                    <div className="flex flex-col">
                                        <span className="text-gray-500">Total Crédito</span>
                                        <span className="font-mono font-bold text-gray-800">{totals.totalCredit.toFixed(2)}</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        {totals.balanced ? (
                                            <span className="text-green-600 flex items-center gap-1 font-bold bg-green-50 px-3 py-1 rounded-full">
                                                <CheckCircle size={16} /> Balanceado
                                            </span>
                                        ) : (
                                            <span className="text-red-600 flex items-center gap-1 font-bold bg-red-50 px-3 py-1 rounded-full">
                                                <AlertCircle size={16} /> Descuadrado
                                            </span>
                                        )}
                                    </div>
                                </div>
                                <div className="flex gap-3">
                                    <button
                                        type="button"
                                        onClick={() => setShowModal(false)}
                                        className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
                                    >
                                        Cancelar
                                    </button>
                                    <button
                                        type="submit"
                                        disabled={!totals.balanced}
                                        className={`px-6 py-2 rounded-lg text-white font-bold flex items-center gap-2 ${totals.balanced ? 'bg-blue-600 hover:bg-blue-700' : 'bg-gray-300 cursor-not-allowed'}`}
                                    >
                                        <Save size={18} /> Guardar Borrador
                                    </button>
                                </div>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                {loading ? (
                    <div className="p-8 text-center text-gray-500">Cargando asientos...</div>
                ) : (
                    <div className="divide-y divide-gray-100">
                        {entries.map(entry => (
                            <div key={entry.id} className="p-4 hover:bg-gray-50 transition">
                                <div className="flex justify-between items-start mb-3">
                                    <div className="flex items-center gap-3">
                                        <div className={`p-2 rounded-lg ${entry.state === 'POSTED' ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-500'}`}>
                                            <FileText size={20} />
                                        </div>
                                        <div>
                                            <h4 className="font-bold text-gray-800">{entry.description}</h4>
                                            <div className="flex items-center gap-2 text-xs text-gray-500">
                                                <span className="font-mono">{entry.date}</span>
                                                <span>•</span>
                                                <span>ID: {entry.id}</span>
                                                {entry.entry_number && (
                                                    <>
                                                        <span>•</span>
                                                        <span className="font-mono text-gray-700">Ref: {entry.entry_number}</span>
                                                    </>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <span className={`text-xs font-bold px-2 py-1 rounded uppercase ${entry.state === 'POSTED' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}>
                                            {entry.state === 'POSTED' ? 'Asentado' : 'Borrador'}
                                        </span>
                                        {entry.state === 'DRAFT' && (
                                            <button
                                                onClick={() => handlePost(entry.id)}
                                                className="text-sm bg-indigo-600 text-white px-3 py-1 rounded hover:bg-indigo-700 flex items-center gap-1"
                                                title="Postear Asiento"
                                            >
                                                <Send size={14} /> Postear
                                            </button>
                                        )}
                                        {isAdmin() && (
                                            <button
                                                onClick={() => handleDeleteEntry(entry.id)}
                                                className="text-red-500 hover:text-red-700 p-1"
                                                title="Eliminar (Admin)"
                                            >
                                                <Trash2 size={16} />
                                            </button>
                                        )}
                                    </div>
                                </div>

                                <div className="bg-gray-50 rounded p-3 text-sm">
                                    {entry.items.map(item => (
                                        <div key={item.id} className="flex justify-between py-1 border-b border-gray-100 last:border-0">
                                            <span className="text-gray-600 flex-1">
                                                {accounts.find(a => a.id === item.account_id)?.name || `Cuenta #${item.account_id}`}
                                            </span>
                                            <div className="flex gap-8 font-mono text-gray-700">
                                                <span className="w-24 text-right">{Number(item.debit) > 0 ? Number(item.debit).toFixed(2) : '-'}</span>
                                                <span className="w-24 text-right">{Number(item.credit) > 0 ? Number(item.credit).toFixed(2) : '-'}</span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ))}
                        {entries.length === 0 && (
                            <div className="p-8 text-center text-gray-400">No hay asientos registrados</div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};

export default JournalEntryPage;
