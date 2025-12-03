import React, { useState, useEffect } from 'react';
import api from '../../../shared/api/axiosConfig';
import { FolderTree, Plus, ChevronRight, ChevronDown, Trash2 } from 'lucide-react';
import { isAdmin } from '../../../shared/utils/auth';

const AccountItem = ({ account, level = 0, expanded, toggleExpand, handleDelete }) => {
    const hasChildren = account.children && account.children.length > 0;
    const isExpanded = expanded[account.id];

    return (
        <div className="select-none">
            <div
                className={`flex items-center justify-between py-2 px-4 hover:bg-gray-50 border-b border-gray-100 transition-colors ${level === 0 ? 'font-bold text-gray-800' : 'text-gray-600'}`}
                style={{ paddingLeft: `${level * 20 + 16}px` }}
            >
                <div className="flex items-center gap-2 flex-1">
                    <button
                        onClick={() => toggleExpand(account.id)}
                        className={`p-1 rounded hover:bg-gray-200 text-gray-400 ${!hasChildren && 'invisible'}`}
                    >
                        {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </button>

                    <span className="font-mono text-sm text-gray-500 w-24">{account.code}</span>
                    <span className="flex-1">{account.name}</span>

                    <span className={`text-xs px-2 py-1 rounded-full ${account.is_imputable ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                        {account.is_imputable ? 'Imputable' : 'Agrupador'}
                    </span>
                    <span className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded-full ml-2">
                        {account.account_type}
                    </span>
                </div>

                {isAdmin() && (
                    <button
                        onClick={() => handleDelete(account.id)}
                        className="text-red-500 hover:text-red-700 p-1 ml-4"
                        title="Eliminar (Admin)"
                    >
                        <Trash2 size={16} />
                    </button>
                )}
            </div>

            {hasChildren && isExpanded && (
                <div>
                    {account.children.map(child => (
                        <AccountItem
                            key={child.id}
                            account={child}
                            level={level + 1}
                            expanded={expanded}
                            toggleExpand={toggleExpand}
                            handleDelete={handleDelete}
                        />
                    ))}
                </div>
            )}
        </div>
    );
};

const ChartOfAccountsPage = () => {
    const [accounts, setAccounts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [expanded, setExpanded] = useState({});
    const [showModal, setShowModal] = useState(false);
    const [newAccount, setNewAccount] = useState({
        code: '',
        name: '',
        account_type: 'ASSET',
        parent_id: null,
        is_imputable: true
    });

    useEffect(() => {
        fetchAccounts();
    }, []);

    const fetchAccounts = async () => {
        try {
            const response = await api.get('/accounting/accounts');
            setAccounts(response.data);
        } catch (error) {
            console.error("Error fetching accounts:", error);
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (id) => {
        if (!window.confirm("¿Está seguro de eliminar esta cuenta?")) return;
        try {
            await api.delete(`/accounting/accounts/${id}`);
            fetchAccounts();
        } catch (error) {
            console.error(error);
            alert("Error al eliminar cuenta: " + (error.response?.data?.detail || error.message));
        }
    };

    const toggleExpand = (id) => {
        setExpanded(prev => ({ ...prev, [id]: !prev[id] }));
    };

    const handleCreateAccount = async (e) => {
        e.preventDefault();
        try {
            await api.post('/accounting/accounts', newAccount);
            setShowModal(false);
            setNewAccount({ code: '', name: '', account_type: 'ASSET', parent_id: null, is_imputable: true });
            fetchAccounts();
        } catch (error) {
            console.error(error);
            alert("Error al crear cuenta: " + (error.response?.data?.detail || error.message));
        }
    };

    // Flatten accounts for parent selection
    const getAllAccounts = (nodes) => {
        let accs = [];
        nodes.forEach(node => {
            accs.push(node);
            if (node.children) {
                accs = accs.concat(getAllAccounts(node.children));
            }
        });
        return accs;
    };
    const flatAccounts = getAllAccounts(accounts);

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-xl font-bold text-gray-800">Plan de Cuentas</h2>
                    <p className="text-sm text-gray-500">Estructura jerárquica de cuentas contables</p>
                </div>
                <button
                    onClick={() => setShowModal(true)}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2"
                >
                    <Plus size={18} /> Nueva Cuenta
                </button>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                {loading ? (
                    <div className="p-8 text-center text-gray-500">Cargando cuentas...</div>
                ) : (
                    <div className="divide-y divide-gray-100">
                        {accounts.map(account => (
                            <AccountItem
                                key={account.id}
                                account={account}
                                expanded={expanded}
                                toggleExpand={toggleExpand}
                                handleDelete={handleDelete}
                            />
                        ))}
                    </div>
                )}
            </div>

            {/* Modal de Creación */}
            {showModal && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
                        <h3 className="text-lg font-bold text-gray-800 mb-4">Nueva Cuenta</h3>
                        <form onSubmit={handleCreateAccount} className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Código</label>
                                <input
                                    type="text"
                                    required
                                    className="w-full border border-gray-300 rounded-lg px-3 py-2"
                                    value={newAccount.code}
                                    onChange={e => setNewAccount({ ...newAccount, code: e.target.value })}
                                    placeholder="Ej: 1.1.01"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Nombre</label>
                                <input
                                    type="text"
                                    required
                                    className="w-full border border-gray-300 rounded-lg px-3 py-2"
                                    value={newAccount.name}
                                    onChange={e => setNewAccount({ ...newAccount, name: e.target.value })}
                                    placeholder="Ej: Caja General"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Tipo</label>
                                <select
                                    className="w-full border border-gray-300 rounded-lg px-3 py-2"
                                    value={newAccount.account_type}
                                    onChange={e => setNewAccount({ ...newAccount, account_type: e.target.value })}
                                >
                                    <option value="ASSET">Activo</option>
                                    <option value="LIABILITY">Pasivo</option>
                                    <option value="EQUITY">Patrimonio</option>
                                    <option value="REVENUE">Ingreso</option>
                                    <option value="EXPENSE">Gasto</option>
                                </select>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Cuenta Padre (Opcional)</label>
                                <select
                                    className="w-full border border-gray-300 rounded-lg px-3 py-2"
                                    value={newAccount.parent_id || ''}
                                    onChange={e => setNewAccount({ ...newAccount, parent_id: e.target.value ? parseInt(e.target.value) : null })}
                                >
                                    <option value="">Ninguna (Raíz)</option>
                                    {flatAccounts.filter(a => !a.is_imputable).map(acc => (
                                        <option key={acc.id} value={acc.id}>{acc.code} - {acc.name}</option>
                                    ))}
                                </select>
                            </div>

                            <div className="flex items-center gap-2">
                                <input
                                    type="checkbox"
                                    id="is_imputable"
                                    checked={newAccount.is_imputable}
                                    onChange={e => setNewAccount({ ...newAccount, is_imputable: e.target.checked })}
                                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                                />
                                <label htmlFor="is_imputable" className="text-sm text-gray-700">Es Imputable (Recibe asientos)</label>
                            </div>

                            <div className="flex justify-end gap-3 mt-6">
                                <button
                                    type="button"
                                    onClick={() => setShowModal(false)}
                                    className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
                                >
                                    Cancelar
                                </button>
                                <button
                                    type="submit"
                                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
                                >
                                    Guardar Cuenta
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
};

export default ChartOfAccountsPage;
