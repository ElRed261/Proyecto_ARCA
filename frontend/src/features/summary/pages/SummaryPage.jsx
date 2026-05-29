import React, { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { open as openDialog, save as saveDialog } from '@tauri-apps/plugin-dialog';
import { FileSpreadsheet, FileJson, Download, Plus, Clock, FileWarning, Loader2, ArrowRight } from 'lucide-react';
import toast from 'react-hot-toast';

const SummaryPage = () => {
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(false);
    const [processing, setProcessing] = useState(false);
    
    const [currentDoc, setCurrentDoc] = useState(null);
    const [activeTab, setActiveTab] = useState('history'); // 'history' | 'view'

    useEffect(() => {
        fetchHistory();
    }, []);

    const fetchHistory = async () => {
        setLoading(true);
        try {
            const data = await invoke('ms_list_history');
            setHistory(data);
        } catch (error) {
            console.error("Error fetching history:", error);
            toast.error("Error cargando historial de resúmenes");
        } finally {
            setLoading(false);
        }
    };

    const handleGenerateNew = async () => {
        try {
            const selectedFiles = await openDialog({
                multiple: true,
                filters: [{
                    name: 'Observaciones',
                    extensions: ['json', 'xlsx']
                }]
            });

            if (!selectedFiles || selectedFiles.length === 0) return;

            setProcessing(true);
            const doc = await invoke('ms_generate_summary', { files: selectedFiles });
            setCurrentDoc(doc);
            setActiveTab('view');
            toast.success("Resumen generado exitosamente");
            fetchHistory(); // Refresh history
        } catch (error) {
            console.error("Generate error:", error);
            toast.error(error.toString() || "Error al procesar archivos");
        } finally {
            setProcessing(false);
        }
    };

    const handleLoadSummary = async (path) => {
        setLoading(true);
        try {
            const doc = await invoke('ms_load_summary', { path });
            setCurrentDoc(doc);
            setActiveTab('view');
            toast.success("Resumen cargado");
        } catch (error) {
            console.error("Load error:", error);
            toast.error("Error al cargar el resumen");
        } finally {
            setLoading(false);
        }
    };

    const handleExportExcel = async () => {
        if (!currentDoc) return;
        try {
            const safeStation = currentDoc.meta.estacion.replace(/[\/\\]/g, '_');
            const safePeriod = currentDoc.meta.periodo.replace(/[\/\\]/g, '');
            const defaultName = `resumen_${safeStation}_${safePeriod}.xlsx`;

            const savePath = await saveDialog({
                defaultPath: defaultName,
                filters: [{ name: 'Excel', extensions: ['xlsx'] }]
            });

            if (!savePath) return;

            await invoke('ms_export_excel', { doc: currentDoc, outPath: savePath });
            toast.success("Exportado a Excel correctamente");
        } catch (error) {
            console.error("Export error:", error);
            toast.error("Error al exportar a Excel");
        }
    };

    const TableHeader = ({ children }) => (
        <th className="px-3 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider whitespace-nowrap bg-slate-50 border-b border-slate-200">
            {children}
        </th>
    );

    const TableCell = ({ children, isNumeric }) => (
        <td className={`px-3 py-2 whitespace-nowrap text-sm text-slate-700 border-b border-slate-100 ${isNumeric ? 'text-right font-mono' : ''}`}>
            {children !== null && children !== undefined ? children : '-'}
        </td>
    );

    return (
        <div className="flex flex-col h-[calc(100vh-8rem)]">
            {/* Header section */}
            <div className="flex justify-between items-center mb-6">
                <div>
                    <h1 className="text-3xl font-bold text-slate-800 tracking-tight">Resumen Mensual SYNOP</h1>
                    <p className="text-slate-500 mt-1">Generación y visualización de resúmenes climáticos</p>
                </div>
                <div className="flex gap-3">
                    <button
                        onClick={() => setActiveTab('history')}
                        className={`px-4 py-2 rounded-lg font-medium transition-all flex items-center gap-2 ${
                            activeTab === 'history' 
                            ? 'bg-blue-50 text-blue-700 border border-blue-200' 
                            : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
                        }`}
                    >
                        <Clock className="w-4 h-4" /> Historial
                    </button>
                    {currentDoc && (
                        <button
                            onClick={() => setActiveTab('view')}
                            className={`px-4 py-2 rounded-lg font-medium transition-all flex items-center gap-2 ${
                                activeTab === 'view' 
                                ? 'bg-blue-50 text-blue-700 border border-blue-200' 
                                : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
                            }`}
                        >
                            <FileJson className="w-4 h-4" /> Resumen Actual
                        </button>
                    )}
                    <button
                        onClick={handleGenerateNew}
                        disabled={processing}
                        className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-all shadow-sm flex items-center gap-2 disabled:opacity-50"
                    >
                        {processing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                        Generar Nuevo
                    </button>
                </div>
            </div>

            {/* Content section */}
            <div className="bg-white border border-slate-200 rounded-xl shadow-sm flex-1 overflow-hidden flex flex-col">
                {activeTab === 'history' && (
                    <div className="p-6 overflow-y-auto">
                        <h2 className="text-xl font-semibold text-slate-800 mb-4 flex items-center gap-2">
                            <Clock className="w-5 h-5 text-slate-400" />
                            Resúmenes Guardados
                        </h2>
                        {loading ? (
                            <div className="flex items-center justify-center py-12 text-slate-500">
                                <Loader2 className="w-6 h-6 animate-spin mr-2" /> Cargando historial...
                            </div>
                        ) : history.length === 0 ? (
                            <div className="text-center py-16 bg-slate-50 rounded-lg border border-dashed border-slate-300">
                                <FileWarning className="w-12 h-12 text-slate-400 mx-auto mb-3" />
                                <h3 className="text-lg font-medium text-slate-900">No hay resúmenes</h3>
                                <p className="text-slate-500 mt-1 max-w-sm mx-auto">Genera tu primer resumen mensual seleccionando archivos de observaciones diarias.</p>
                            </div>
                        ) : (
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                {history.map((entry, i) => (
                                    <div key={i} className="border border-slate-200 rounded-xl p-5 hover:shadow-md transition-all hover:border-blue-300 group cursor-pointer"
                                         onClick={() => handleLoadSummary(entry.path)}>
                                        <div className="flex justify-between items-start mb-2">
                                            <div className="bg-blue-50 text-blue-700 text-xs font-bold px-2 py-1 rounded">
                                                {entry.period}
                                            </div>
                                            <ArrowRight className="w-4 h-4 text-slate-300 group-hover:text-blue-500 transition-colors" />
                                        </div>
                                        <h3 className="text-lg font-bold text-slate-800 mt-2">{entry.station}</h3>
                                        <p className="text-xs text-slate-500 mt-3 truncate" title={entry.path}>
                                            {entry.path.split(/[/\\]/).pop()}
                                        </p>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {activeTab === 'view' && currentDoc && (
                    <div className="flex flex-col h-full">
                        <div className="p-5 border-b border-slate-200 bg-slate-50 flex justify-between items-center shrink-0">
                            <div>
                                <h2 className="text-xl font-bold text-slate-800">
                                    Estación {currentDoc.meta.estacion}
                                </h2>
                                <p className="text-sm text-slate-500 flex gap-4 mt-1">
                                    <span>Período: <span className="font-semibold text-slate-700">{currentDoc.meta.periodo}</span></span>
                                    <span>Días analizados: <span className="font-semibold text-slate-700">{currentDoc.meta.total_dias}</span></span>
                                    <span>Generado: {new Date(currentDoc.meta.generado).toLocaleString()}</span>
                                </p>
                            </div>
                            <button
                                onClick={handleExportExcel}
                                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-medium transition-all shadow-sm flex items-center gap-2"
                            >
                                <FileSpreadsheet className="w-4 h-4" />
                                Exportar Excel
                            </button>
                        </div>
                        
                        {/* Table wrapper with scrolling */}
                        <div className="flex-1 overflow-auto bg-white">
                            <table className="min-w-full divide-y divide-slate-200">
                                <thead>
                                    <tr>
                                        <TableHeader>Día</TableHeader>
                                        <TableHeader>P.Est Media</TableHeader>
                                        <TableHeader>P.Est Max</TableHeader>
                                        <TableHeader>P.Est Min</TableHeader>
                                        <TableHeader>P.NMM Media</TableHeader>
                                        <TableHeader>P.NMM Max</TableHeader>
                                        <TableHeader>P.NMM Min</TableHeader>
                                        <TableHeader>Rocío Media</TableHeader>
                                        <TableHeader>T.Vapor Media</TableHeader>
                                        <TableHeader>HR Media</TableHeader>
                                        <TableHeader>HR Max</TableHeader>
                                        <TableHeader>HR Min</TableHeader>
                                        <TableHeader>Viento Dir</TableHeader>
                                        <TableHeader>Viento Vel (km/h)</TableHeader>
                                        <TableHeader>Recorrido Viento</TableHeader>
                                        <TableHeader>Viento Max Dir</TableHeader>
                                        <TableHeader>Nub Día</TableHeader>
                                        <TableHeader>Nub Tarde</TableHeader>
                                        <TableHeader>Nub Media</TableHeader>
                                        <TableHeader>T Max</TableHeader>
                                        <TableHeader>T Min</TableHeader>
                                        <TableHeader>T Media</TableHeader>
                                        <TableHeader>Lluvia (mm)</TableHeader>
                                    </tr>
                                </thead>
                                <tbody className="bg-white divide-y divide-slate-100">
                                    {currentDoc.datos.map((row, idx) => (
                                        <tr key={idx} className="hover:bg-slate-50 transition-colors">
                                            <TableCell><strong>{row['Dias']}</strong></TableCell>
                                            <TableCell isNumeric>{row['Presión Estación (media)']}</TableCell>
                                            <TableCell isNumeric>{row['Presión Estación (max)']}</TableCell>
                                            <TableCell isNumeric>{row['Presión Estación (min)']}</TableCell>
                                            <TableCell isNumeric>{row['Presión NMM (media)']}</TableCell>
                                            <TableCell isNumeric>{row['Presión NMM (max)']}</TableCell>
                                            <TableCell isNumeric>{row['Presión NMM (min)']}</TableCell>
                                            <TableCell isNumeric>{row['Punto de Rocío (media)']}</TableCell>
                                            <TableCell isNumeric>{row['Tensión Vapor (media)']}</TableCell>
                                            <TableCell isNumeric>{row['HR (media)']}</TableCell>
                                            <TableCell isNumeric>{row['HR (max)']}</TableCell>
                                            <TableCell isNumeric>{row['HR (min)']}</TableCell>
                                            <TableCell>{row['Viento Dir (moda)']}</TableCell>
                                            <TableCell isNumeric>{row['Viento Vel (media)']}</TableCell>
                                            <TableCell isNumeric>{row['Recorrido del Viento']}</TableCell>
                                            <TableCell>{row['Viento max y dir']}</TableCell>
                                            <TableCell isNumeric>{row['Nubosidad Día (media)']}</TableCell>
                                            <TableCell isNumeric>{row['Nubosidad Tarde (media)']}</TableCell>
                                            <TableCell isNumeric>{row['Media de nubosidad']}</TableCell>
                                            <TableCell isNumeric>{row['Temp Máxima']}</TableCell>
                                            <TableCell isNumeric>{row['Temp Mínima']}</TableCell>
                                            <TableCell isNumeric>{row['Temp. Media']}</TableCell>
                                            <TableCell isNumeric>
                                                {row['Lluvia (mm)'] !== null && row['Lluvia (mm)'] !== undefined ? (
                                                    <span className={row['Lluvia (mm)'] > 0 ? "text-blue-600 font-bold" : "text-slate-400"}>
                                                        {row['Lluvia (mm)']}
                                                    </span>
                                                ) : '-'}
                                            </TableCell>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default SummaryPage;
