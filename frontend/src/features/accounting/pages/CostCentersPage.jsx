import React, { useState, useEffect } from 'react';
import api from '../../../shared/api/axiosConfig';
import { Layers, Plus, X, Trash2 } from 'lucide-react';
import { isAdmin } from '../../../shared/utils/auth';

const CostCentersPage = () => {
    const [costCenters, setCostCenters] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);

    const [formData, setFormData] = useState({
        code: '',
        name: ''
    });

    useEffect(() => {
        fetchCostCenters();
    }, []);

    const fetchCostCenters = async () => {
        try {
            const response = await api.get('/accounting/cost-centers');
            setCostCenters(response.data);
        } catch (error) {
            console.error("Error fetching cost centers:", error);
        } finally {
            setLoading(false);
        }
    };

    const handleDelete = async (id) => {
        if (!window.confirm("¿Está seguro de eliminar este centro de costos?")) return;
        try {
            await api.delete(`/accounting/cost-centers/${id}`);
            fetchCostCenters();
        } catch (error) {
            console.error(error);
            alert("Error al eliminar: " + (error.response?.data?.detail || error.message));
        }
    };

    const handleCreate = async (e) => {
        e.preventDefault();
        try {
            await api.post('/accounting/cost-centers', formData);
            setShowModal(false);
            setFormData({ code: '', name: '' });
            fetchCostCenters();
        } catch (error) {
            console.error(error);
            alert("Error al crear centro de costos");
        }
    };

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-xl font-bold text-gray-800">Centros de Costos</h2>
                    <p className="text-sm text-gray-500">Gestión de departamentos y proyectos</p>
                </div>
                <button
                    onClick={() => setShowModal(true)}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2"
                >
                    <Plus size={18} /> Nuevo Centro
                </button>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                {loading ? (
                    <div className="p-8 text-center text-gray-500">Cargando...</div>
                ) : (
                    <div className="divide-y divide-gray-100">
                        {costCenters.length === 0 ? (
                            <div className="p-12 text-center flex flex-col items-center text-gray-400">
                                <Layers size={48} className="mb-4 opacity-20" />
                                <p>No hay centros de costos definidos.</p>
                            </div>
                        ) : (
                            costCenters.map(cc => (
                                <div key={cc.id} className="p-4 flex items-center justify-between hover:bg-gray-50">
                                    <div className="flex items-center gap-4">
                                        <div className="p-3 rounded-lg bg-indigo-50 text-indigo-600">
                                            <Layers size={20} />
                                        </div>
                                        <div>
                                            <h4 className="font-bold text-gray-800">{cc.name}</h4>
                                            <p className="text-sm text-gray-500 font-mono">
                                                Código: {cc.code}
                                            </p>
                                        </div>
                                    </div>
                                    {isAdmin() && (
                                        <button
                                            onClick={() => handleDelete(cc.id)}
                                            className="text-red-500 hover:text-red-700 p-2 rounded-lg hover:bg-red-50"
                                            title="Eliminar (Admin)"
                                        >
                                            <Trash2 size={18} />
                                        </button>
                                    )}
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
                            <h3 className="text-lg font-bold text-gray-800">Nuevo Centro de Costos</h3>
                            <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600">
                                <X size={20} />
                            </button>
                        </div>

                        <form onSubmit={handleCreate} className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Código</label>
                                <input
                                    type="text"
                                    required
                                    placeholder="Ej: CC-001"
                                    className="w-full border border-gray-300 rounded-lg px-3 py-2"
                                    value={formData.code}
                                    onChange={e => setFormData({ ...formData, code: e.target.value })}
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Nombre</label>
                                <input
                                    type="text"
                                    required
                                    placeholder="Ej: Ventas"
                                    className="w-full border border-gray-300 rounded-lg px-3 py-2"
                                    value={formData.name}
                                    onChange={e => setFormData({ ...formData, name: e.target.value })}
                                />
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
                                    Guardar
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
};

export default CostCentersPage;
