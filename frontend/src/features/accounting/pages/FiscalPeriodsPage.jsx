import React, { useState, useEffect } from 'react';
import api from '../../../shared/api/axiosConfig';
import { Calendar, Lock, Unlock, Plus, X, Trash2, RefreshCw, AlertTriangle } from 'lucide-react';
import { isAdmin } from '../../../shared/utils/auth';

const FiscalPeriodsPage = () => {
    const [periods, setPeriods] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [newPeriod, setNewPeriod] = useState({
        name: '',
        start_date: '',
        end_date: ''
    });

    useEffect(() => {
        fetchPeriods();
    }, []);

    const fetchPeriods = async () => {
        try {
            const response = await api.get('/accounting/periods');
            setPeriods(response.data);
        } catch (error) {
            console.error("Error fetching periods:", error);
        } finally {
            setLoading(false);
        }
    };

    const handleClosePeriod = async (id) => {
        if (!window.confirm("¿Está seguro de cerrar este periodo? No se podrán crear más asientos.")) return;
        try {
            await api.post(`/accounting/periods/${id}/close`);
            fetchPeriods();
        } catch (error) {
            console.error(error);
            alert("Error al cerrar periodo");
        }
    };

    const handleReopenPeriod = async (id) => {
        if (!window.confirm("¿Está seguro de reabrir este periodo? (Acción de Administrador)")) return;
        try {
            await api.post(`/accounting/periods/${id}/reopen`);
            fetchPeriods();
        } catch (error) {
            console.error(error);
            alert("Error al reabrir periodo");
        }
    };

    const handleDeletePeriod = async (id) => {
        if (!window.confirm("¿Está seguro de eliminar este periodo? (Acción de Administrador)")) return;
        try {
            await api.delete(`/accounting/periods/${id}`);
            fetchPeriods();
        } catch (error) {
            console.error(error);
            alert("Error al eliminar periodo");
        }
    };

    const handleCreate = async (e) => {
        e.preventDefault();
        try {
            await api.post('/accounting/periods', newPeriod);
            setShowModal(false);
            setNewPeriod({ name: '', start_date: '', end_date: '' });
            fetchPeriods();
        } catch (error) {
            console.error(error);
            alert("Error al crear periodo: " + (error.response?.data?.detail || error.message));
        }
    };

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-xl font-bold text-gray-800">Periodos Fiscales</h2>
                    <p className="text-sm text-gray-500">Gestión de cierres mensuales y anuales</p>
                </div>
                <button
                    onClick={() => setShowModal(true)}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2"
                >
                    <Plus size={18} /> Nuevo Periodo
                </button>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                {loading ? (
                    <div className="p-8 text-center text-gray-500">Cargando...</div>
                ) : (
                    <div className="divide-y divide-gray-100">
                        {periods.length === 0 ? (
                            <div className="p-12 text-center flex flex-col items-center text-gray-400">
                                <Calendar size={48} className="mb-4 opacity-20" />
                                <p>No hay periodos fiscales definidos.</p>
                            </div>
                        ) : (
                            periods.map(period => (
                                <div key={period.id} className="p-4 flex items-center justify-between hover:bg-gray-50">
                                    <div className="flex items-center gap-4">
                                        <div className={`p-3 rounded-lg ${period.is_closed ? 'bg-red-50 text-red-600' : 'bg-green-50 text-green-600'}`}>
                                            {period.is_closed ? <Lock size={20} /> : <Unlock size={20} />}
                                        </div>
                                        <div>
                                            <h4 className="font-bold text-gray-800">{period.name}</h4>
                                            <p className="text-sm text-gray-500 font-mono">
                                                {period.start_date} - {period.end_date}
                                            </p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        {!period.is_closed ? (
                                            <button
                                                onClick={() => handleClosePeriod(period.id)}
                                                className="px-3 py-1 text-sm border border-red-200 text-red-600 rounded-lg hover:bg-red-50"
                                            >
                                                Cerrar Periodo
                                            </button>
                                        ) : (
                                            <span className="px-3 py-1 text-sm bg-gray-100 text-gray-500 rounded-lg">
                                                Cerrado
                                            </span>
                                        )}

                                        {isAdmin() && (
                                            <>
                                                {period.is_closed && (
                                                    <button
                                                        onClick={() => handleReopenPeriod(period.id)}
                                                        className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg"
                                                        title="Reabrir (Admin)"
                                                    >
                                                        <RefreshCw size={18} />
                                                    </button>
                                                )}
                                                <button
                                                    onClick={() => handleDeletePeriod(period.id)}
                                                    className="p-2 text-red-500 hover:bg-red-50 rounded-lg"
                                                    title="Eliminar (Admin)"
                                                >
                                                    <Trash2 size={18} />
                                                </button>
                                            </>
                                        )}
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                )}
            </div>

            {/* Modal */}
            {showModal && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                    <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
                        <div className="flex justify-between items-center mb-6">
                            <h3 className="text-lg font-bold text-gray-800">Nuevo Periodo Fiscal</h3>
                            <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600">
                                <X size={20} />
                            </button>
                        </div>

                        <form onSubmit={handleCreate} className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Nombre</label>
                                <input
                                    type="text"
                                    required
                                    placeholder="Ej: Enero 2025"
                                    className="w-full border border-gray-300 rounded-lg px-3 py-2"
                                    value={formData.name}
                                    onChange={e => setFormData({ ...formData, name: e.target.value })}
                                />
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Inicio</label>
                                    <input
                                        type="date"
                                        required
                                        className="w-full border border-gray-300 rounded-lg px-3 py-2"
                                        value={formData.start_date}
                                        onChange={e => setFormData({ ...formData, start_date: e.target.value })}
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Fin</label>
                                    <input
                                        type="date"
                                        required
                                        className="w-full border border-gray-300 rounded-lg px-3 py-2"
                                        value={formData.end_date}
                                        onChange={e => setFormData({ ...formData, end_date: e.target.value })}
                                    />
                                </div>
                            </div>

                            <div className="bg-yellow-50 p-3 rounded-lg flex gap-2 text-xs text-yellow-800">
                                <AlertTriangle size={16} className="shrink-0" />
                                <p>Asegúrese de que las fechas no se solapen con otros periodos existentes.</p>
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
                                    Crear Periodo
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
};

export default FiscalPeriodsPage;
