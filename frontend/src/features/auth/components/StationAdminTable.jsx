import React, { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { Edit, Trash2, Plus, CheckCircle, XCircle } from 'lucide-react';
import toast from 'react-hot-toast';

export const StationAdminTable = ({ addLog, fetchStationsAndConfig }) => {
    const [stations, setStations] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [form, setForm] = useState({ id: '', name: '', provincia: '', latitud: 0, longitud: 0, elevacion: 0, ch: 0, is_active: true });
    const [isEditing, setIsEditing] = useState(false);

    useEffect(() => {
        loadStations();
    }, []);

    const loadStations = async () => {
        try {
            setLoading(true);
            const data = await invoke('get_stations');
            const arr = Object.values(data).sort((a, b) => a.name.localeCompare(b.name));
            setStations(arr);
            fetchStationsAndConfig && fetchStationsAndConfig(); // Sync parent's list
        } catch (error) {
            console.error('Error cargando estaciones:', error);
            toast.error('Error al cargar la lista de estaciones');
        } finally {
            setLoading(false);
        }
    };

    const openCreate = () => {
        setForm({ id: '', name: '', provincia: '', latitud: 0, longitud: 0, elevacion: 0, ch: 0, is_active: true });
        setIsEditing(false);
        setShowModal(true);
    };

    const openEdit = (st) => {
        setForm({ ...st });
        setIsEditing(true);
        setShowModal(true);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            // Convert to numbers
            const payload = {
                ...form,
                latitud: parseFloat(form.latitud),
                longitud: parseFloat(form.longitud),
                elevacion: parseFloat(form.elevacion),
                ch: parseFloat(form.ch),
            };

            if (isEditing) {
                await invoke('update_station', { station: payload });
                toast.success('Estación actualizada correctamente');
                addLog && addLog(`Estación ${form.name} actualizada`, 'success');
            } else {
                await invoke('create_station', { station: payload });
                toast.success('Estación creada correctamente');
                addLog && addLog(`Estación ${form.name} creada`, 'success');
            }
            setShowModal(false);
            loadStations();
        } catch (err) {
            console.error(err);
            toast.error('Error al guardar estación');
        }
    };

    const handleDelete = async (st) => {
        if (window.confirm(`¿Seguro que deseas eliminar la estación ${st.name}?`)) {
            try {
                await invoke('delete_station', { id: st.id });
                toast.success('Estación eliminada');
                addLog && addLog(`Estación ${st.name} eliminada`, 'warning');
                loadStations();
            } catch (err) {
                console.error(err);
                toast.error('Error al eliminar estación');
            }
        }
    };

    return (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden mt-8">
            <div className="p-6 border-b border-gray-200 flex justify-between items-center bg-gray-50">
                <h2 className="text-xl font-bold text-gray-800">Directorio de Estaciones</h2>
                <button
                    onClick={openCreate}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition flex items-center gap-2 text-sm font-medium"
                >
                    <Plus size={16} /> Nueva Estación
                </button>
            </div>
            
            <div className="overflow-x-auto">
                <table className="w-full text-left">
                    <thead className="bg-gray-50 border-b border-gray-200">
                        <tr>
                            <th className="px-6 py-4 text-xs font-semibold text-gray-500 uppercase">Código</th>
                            <th className="px-6 py-4 text-xs font-semibold text-gray-500 uppercase">Nombre</th>
                            <th className="px-6 py-4 text-xs font-semibold text-gray-500 uppercase">Provincia</th>
                            <th className="px-6 py-4 text-xs font-semibold text-gray-500 uppercase">C. Altura</th>
                            <th className="px-6 py-4 text-xs font-semibold text-gray-500 uppercase">Estado</th>
                            <th className="px-6 py-4 text-xs font-semibold text-gray-500 uppercase text-right">Acciones</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                        {loading ? (
                            <tr><td colSpan="6" className="px-6 py-8 text-center text-gray-500">Cargando...</td></tr>
                        ) : stations.map((st) => (
                            <tr key={st.id} className="hover:bg-gray-50 transition">
                                <td className="px-6 py-4 text-sm font-medium text-gray-900">{st.id}</td>
                                <td className="px-6 py-4 text-sm text-gray-600">{st.name}</td>
                                <td className="px-6 py-4 text-sm text-gray-500">{st.provincia}</td>
                                <td className="px-6 py-4 text-sm text-gray-500">{st.ch}</td>
                                <td className="px-6 py-4">
                                    {st.is_active ? (
                                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                            <CheckCircle size={12} /> Activa
                                        </span>
                                    ) : (
                                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                                            <XCircle size={12} /> Inactiva
                                        </span>
                                    )}
                                </td>
                                <td className="px-6 py-4 text-right space-x-2">
                                    <button onClick={() => openEdit(st)} aria-label="Editar estación" className="p-2 text-blue-600 hover:bg-blue-50 rounded-full">
                                        <Edit size={16} />
                                    </button>
                                    <button onClick={() => handleDelete(st)} aria-label="Eliminar estación" className="p-2 text-red-600 hover:bg-red-50 rounded-full">
                                        <Trash2 size={16} />
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Modal */}
            {showModal && (
                <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className="bg-white rounded-2xl w-full max-w-xl shadow-2xl overflow-hidden">
                        <div className="p-6 border-b border-gray-100 bg-gray-50">
                            <h2 className="text-xl font-bold text-gray-800">
                                {isEditing ? 'Editar Estación' : 'Nueva Estación'}
                            </h2>
                        </div>
                        <form onSubmit={handleSubmit} className="p-6">
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Código (ID)</label>
                                    <input required disabled={isEditing} className="w-full border border-gray-300 rounded-lg p-2 bg-gray-50" value={form.id} onChange={e => setForm({...form, id: e.target.value})} />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Nombre</label>
                                    <input required className="w-full border border-gray-300 rounded-lg p-2" value={form.name} onChange={e => setForm({...form, name: e.target.value})} />
                                </div>
                                <div className="col-span-2">
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Provincia</label>
                                    <input required className="w-full border border-gray-300 rounded-lg p-2" value={form.provincia} onChange={e => setForm({...form, provincia: e.target.value})} />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Latitud</label>
                                    <input required type="number" step="any" className="w-full border border-gray-300 rounded-lg p-2" value={form.latitud} onChange={e => setForm({...form, latitud: e.target.value})} />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Longitud</label>
                                    <input required type="number" step="any" className="w-full border border-gray-300 rounded-lg p-2" value={form.longitud} onChange={e => setForm({...form, longitud: e.target.value})} />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Elevación (m)</label>
                                    <input required type="number" step="any" className="w-full border border-gray-300 rounded-lg p-2" value={form.elevacion} onChange={e => setForm({...form, elevacion: e.target.value})} />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Correc. Altura (CH)</label>
                                    <input required type="number" step="any" className="w-full border border-gray-300 rounded-lg p-2" value={form.ch} onChange={e => setForm({...form, ch: e.target.value})} />
                                </div>
                                <div className="col-span-2 flex items-center mt-2">
                                    <input type="checkbox" id="active" checked={form.is_active} onChange={e => setForm({...form, is_active: e.target.checked})} className="mr-2 h-4 w-4 text-blue-600 rounded border-gray-300" />
                                    <label htmlFor="active" className="text-sm font-medium text-gray-700">Estación Activa</label>
                                </div>
                            </div>
                            <div className="flex justify-end gap-3 mt-8">
                                <button type="button" onClick={() => setShowModal(false)} className="px-5 py-2 text-gray-600 hover:bg-gray-100 rounded-lg font-medium transition">Cancelar</button>
                                <button type="submit" className="px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition font-medium shadow-md">
                                    Guardar Cambios
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
};
