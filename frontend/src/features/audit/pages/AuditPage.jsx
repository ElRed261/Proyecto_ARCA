import React, { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

const AuditPage = () => {
    const navigate = useNavigate();
    const [logs, setLogs] = useState([]);
    const [corrections, setCorrections] = useState([]);
    const [activeTab, setActiveTab] = useState('logs');
    const [loading, setLoading] = useState(true);
    const [newCorrection, setNewCorrection] = useState('');

    useEffect(() => {
        fetchData();
    }, [activeTab]);

    const fetchData = async () => {
        setLoading(true);
        try {
            if (activeTab === 'logs') {
                const logsData = await invoke('get_audit_logs', { skip: 0, limit: 100 });
                setLogs(logsData || []);
            } else {
                const corrData = await invoke('get_correction_requests', { skip: 0, limit: 100 });
                setCorrections(corrData || []);
            }
        } catch (error) {
            console.error("Error fetching data:", error);
        } finally {
            setLoading(false);
        }
    };

    const handleCorrectionSubmit = async (e) => {
        e.preventDefault();
        try {
            await invoke('create_correction_request', { 
                request: {
                    station_id: "General",
                    fecha: new Date().toISOString().split('T')[0],
                    hora: "00Z",
                    campo: "General",
                    valor_actual: "",
                    valor_propuesto: "",
                    justificacion: newCorrection,
                }
            });
            setNewCorrection('');
            fetchData();
        } catch (error) {
            console.error("Error submitting correction:", error);
        }
    };

    return (
        <div className="p-6">
            <div className="flex items-center gap-4 mb-4">
                <button
                    onClick={() => navigate('/dashboard')}
                    className="w-10 h-10 rounded-full bg-white border border-orange-200/60 shadow-sm transition-all hover:bg-orange-50 hover:scale-110 flex items-center justify-center text-orange-600 focus:outline-none focus:ring-2 focus:ring-orange-200/50 cursor-pointer"
                    title="Volver al Dashboard"
                >
                    <ArrowLeft className="w-5 h-5" />
                </button>
                <h1 className="text-2xl font-bold">Correcciones y Auditoría</h1>
            </div>

            <div className="mb-4 border-b border-gray-200">
                <nav className="-mb-px flex space-x-8">
                    <button
                        onClick={() => setActiveTab('logs')}
                        className={`${activeTab === 'logs' ? 'border-indigo-500 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'} whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
                    >
                        Logs de Auditoría
                    </button>
                    <button
                        onClick={() => setActiveTab('corrections')}
                        className={`${activeTab === 'corrections' ? 'border-indigo-500 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'} whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
                    >
                        Solicitudes de Corrección
                    </button>
                </nav>
            </div>

            <div className="bg-white shadow rounded-lg p-4">
                {loading ? (
                    <p>Cargando...</p>
                ) : activeTab === 'logs' ? (
                    <div className="overflow-x-auto">
                        <table className="min-w-full leading-normal">
                            <thead>
                                <tr>
                                    <th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">Timestamp</th>
                                    <th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">Acción</th>
                                    <th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">Entidad</th>
                                    <th className="px-5 py-3 border-b-2 border-gray-200 bg-gray-100 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">Detalles</th>
                                </tr>
                            </thead>
                            <tbody>
                                {logs.map((log) => (
                                    <tr key={log.id}>
                                        <td className="px-5 py-5 border-b border-gray-200 bg-white text-sm">{new Date(log.timestamp).toLocaleString()}</td>
                                        <td className="px-5 py-5 border-b border-gray-200 bg-white text-sm">{log.action}</td>
                                        <td className="px-5 py-5 border-b border-gray-200 bg-white text-sm">{log.entity}</td>
                                        <td className="px-5 py-5 border-b border-gray-200 bg-white text-sm">{log.details}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                ) : (
                    <div>
                        <form onSubmit={handleCorrectionSubmit} className="mb-6">
                            <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="correction">
                                Nueva Solicitud de Corrección
                            </label>
                            <div className="flex gap-2">
                                <input
                                    className="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
                                    id="correction"
                                    type="text"
                                    placeholder="Describa la corrección necesaria..."
                                    value={newCorrection}
                                    onChange={(e) => setNewCorrection(e.target.value)}
                                    required
                                />
                                <button
                                    className="bg-indigo-500 hover:bg-indigo-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline"
                                    type="submit"
                                >
                                    Enviar
                                </button>
                            </div>
                        </form>

                        <h3 className="text-lg font-semibold mb-2">Historial de Solicitudes</h3>
                        <ul className="divide-y divide-gray-200">
                            {corrections.map((correction) => (
                                <li key={correction.id} className="py-4">
                                    <div className="flex space-x-3">
                                        <div className="flex-1 space-y-1">
                                            <div className="flex items-center justify-between">
                                                <h3 className="text-sm font-medium">{correction.description}</h3>
                                                <p className={`text-sm ${correction.status === 'PENDING' ? 'text-yellow-600' : 'text-green-600'}`}>{correction.status}</p>
                                            </div>
                                            <p className="text-sm text-gray-500">Solicitado el {new Date(correction.created_at).toLocaleDateString()}</p>
                                        </div>
                                    </div>
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>
        </div>
    );
};

export default AuditPage;
