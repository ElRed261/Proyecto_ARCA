import React, { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { open as openDialog, save as saveDialog, ask } from '@tauri-apps/plugin-dialog';
import { FileSpreadsheet, FileJson, Download, Plus, Clock, FileWarning, Loader2, ArrowRight, Trash2, BarChart3, Sun, Cloud, Wind, Droplets, Thermometer, Gauge, ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { ResponsiveContainer, LineChart, Line, BarChart, Bar, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';
import html2canvas from 'html2canvas';
import { jsPDF } from 'jspdf';
import { normalizeRoles, hasRole } from '../../../shared/utils/auth';


const SummaryPage = () => {
    const navigate = useNavigate();
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(false);
    const [processing, setProcessing] = useState(false);
    
    const [currentDoc, setCurrentDoc] = useState(null);
    const [activeTab, setActiveTab] = useState('history'); // 'history' | 'table' | 'charts'
    const [chartGroup, setChartGroup] = useState('temp'); // 'temp' | 'pressure' | 'humidity' | 'wind' | 'rain' | 'clouds'

    // Process data for charts
    const chartData = currentDoc ? currentDoc.datos.map(row => {
        const dayLabel = row['Dias'] ? row['Dias'].split('-').pop() : '';
        return {
            name: `Día ${dayLabel}`,
            // Temp
            tempMax: parseFloat(row['Mayor temperatura máxima']) || null,
            tempMin: parseFloat(row['Menor temperatura minima']) || null,
            tempMedia: parseFloat(row['Media temperatura']) || null,
            // Presion
            presNmmMax: parseFloat(row['MAxima presión nivel medio del mar']) || null,
            presNmmMin: parseFloat(row['Minima presión nivel medio del mar']) || null,
            presNmmMedia: parseFloat(row['Media presión nivel medio del mar']) || null,
            presEstMedia: parseFloat(row['Media presion en la estación']) || null,
            // Lluvia
            lluvia: parseFloat(row['Lluvia']) || 0,
            // Humedad
            hrMax: parseFloat(row['Humedad maxima']) || null,
            hrMin: parseFloat(row['Humedad minima']) || null,
            hrMedia: parseFloat(row['Humedad media']) || null,
            rocio: parseFloat(row['Punto de rocio']) || null,
            tVapor: parseFloat(row['Tensión de vapor']) || null,
            // Viento
            vientoVel: parseFloat(row['Velocidad media del viento']) || null,
            vientoRecorrido: parseFloat(row['Recorrido del viento']) || null,
            // Nubosidad
            nubDia: parseFloat(row['Nuvocidad dia']) || null,
            nubNoche: parseFloat(row['Nuvocidad noche']) || null,
            nubMedia: parseFloat(row['Media de nuvocidad']) || null,
        };
    }) : [];

    const getSummaryStats = () => {
        if (!currentDoc || currentDoc.datos.length === 0) return {};
        
        const datos = currentDoc.datos;
        
        // Temperatures
        const tempMaxs = datos.map(r => parseFloat(r['Mayor temperatura máxima'])).filter(v => !isNaN(v));
        const tempMins = datos.map(r => parseFloat(r['Menor temperatura minima'])).filter(v => !isNaN(v));
        const tempMedias = datos.map(r => parseFloat(r['Media temperatura'])).filter(v => !isNaN(v));
        
        const maxTemp = tempMaxs.length > 0 ? Math.max(...tempMaxs) : null;
        const minTemp = tempMins.length > 0 ? Math.min(...tempMins) : null;
        const avgTemp = tempMedias.length > 0 ? (tempMedias.reduce((a, b) => a + b, 0) / tempMedias.length) : null;
        
        // Pressures
        const presNmmMaxs = datos.map(r => parseFloat(r['MAxima presión nivel medio del mar'])).filter(v => !isNaN(v));
        const presNmmMins = datos.map(r => parseFloat(r['Minima presión nivel medio del mar'])).filter(v => !isNaN(v));
        const presEstMedias = datos.map(r => parseFloat(r['Media presion en la estación'])).filter(v => !isNaN(v));
        
        const maxPres = presNmmMaxs.length > 0 ? Math.max(...presNmmMaxs) : null;
        const minPres = presNmmMins.length > 0 ? Math.min(...presNmmMins) : null;
        const avgPresEst = presEstMedias.length > 0 ? (presEstMedias.reduce((a, b) => a + b, 0) / presEstMedias.length) : null;
        
        // Humidity & Dew point
        const hrMaxs = datos.map(r => parseFloat(r['Humedad maxima'])).filter(v => !isNaN(v));
        const hrMins = datos.map(r => parseFloat(r['Humedad minima'])).filter(v => !isNaN(v));
        const rocios = datos.map(r => parseFloat(r['Punto de rocio'])).filter(v => !isNaN(v));
        
        const maxHr = hrMaxs.length > 0 ? Math.max(...hrMaxs) : null;
        const minHr = hrMins.length > 0 ? Math.min(...hrMins) : null;
        const avgRocio = rocios.length > 0 ? (rocios.reduce((a, b) => a + b, 0) / rocios.length) : null;
        
        // Wind
        const vientoVels = datos.map(r => parseFloat(r['Velocidad media del viento'])).filter(v => !isNaN(v));
        const vientoRecorridos = datos.map(r => parseFloat(r['Recorrido del viento'])).filter(v => !isNaN(v));
        
        const maxVientoVel = vientoVels.length > 0 ? Math.max(...vientoVels) : null;
        const avgVientoVel = vientoVels.length > 0 ? (vientoVels.reduce((a, b) => a + b, 0) / vientoVels.length) : null;
        const totalRecorrido = vientoRecorridos.length > 0 ? vientoRecorridos.reduce((a, b) => a + b, 0) : null;
        
        // Rain
        const lluvias = datos.map(r => parseFloat(r['Lluvia'])).filter(v => !isNaN(v));
        const totalLluvia = lluvias.reduce((a, b) => a + b, 0);
        const maxLluvia = lluvias.length > 0 ? Math.max(...lluvias) : 0;
        const diasLluvia = lluvias.filter(v => v > 0).length;
        
        // Cloudiness
        const nubsDia = datos.map(r => parseFloat(r['Nuvocidad dia'])).filter(v => !isNaN(v));
        const nubsNoche = datos.map(r => parseFloat(r['Nuvocidad noche'])).filter(v => !isNaN(v));
        const nubsMedia = datos.map(r => parseFloat(r['Media de nuvocidad'])).filter(v => !isNaN(v));
        
        const avgNubDia = nubsDia.length > 0 ? (nubsDia.reduce((a, b) => a + b, 0) / nubsDia.length) : null;
        const avgNubNoche = nubsNoche.length > 0 ? (nubsNoche.reduce((a, b) => a + b, 0) / nubsNoche.length) : null;
        const avgNubMedia = nubsMedia.length > 0 ? (nubsMedia.reduce((a, b) => a + b, 0) / nubsMedia.length) : null;
        
        return {
            maxTemp, minTemp, avgTemp,
            maxPres, minPres, avgPresEst,
            maxHr, minHr, avgRocio,
            maxVientoVel, avgVientoVel, totalRecorrido,
            totalLluvia, maxLluvia, diasLluvia,
            avgNubDia, avgNubNoche, avgNubMedia
        };
    };

    const stats = getSummaryStats();

    // Station and period loader state
    const [stations, setStations] = useState({});
    const [selectedStation, setSelectedStation] = useState('');
    const [selectedYear, setSelectedYear] = useState(() => new Date().getFullYear());
    const [selectedMonth, setSelectedMonth] = useState(() => new Date().getMonth() + 1); // 1-12
    const [currentUserRoles, setCurrentUserRoles] = useState([]);
    const [includeCorrections, setIncludeCorrections] = useState(false);

    const getStationName = (code) => {
        if (!code) return "";
        return stations[code]?.name || `Estación ${code}`;
    };

    const canSeeCorrections = hasRole(currentUserRoles, ['admin', 'control_calidad']);

    useEffect(() => {
        const initialize = async () => {
            setLoading(true);
            try {
                // Fetch stations list
                const stationData = await invoke('get_stations');
                setStations(stationData);
                const keys = Object.keys(stationData);
                if (keys.length > 0) {
                    setSelectedStation(keys[0]);
                }

                // Get user roles
                const savedRoles = localStorage.getItem('user_roles');
                if (savedRoles) {
                    setCurrentUserRoles(normalizeRoles(savedRoles));
                }
            } catch (error) {
                console.error("Error loading stations and roles:", error);
            }
            await fetchHistory();
            setLoading(false);
        };
        initialize();
    }, []);

    const fetchHistory = async () => {
        try {
            const data = await invoke('ms_list_history');
            setHistory(data);
        } catch (error) {
            console.error("Error fetching history:", error);
            toast.error("Error cargando historial de resúmenes");
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
            setActiveTab('table');
            toast.success("Resumen generado exitosamente");
            fetchHistory(); // Refresh history
        } catch (error) {
            console.error("Generate error:", error);
            toast.error(error.toString() || "Error al procesar archivos");
        } finally {
            setProcessing(false);
        }
    };

    const handleLoadStationMonth = async () => {
        if (!selectedStation) {
            toast.error("Debe seleccionar una estación");
            return;
        }
        setProcessing(true);
        try {
            const command = (includeCorrections && canSeeCorrections)
                ? 'ms_load_station_month_with_corrections'
                : 'ms_load_station_month';

            const doc = await invoke(command, {
                stationCode: selectedStation,
                year: parseInt(selectedYear, 10),
                month: parseInt(selectedMonth, 10)
            });
            setCurrentDoc(doc);
            setActiveTab('table');
            toast.success("Resumen de estación generado exitosamente");
            fetchHistory(); // Refresh history
        } catch (error) {
            console.error("Load station month error:", error);
            toast.error(error.toString() || "No se encontraron datos para la estación y período seleccionados");
        } finally {
            setProcessing(false);
        }
    };

    const handleLoadSummary = async (path) => {
        setLoading(true);
        try {
            const doc = await invoke('ms_load_summary', { path });
            setCurrentDoc(doc);
            setActiveTab('table');
            toast.success("Resumen cargado");
        } catch (error) {
            console.error("Load error:", error);
            toast.error("Error al cargar el resumen");
        } finally {
            setLoading(false);
        }
    };

    const handleDeleteSummary = async (e, entry) => {
        e.stopPropagation(); // Prevent loading the summary when clicking delete
        
        const firstConfirm = await ask(`¿Está seguro que desea enviar a la papelera el resumen generado para la estación "${getStationName(entry.station)}" del período "${entry.period}"?`, {
            title: 'Enviar a la papelera',
            kind: 'warning',
        });
        if (!firstConfirm) return;
        
        const secondConfirm = await ask(`¡ATENCIÓN! ¿Confirma la acción para "${getStationName(entry.station)}" - "${entry.period}"?`, {
            title: 'Confirmar eliminación',
            kind: 'warning',
        });
        if (!secondConfirm) return;
        
        try {
            await invoke('ms_delete_summary', { path: entry.path });
            toast.success("Resumen enviado a la papelera exitosamente");
            if (currentDoc && currentDoc.path === entry.path) {
                setCurrentDoc(null);
                setActiveTab('history');
            }
            fetchHistory();
        } catch (error) {
            console.error("Delete error:", error);
            toast.error("Error al eliminar el resumen");
        }
    };

    const handleExportExcel = async () => {
        if (!currentDoc) return;
        try {
            const safeStation = currentDoc.meta.estacion.replace(/[/\\]/g, '_');
            const safePeriod = currentDoc.meta.periodo.replace(/[/\\]/g, '');
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

    const [exportingPDF, setExportingPDF] = useState(false);

    const handleExportChartsPDF = async () => {
        if (!currentDoc) return;
        setExportingPDF(true);
        const toastId = toast.loading("Generando reporte de gráficos en PDF...");
        
        try {
            const pdf = new jsPDF({
                orientation: 'landscape',
                unit: 'px',
                format: [800, 600]
            });
            
            const chartIds = [
                { id: 'chart-pdf-temp', title: 'Gráfico de Temperatura (°C)' },
                { id: 'chart-pdf-pressure', title: 'Gráfico de Presión Atmosférica (hPa)' },
                { id: 'chart-pdf-humidity', title: 'Gráfico de Humedad (%) y Punto de Rocío (°C)' },
                { id: 'chart-pdf-rain', title: 'Gráfico de Precipitación Diaria (mm)' },
                { id: 'chart-pdf-wind', title: 'Gráfico de Velocidad del Viento (km/h)' },
                { id: 'chart-pdf-clouds', title: 'Gráfico de Nubosidad Total (Octas)' }
            ];

            for (let i = 0; i < chartIds.length; i++) {
                const item = chartIds[i];
                const element = document.getElementById(item.id);
                if (!element) continue;

                // Capturar canvas del elemento
                const canvas = await html2canvas(element, {
                    scale: 2, // Mayor calidad
                    logging: false,
                    useCORS: true
                });

                const imgData = canvas.toDataURL('image/png');
                
                // Agregar encabezado a la página del PDF
                pdf.setFontSize(14);
                pdf.setFont("helvetica", "bold");
                pdf.setTextColor(30, 41, 59); // Slate-800
                pdf.text(`Estación: ${getStationName(currentDoc.meta.estacion)} (${currentDoc.meta.estacion})`, 40, 40);
                pdf.text(`Período: ${currentDoc.meta.periodo}`, 40, 55);
                pdf.setFontSize(12);
                pdf.setTextColor(71, 85, 105); // Slate-600
                pdf.text(item.title, 40, 75);
                
                // Agregar imagen al PDF
                pdf.addImage(imgData, 'PNG', 40, 100, 720, 420);

                if (i < chartIds.length - 1) {
                    pdf.addPage();
                }
            }

            const fileName = `Graficos_Resumen_${currentDoc.meta.estacion}_${currentDoc.meta.periodo.replace('/', '_')}.pdf`;
            pdf.save(fileName);
            toast.success("¡PDF con gráficos descargado con éxito!", { id: toastId });
        } catch (error) {
            console.error("Error al exportar gráficos a PDF:", error);
            toast.error("Error al generar PDF: " + error.toString(), { id: toastId });
        } finally {
            setExportingPDF(false);
        }
    };

    const TableHeader = ({ children }) => (
        <th className="sticky top-0 px-3 py-3 text-center text-xs font-bold text-white uppercase tracking-wider whitespace-nowrap bg-slate-800 border-b border-slate-700 z-10 border-r border-slate-700/50 last:border-r-0">
            {children}
        </th>
    );

    const TableCell = ({ children, isNumeric, className = '' }) => (
        <td className={`px-3 py-2.5 whitespace-nowrap text-sm text-slate-750 border-b border-slate-150 border-r border-slate-100 last:border-r-0 text-center ${isNumeric ? 'font-mono' : ''} ${className}`}>
            {children !== null && children !== undefined ? children : '-'}
        </td>
    );

    return (
        <div className="flex flex-col h-[calc(100vh-8rem)]">
            {/* Header section */}
            <div className="flex justify-between items-center mb-6">
                <div className="flex items-center gap-4">
                    <button
                        onClick={() => navigate('/dashboard')}
                        className="w-10 h-10 rounded-full bg-white/80 border border-slate-200/80 backdrop-blur-sm shadow-sm transition-all hover:bg-purple-50/80 hover:scale-110 flex items-center justify-center text-purple-600 focus:outline-none focus:ring-0 outline-none cursor-pointer"
                        title="Volver al Dashboard"
                    >
                        <ArrowLeft className="w-5 h-5" />
                    </button>
                    <div>
                        <h1 className="text-3xl font-bold tracking-tight text-slate-900">Resumen Mensual SYNOP</h1>
                        <p className="text-slate-500 mt-1">Generación y visualización de resúmenes climáticos</p>
                    </div>
                </div>
                <div className="flex gap-3">
                    <button
                        onClick={() => setActiveTab('history')}
                        className={`px-4 py-2 rounded-lg font-semibold text-sm transition-all flex items-center gap-2 cursor-pointer focus:outline-none focus:ring-2 focus:ring-purple-500/20 ${
                            activeTab === 'history' 
                            ? 'bg-purple-50 text-purple-700 border border-purple-200' 
                            : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
                        }`}
                    >
                        <Clock className="w-4 h-4" /> Historial
                    </button>
                    {currentDoc && (
                        <>
                            <button
                                onClick={() => setActiveTab('table')}
                                className={`px-4 py-2 rounded-lg font-semibold text-sm transition-all flex items-center gap-2 cursor-pointer focus:outline-none focus:ring-2 focus:ring-purple-500/20 ${
                                    activeTab === 'table' 
                                    ? 'bg-purple-50 text-purple-700 border border-purple-200' 
                                    : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
                            }`}
                            >
                                <FileJson className="w-4 h-4" /> Tabla de Datos
                            </button>
                            <button
                                onClick={() => setActiveTab('charts')}
                                className={`px-4 py-2 rounded-lg font-semibold text-sm transition-all flex items-center gap-2 cursor-pointer focus:outline-none focus:ring-2 focus:ring-purple-500/20 ${
                                    activeTab === 'charts' 
                                    ? 'bg-purple-50 text-purple-700 border border-purple-200' 
                                    : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
                            }`}
                            >
                                <BarChart3 className="w-4 h-4" /> Gráficos
                            </button>
                        </>
                    )}
                    <button
                        onClick={handleGenerateNew}
                        disabled={processing}
                        className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-semibold text-sm transition-all shadow-sm flex items-center gap-2 disabled:opacity-50 cursor-pointer focus:outline-none focus:ring-2 focus:ring-purple-500/50"
                    >
                        {processing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                        Generar Manual
                    </button>
                </div>
            </div>

            {/* Content section */}
            <div className="bg-white border border-slate-200 rounded-xl shadow-sm flex-1 overflow-hidden flex flex-col">
                {activeTab === 'history' && (
                    <div className="p-6 overflow-y-auto flex-1">
                        {/* Auto selector card */}
                        {/* Auto selector card */}
                        <div className="bg-gradient-to-br from-purple-50 via-indigo-50/20 to-purple-50/50 border border-purple-100 rounded-2xl p-6 mb-8 shadow-sm relative overflow-hidden text-slate-800">
                            <div className="absolute top-0 right-0 w-64 h-64 bg-purple-200/20 rounded-full blur-3xl pointer-events-none"></div>
                            <h3 className="text-xs font-bold uppercase tracking-wider text-purple-700 mb-4 flex items-center gap-2">
                                <Gauge className="w-4 h-4 text-purple-600 animate-pulse" /> Carga automática por Estación y Período
                            </h3>
                            <div className="flex flex-wrap gap-4 items-end">
                                <div className="flex-1 min-w-[200px]">
                                    <label className="block text-xs font-semibold text-slate-500 mb-1.5">Estación Meteorológica</label>
                                    <select
                                        value={selectedStation}
                                        onChange={(e) => setSelectedStation(e.target.value)}
                                        className="w-full px-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 transition-all font-medium text-slate-700"
                                    >
                                        <option value="">Seleccionar...</option>
                                        {Object.entries(stations).map(([id, info]) => (
                                            <option key={id} value={id}>
                                                {info.name || `Estación ${id}`}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                                
                                <div className="w-[150px]">
                                    <label className="block text-xs font-semibold text-slate-500 mb-1.5">Mes</label>
                                    <select
                                        value={selectedMonth}
                                        onChange={(e) => setSelectedMonth(e.target.value)}
                                        className="w-full px-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 transition-all font-medium text-slate-700"
                                    >
                                        <option value="1">Enero</option>
                                        <option value="2">Febrero</option>
                                        <option value="3">Marzo</option>
                                        <option value="4">Abril</option>
                                        <option value="5">Mayo</option>
                                        <option value="6">Junio</option>
                                        <option value="7">Julio</option>
                                        <option value="8">Agosto</option>
                                        <option value="9">Septiembre</option>
                                        <option value="10">Octubre</option>
                                        <option value="11">Noviembre</option>
                                        <option value="12">Diciembre</option>
                                    </select>
                                </div>
                                
                                <div className="w-[120px]">
                                    <label className="block text-xs font-semibold text-slate-500 mb-1.5">Año</label>
                                    <select
                                        value={selectedYear}
                                        onChange={(e) => setSelectedYear(e.target.value)}
                                        className="w-full px-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/20 focus:border-purple-500 transition-all font-medium text-slate-700"
                                    >
                                        {Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - i).map(year => (
                                            <option key={year} value={year}>{year}</option>
                                        ))}
                                    </select>
                                </div>

                                {canSeeCorrections && (
                                    <div className="flex items-center gap-2 mb-2 self-end h-[42px] px-2">
                                        <input
                                            type="checkbox"
                                            id="includeCorr"
                                            checked={includeCorrections}
                                            onChange={(e) => setIncludeCorrections(e.target.checked)}
                                            className="w-4.5 h-4.5 text-purple-600 border-slate-300 rounded focus:ring-purple-500 transition cursor-pointer"
                                        />
                                        <label htmlFor="includeCorr" className="text-xs font-bold text-slate-700 cursor-pointer select-none">
                                            Incluir correcciones (overlay)
                                        </label>
                                    </div>
                                )}
                                
                                <button
                                    onClick={handleLoadStationMonth}
                                    disabled={processing || !selectedStation}
                                    className="px-6 py-2.5 bg-purple-600 hover:bg-purple-750 disabled:bg-slate-100 text-white disabled:text-slate-400 rounded-xl font-semibold text-sm transition-all shadow-sm hover:shadow-md flex items-center justify-center gap-2 h-[42px] disabled:cursor-not-allowed cursor-pointer border border-purple-500 disabled:border-slate-200 focus:outline-none focus:ring-2 focus:ring-purple-500/50"
                                >
                                    {processing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                                    Cargar Mes
                                </button>
                            </div>
                        </div>

                        <h2 className="text-xl font-black text-slate-800 mb-5 flex items-center gap-2.5">
                            <Clock className="w-5 h-5 text-purple-600" />
                            Historial de Reportes Guardados
                        </h2>

                        {loading ? (
                            <div className="flex items-center justify-center py-16 text-slate-500">
                                <Loader2 className="w-6 h-6 animate-spin mr-3 text-purple-600" /> Cargando historial...
                            </div>
                        ) : history.length === 0 ? (
                            <div className="text-center py-20 bg-slate-50/50 rounded-2xl border border-dashed border-slate-200">
                                <FileWarning className="w-12 h-12 text-slate-400 mx-auto mb-4" />
                                <h3 className="text-lg font-bold text-slate-900">No hay resúmenes</h3>
                                <p className="text-slate-500 mt-2 max-w-sm mx-auto text-sm">Selecciona una estación y un período arriba para generar tu primer resumen mensual, o importa archivos manualmente.</p>
                            </div>
                        ) : (
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                {history.map((entry, i) => (
                                    <div key={i} className="bg-gradient-to-br from-white to-slate-50/40 border border-slate-200/80 rounded-2xl p-5 shadow-sm hover:shadow-md hover:border-purple-400 group cursor-pointer transition-all duration-300 hover:-translate-y-1"
                                         onClick={() => handleLoadSummary(entry.path)}>
                                        <div className="flex justify-between items-start mb-3">
                                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold bg-purple-50 text-purple-700 border border-purple-100">
                                                <Clock className="w-3 h-3 text-purple-500" /> {entry.period}
                                            </span>
                                            <div className="flex items-center gap-1.5 opacity-60 group-hover:opacity-100 transition-opacity">
                                                <button 
                                                    onClick={(e) => handleDeleteSummary(e, entry)}
                                                    className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-red-500/30"
                                                    title="Eliminar resumen"
                                                >
                                                    <Trash2 className="w-4 h-4" />
                                                </button>
                                                <span className="p-1.5 text-slate-400 group-hover:text-purple-600 transition-colors">
                                                    <ArrowRight className="w-4 h-4" />
                                                </span>
                                            </div>
                                        </div>
                                        <h3 className="text-lg font-black text-slate-800 mt-2 flex items-center gap-2">
                                            <div className="w-2 h-2 bg-purple-650 rounded-full animate-pulse"></div>
                                            {getStationName(entry.station)}
                                        </h3>
                                        <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
                                            <span className="text-[11px] font-medium text-slate-400 font-mono truncate max-w-[200px]" title={entry.path}>
                                                {entry.path.split(/[/\\]/).pop()}
                                            </span>
                                            <span className="text-[10px] font-bold uppercase text-slate-400 tracking-wider">SYNOP</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {activeTab === 'table' && currentDoc && (
                    <div className="flex flex-col h-full overflow-hidden">
                        <div className="p-5 border-b border-slate-200 bg-slate-50 flex justify-between items-center shrink-0">
                            <div>
                                <h2 className="text-xl font-bold text-slate-850">
                                    Estación {getStationName(currentDoc.meta.estacion)}
                                </h2>
                                <p className="text-sm text-slate-500 flex gap-4 mt-1">
                                    <span>Período: <span className="font-semibold text-slate-700">{currentDoc.meta.periodo}</span></span>
                                    <span>Días analizados: <span className="font-semibold text-slate-700">{currentDoc.meta.total_dias}</span></span>
                                    <span>Generado: {new Date(currentDoc.meta.generado).toLocaleString()}</span>
                                </p>
                            </div>
                            <button
                                onClick={handleExportExcel}
                                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-semibold text-sm transition-all shadow-sm flex items-center gap-2 cursor-pointer focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
                            >
                                <FileSpreadsheet className="w-4 h-4" />
                                Exportar Excel
                            </button>
                        </div>
                        
                        {/* Table wrapper with scrolling */}
                        <div className="flex-1 overflow-auto bg-white relative">
                            <table className="min-w-full divide-y divide-slate-200 border-separate border-spacing-0">
                                <thead>
                                    <tr>
                                        <TableHeader>Día</TableHeader>
                                        <TableHeader>T Max</TableHeader>
                                        <TableHeader>T Min</TableHeader>
                                        <TableHeader>T Media</TableHeader>
                                        <TableHeader>P.NMM Max</TableHeader>
                                        <TableHeader>P.NMM Min</TableHeader>
                                        <TableHeader>P.NMM Media</TableHeader>
                                        <TableHeader>P.Est Media</TableHeader>
                                        <TableHeader>Lluvia (mm)</TableHeader>
                                        <TableHeader>Viento Dir</TableHeader>
                                        <TableHeader>Viento Vel (km/h)</TableHeader>
                                        <TableHeader>Viento Máx Dir</TableHeader>
                                        <TableHeader>Recorrido Viento</TableHeader>
                                        <TableHeader>Nub Día</TableHeader>
                                        <TableHeader>Nub Tarde</TableHeader>
                                        <TableHeader>Nub Media</TableHeader>
                                        <TableHeader>HR Max</TableHeader>
                                        <TableHeader>HR Min</TableHeader>
                                        <TableHeader>HR Media</TableHeader>
                                        <TableHeader>Rocío Media</TableHeader>
                                        <TableHeader>T.Vapor Media</TableHeader>
                                    </tr>
                                </thead>
                                <tbody className="bg-white divide-y divide-slate-100">
                                    {currentDoc.datos.map((row, idx) => {
                                        const rainVal = parseFloat(row['Lluvia']);
                                        const isRainy = !isNaN(rainVal) && rainVal > 0;
                                        return (
                                            <tr key={idx} className="odd:bg-white even:bg-slate-50/20 hover:bg-purple-50/20 transition-colors">
                                                <TableCell className="font-bold text-slate-800 bg-slate-50/40">
                                                    {row['Dias'] ? row['Dias'].split('-').pop() : ''}
                                                </TableCell>
                                                <TableCell isNumeric className="bg-red-50/20 text-red-750 font-semibold">{row['Mayor temperatura máxima']}</TableCell>
                                                <TableCell isNumeric className="bg-blue-50/20 text-blue-750 font-semibold">{row['Menor temperatura minima']}</TableCell>
                                                <TableCell isNumeric className="bg-amber-50/10 text-amber-850">{row['Media temperatura']}</TableCell>
                                                <TableCell isNumeric>{row['MAxima presión nivel medio del mar']}</TableCell>
                                                <TableCell isNumeric>{row['Minima presión nivel medio del mar']}</TableCell>
                                                <TableCell isNumeric className="bg-indigo-50/10 text-indigo-850">{row['Media presión nivel medio del mar']}</TableCell>
                                                <TableCell isNumeric>{row['Media presion en la estación']}</TableCell>
                                                <TableCell isNumeric className={isRainy ? "bg-blue-550/15 text-blue-750 font-bold" : "text-slate-400"}>
                                                    {row['Lluvia']}
                                                </TableCell>
                                                <TableCell className="font-semibold text-slate-600">{row['Dirección del viento']}</TableCell>
                                                <TableCell isNumeric>{row['Velocidad media del viento']}</TableCell>
                                                <TableCell className="text-xs text-slate-600">{row['Velocidad máxima y direccion']}</TableCell>
                                                <TableCell isNumeric>{row['Recorrido del viento']}</TableCell>
                                                <TableCell isNumeric>{row['Nuvocidad dia']}</TableCell>
                                                <TableCell isNumeric>{row['Nuvocidad noche']}</TableCell>
                                                <TableCell isNumeric className="bg-amber-50/15 text-amber-900 font-semibold">{row['Media de nuvocidad']}</TableCell>
                                                <TableCell isNumeric className="text-slate-500">{row['Humedad maxima']}</TableCell>
                                                <TableCell isNumeric className="text-slate-500">{row['Humedad minima']}</TableCell>
                                                <TableCell isNumeric className="bg-teal-50/10 text-teal-850 font-semibold">{row['Humedad media']}</TableCell>
                                                <TableCell isNumeric>{row['Punto de rocio']}</TableCell>
                                                <TableCell isNumeric>{row['Tensión de vapor']}</TableCell>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {activeTab === 'charts' && currentDoc && (
                    <div className="flex flex-col md:flex-row h-full overflow-hidden">
                        {/* Chart tabs sidebar */}
                        <div className="w-full md:w-64 border-r border-slate-200 bg-slate-50 p-4 flex flex-col gap-2 shrink-0 overflow-y-auto">
                            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2 px-2">Variables</h3>
                            {[
                                { id: 'temp', label: 'Temperatura', icon: Thermometer },
                                { id: 'pressure', label: 'Presión Atmosférica', icon: Gauge },
                                { id: 'humidity', label: 'Humedad y Rocío', icon: Droplets },
                                { id: 'rain', label: 'Precipitación', icon: Cloud },
                                { id: 'wind', label: 'Viento', icon: Wind },
                                { id: 'clouds', label: 'Nubosidad', icon: Cloud }
                            ].map(group => {
                                const Icon = group.icon;
                                const isSelected = chartGroup === group.id;
                                return (
                                    <button
                                        key={group.id}
                                        onClick={() => setChartGroup(group.id)}
                                        className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl font-semibold text-sm transition-all border cursor-pointer text-left focus:outline-none focus:ring-2 focus:ring-purple-500/25 ${
                                            isSelected 
                                            ? 'bg-purple-600 border-purple-600 text-white shadow-md shadow-purple-500/20' 
                                            : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
                                        }`}
                                    >
                                        <Icon className={`w-4 h-4 ${isSelected ? 'text-white' : 'text-slate-450'}`} />
                                        {group.label}
                                    </button>
                                );
                            })}
                            <div className="mt-auto pt-4 border-t border-slate-200">
                                <button
                                    onClick={handleExportChartsPDF}
                                    disabled={exportingPDF}
                                    className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl font-bold text-sm bg-purple-600 hover:bg-purple-700 text-white transition-all shadow-md shadow-purple-500/20 hover:shadow-lg disabled:opacity-50 cursor-pointer focus:outline-none focus:ring-2 focus:ring-purple-500/50"
                                >
                                    {exportingPDF ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                                    {exportingPDF ? 'Exportando...' : 'Exportar PDF'}
                                </button>
                            </div>
                        </div>

                        {/* Chart content panel */}
                        <div className="flex-1 p-6 overflow-y-auto flex flex-col gap-6 bg-slate-50/30">
                            {/* Summary cards row */}
                            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                                {chartGroup === 'temp' && (
                                    <>
                                        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm flex items-center justify-between transition-all hover:shadow-md hover:border-slate-300">
                                            <div>
                                                <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">Temp Máxima Absoluta</div>
                                                <div className="text-3xl font-black text-red-655 mt-1.5 font-mono">{stats.maxTemp !== null ? `${stats.maxTemp.toFixed(1)} °C` : '-'}</div>
                                            </div>
                                            <div className="p-3 bg-red-50 text-red-500 rounded-xl">
                                                <Sun className="w-6 h-6" />
                                            </div>
                                        </div>
                                        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm flex items-center justify-between transition-all hover:shadow-md hover:border-slate-300">
                                            <div>
                                                <div className="text-xs font-bold text-slate-455 uppercase tracking-wider">Temp Mínima Absoluta</div>
                                                <div className="text-3xl font-black text-blue-600 mt-1.5 font-mono">{stats.minTemp !== null ? `${stats.minTemp.toFixed(1)} °C` : '-'}</div>
                                            </div>
                                            <div className="p-3 bg-blue-50 text-blue-500 rounded-xl">
                                                <Thermometer className="w-6 h-6" />
                                            </div>
                                        </div>
                                        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm flex items-center justify-between transition-all hover:shadow-md hover:border-slate-300">
                                            <div>
                                                <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">Temp Promedio Mensual</div>
                                                <div className="text-3xl font-black text-slate-800 mt-1.5 font-mono">{stats.avgTemp !== null ? `${stats.avgTemp.toFixed(1)} °C` : '-'}</div>
                                            </div>
                                            <div className="p-3 bg-slate-50 text-slate-500 rounded-xl">
                                                <Sun className="w-6 h-6 text-amber-500" />
                                            </div>
                                        </div>
                                    </>
                                )}
                                {chartGroup === 'pressure' && (
                                    <>
                                        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm flex items-center justify-between transition-all hover:shadow-md hover:border-slate-300">
                                            <div>
                                                <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">Máx Presión NMM</div>
                                                <div className="text-3xl font-black text-indigo-650 mt-1.5 font-mono">{stats.maxPres !== null ? `${stats.maxPres.toFixed(1)} hPa` : '-'}</div>
                                            </div>
                                            <div className="p-3 bg-indigo-50 text-indigo-500 rounded-xl">
                                                <Gauge className="w-6 h-6" />
                                            </div>
                                        </div>
                                        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm flex items-center justify-between transition-all hover:shadow-md hover:border-slate-300">
                                            <div>
                                                <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">Mín Presión NMM</div>
                                                <div className="text-3xl font-black text-violet-600 mt-1.5 font-mono">{stats.minPres !== null ? `${stats.minPres.toFixed(1)} hPa` : '-'}</div>
                                            </div>
                                            <div className="p-3 bg-violet-50 text-violet-500 rounded-xl">
                                                <Gauge className="w-6 h-6" />
                                            </div>
                                        </div>
                                        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm flex items-center justify-between transition-all hover:shadow-md hover:border-slate-300">
                                            <div>
                                                <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">Promedio Presión Estación</div>
                                                <div className="text-3xl font-black text-slate-800 mt-1.5 font-mono">{stats.avgPresEst !== null ? `${stats.avgPresEst.toFixed(1)} hPa` : '-'}</div>
                                            </div>
                                            <div className="p-3 bg-slate-50 text-slate-500 rounded-xl">
                                                <Gauge className="w-6 h-6 text-slate-600" />
                                            </div>
                                        </div>
                                    </>
                                )}
                                {chartGroup === 'humidity' && (
                                    <>
                                        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm flex items-center justify-between transition-all hover:shadow-md hover:border-slate-300">
                                            <div>
                                                <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">Humedad Relativa Máx</div>
                                                <div className="text-3xl font-black text-teal-600 mt-1.5 font-mono">{stats.maxHr !== null ? `${stats.maxHr.toFixed(0)}%` : '-'}</div>
                                            </div>
                                            <div className="p-3 bg-teal-50 text-teal-500 rounded-xl">
                                                <Droplets className="w-6 h-6" />
                                            </div>
                                        </div>
                                        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm flex items-center justify-between transition-all hover:shadow-md hover:border-slate-300">
                                            <div>
                                                <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">Humedad Relativa Mín</div>
                                                <div className="text-3xl font-black text-cyan-600 mt-1.5 font-mono">{stats.minHr !== null ? `${stats.minHr.toFixed(0)}%` : '-'}</div>
                                            </div>
                                            <div className="p-3 bg-cyan-50 text-cyan-500 rounded-xl">
                                                <Droplets className="w-6 h-6" />
                                            </div>
                                        </div>
                                        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm flex items-center justify-between transition-all hover:shadow-md hover:border-slate-300">
                                            <div>
                                                <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">Punto de Rocío Promedio</div>
                                                <div className="text-3xl font-black text-emerald-600 mt-1.5 font-mono">{stats.avgRocio !== null ? `${stats.avgRocio.toFixed(1)} °C` : '-'}</div>
                                            </div>
                                            <div className="p-3 bg-emerald-50 text-emerald-500 rounded-xl">
                                                <Droplets className="w-6 h-6 text-emerald-600" />
                                            </div>
                                        </div>
                                    </>
                                )}
                                {chartGroup === 'rain' && (
                                    <>
                                        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm flex items-center justify-between transition-all hover:shadow-md hover:border-slate-300">
                                            <div>
                                                <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">Lluvia Total Acumulada</div>
                                                <div className="text-3xl font-black text-blue-600 mt-1.5 font-mono">{stats.totalLluvia !== null ? `${stats.totalLluvia.toFixed(1)} mm` : '-'}</div>
                                            </div>
                                            <div className="p-3 bg-blue-50 text-blue-550 rounded-xl">
                                                <Cloud className="w-6 h-6" />
                                            </div>
                                        </div>
                                        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm flex items-center justify-between transition-all hover:shadow-md hover:border-slate-300">
                                            <div>
                                                <div className="text-xs font-bold text-slate-455 uppercase tracking-wider">Máxima Lluvia Diaria</div>
                                                <div className="text-3xl font-black text-sky-600 mt-1.5 font-mono">{stats.maxLluvia !== null ? `${stats.maxLluvia.toFixed(1)} mm` : '-'}</div>
                                            </div>
                                            <div className="p-3 bg-sky-50 text-sky-500 rounded-xl">
                                                <Cloud className="w-6 h-6 text-sky-600" />
                                            </div>
                                        </div>
                                        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm flex items-center justify-between transition-all hover:shadow-md hover:border-slate-300">
                                            <div>
                                                <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">Días con Precipitación</div>
                                                <div className="text-3xl font-black text-slate-800 mt-1.5 font-mono">{stats.diasLluvia !== null ? `${stats.diasLluvia} días` : '-'}</div>
                                            </div>
                                            <div className="p-3 bg-slate-50 text-slate-500 rounded-xl">
                                                <Cloud className="w-6 h-6" />
                                            </div>
                                        </div>
                                    </>
                                )}
                                {chartGroup === 'wind' && (
                                    <>
                                        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm flex items-center justify-between transition-all hover:shadow-md hover:border-slate-300">
                                            <div>
                                                <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">Velocidad Máxima Media</div>
                                                <div className="text-3xl font-black text-cyan-600 mt-1.5 font-mono">{stats.maxVientoVel !== null ? `${stats.maxVientoVel.toFixed(1)} km/h` : '-'}</div>
                                            </div>
                                            <div className="p-3 bg-cyan-50 text-cyan-500 rounded-xl">
                                                <Wind className="w-6 h-6" />
                                            </div>
                                        </div>
                                        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm flex items-center justify-between transition-all hover:shadow-md hover:border-slate-300">
                                            <div>
                                                <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">Velocidad Promedio</div>
                                                <div className="text-3xl font-black text-teal-600 mt-1.5 font-mono">{stats.avgVientoVel !== null ? `${stats.avgVientoVel.toFixed(1)} km/h` : '-'}</div>
                                            </div>
                                            <div className="p-3 bg-teal-50 text-teal-500 rounded-xl">
                                                <Wind className="w-6 h-6" />
                                            </div>
                                        </div>
                                        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm flex items-center justify-between transition-all hover:shadow-md hover:border-slate-300">
                                            <div>
                                                <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">Recorrido Total del Viento</div>
                                                <div className="text-3xl font-black text-indigo-650 mt-1.5 font-mono">{stats.totalRecorrido !== null ? `${stats.totalRecorrido.toFixed(1)} km` : '-'}</div>
                                            </div>
                                            <div className="p-3 bg-indigo-50 text-indigo-500 rounded-xl">
                                                <Wind className="w-6 h-6 text-indigo-600" />
                                            </div>
                                        </div>
                                    </>
                                )}
                                {chartGroup === 'clouds' && (
                                    <>
                                        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm flex items-center justify-between transition-all hover:shadow-md hover:border-slate-300">
                                            <div>
                                                <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">Nubosidad Día Promedio</div>
                                                <div className="text-3xl font-black text-amber-600 mt-1.5 font-mono">{stats.avgNubDia !== null ? `${stats.avgNubDia.toFixed(1)} octas` : '-'}</div>
                                            </div>
                                            <div className="p-3 bg-amber-50 text-amber-500 rounded-xl">
                                                <Cloud className="w-6 h-6" />
                                            </div>
                                        </div>
                                        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm flex items-center justify-between transition-all hover:shadow-md hover:border-slate-300">
                                            <div>
                                                <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">Nubosidad Tarde Promedio</div>
                                                <div className="text-3xl font-black text-slate-655 mt-1.5 font-mono">{stats.avgNubNoche !== null ? `${stats.avgNubNoche.toFixed(1)} octas` : '-'}</div>
                                            </div>
                                            <div className="p-3 bg-slate-100 text-slate-500 rounded-xl">
                                                <Cloud className="w-6 h-6 text-slate-500" />
                                            </div>
                                        </div>
                                        <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm flex items-center justify-between transition-all hover:shadow-md hover:border-slate-300">
                                            <div>
                                                <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">Media Nubosidad Mensual</div>
                                                <div className="text-3xl font-black text-indigo-855 mt-1.5 font-mono">{stats.avgNubMedia !== null ? `${stats.avgNubMedia.toFixed(1)} octas` : '-'}</div>
                                            </div>
                                            <div className="p-3 bg-indigo-50 text-indigo-500 rounded-xl">
                                                <Cloud className="w-6 h-6 text-indigo-550" />
                                            </div>
                                        </div>
                                    </>
                                )}
                            </div>

                            {/* Chart box */}
                            <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm flex-1 min-h-[380px] flex flex-col">
                                <h3 className="text-sm font-bold text-slate-800 mb-4 uppercase tracking-wider">
                                    Gráfico de {chartGroup === 'temp' ? 'Temperatura (°C)' : 
                                               chartGroup === 'pressure' ? 'Presión Atmosférica (hPa)' : 
                                               chartGroup === 'humidity' ? 'Humedad (%) y Punto de Rocío (°C)' : 
                                               chartGroup === 'rain' ? 'Precipitación Diaria (mm)' : 
                                               chartGroup === 'wind' ? 'Velocidad Media del Viento (km/h)' : 
                                               'Nubosidad Total (Octas)'}
                                </h3>
                                
                                <div className="w-full flex-1 min-h-[300px]">
                                    <ResponsiveContainer width="100%" height={300}>
                                        {chartGroup === 'temp' ? (
                                            <AreaChart data={chartData}>
                                                <defs>
                                                    <linearGradient id="colorTempMax" x1="0" y1="0" x2="0" y2="1">
                                                        <stop offset="5%" stopColor="#ef4444" stopOpacity={0.2}/>
                                                        <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                                                    </linearGradient>
                                                    <linearGradient id="colorTempMin" x1="0" y1="0" x2="0" y2="1">
                                                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2}/>
                                                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                                                    </linearGradient>
                                                </defs>
                                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                                <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} tickLine={false} />
                                                <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} />
                                                <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0' }} />
                                                <Legend iconType="circle" />
                                                <Area name="Temp Máxima" type="monotone" dataKey="tempMax" stroke="#ef4444" strokeWidth={2} fillOpacity={1} fill="url(#colorTempMax)" />
                                                <Area name="Temp Mínima" type="monotone" dataKey="tempMin" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#colorTempMin)" />
                                                <Line name="Temp Media" type="monotone" dataKey="tempMedia" stroke="#f59e0b" strokeWidth={2.5} dot={{ r: 3 }} />
                                            </AreaChart>
                                        ) : chartGroup === 'pressure' ? (
                                            <LineChart data={chartData}>
                                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                                <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} tickLine={false} />
                                                <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} domain={['auto', 'auto']} />
                                                <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0' }} />
                                                <Legend iconType="circle" />
                                                <Line name="P.NMM Máx" type="monotone" dataKey="presNmmMax" stroke="#ef4444" strokeWidth={1.5} dot={false} />
                                                <Line name="P.NMM Mín" type="monotone" dataKey="presNmmMin" stroke="#3b82f6" strokeWidth={1.5} dot={false} />
                                                <Line name="P.NMM Media" type="monotone" dataKey="presNmmMedia" stroke="#8b5cf6" strokeWidth={2} dot={{ r: 2 }} />
                                                <Line name="Pres. Estación" type="monotone" dataKey="presEstMedia" stroke="#64748b" strokeWidth={1.5} strokeDasharray="5 5" dot={false} />
                                            </LineChart>
                                        ) : chartGroup === 'humidity' ? (
                                            <AreaChart data={chartData}>
                                                <defs>
                                                    <linearGradient id="colorHr" x1="0" y1="0" x2="0" y2="1">
                                                        <stop offset="5%" stopColor="#0d9488" stopOpacity={0.15}/>
                                                        <stop offset="95%" stopColor="#0d9488" stopOpacity={0}/>
                                                    </linearGradient>
                                                </defs>
                                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                                <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} tickLine={false} />
                                                <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} />
                                                <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0' }} />
                                                <Legend iconType="circle" />
                                                <Area name="HR Media (%)" type="monotone" dataKey="hrMedia" stroke="#0d9488" strokeWidth={2} fillOpacity={1} fill="url(#colorHr)" />
                                                <Line name="HR Máx (%)" type="monotone" dataKey="hrMax" stroke="#3b82f6" strokeWidth={1.5} dot={false} />
                                                <Line name="HR Mín (%)" type="monotone" dataKey="hrMin" stroke="#22d3ee" strokeWidth={1.5} dot={false} />
                                                <Line name="Pto. Rocío (°C)" type="monotone" dataKey="rocio" stroke="#10b981" strokeWidth={2} dot={{ r: 3 }} />
                                            </AreaChart>
                                        ) : chartGroup === 'rain' ? (
                                            <BarChart data={chartData}>
                                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                                <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} tickLine={false} />
                                                <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} />
                                                <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0' }} />
                                                <Legend iconType="circle" />
                                                <Bar name="Lluvia (mm)" dataKey="lluvia" fill="#3b82f6" radius={[4, 4, 0, 0]} maxBarSize={40} />
                                            </BarChart>
                                        ) : chartGroup === 'wind' ? (
                                            <LineChart data={chartData}>
                                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                                <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} tickLine={false} />
                                                <YAxis yAxisId="left" stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} />
                                                <YAxis yAxisId="right" orientation="right" stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} />
                                                <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0' }} />
                                                <Legend iconType="circle" />
                                                <Line yAxisId="left" name="Vel. Viento (km/h)" type="monotone" dataKey="vientoVel" stroke="#06b6d4" strokeWidth={2.5} dot={{ r: 3 }} />
                                                <Line yAxisId="right" name="Recorrido (km)" type="monotone" dataKey="vientoRecorrido" stroke="#6366f1" strokeWidth={1.5} dot={false} strokeDasharray="3 3" />
                                            </LineChart>
                                        ) : (
                                            <AreaChart data={chartData}>
                                                <defs>
                                                    <linearGradient id="colorClouds" x1="0" y1="0" x2="0" y2="1">
                                                        <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.15}/>
                                                        <stop offset="95%" stopColor="#f59e0b" stopOpacity={0}/>
                                                    </linearGradient>
                                                </defs>
                                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                                <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} tickLine={false} />
                                                <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} domain={[0, 8]} tickCount={9} />
                                                <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid #e2e8f0' }} />
                                                <Legend iconType="circle" />
                                                <Area name="Nub. Media" type="monotone" dataKey="nubMedia" stroke="#f59e0b" strokeWidth={2.5} fillOpacity={1} fill="url(#colorClouds)" />
                                                <Line name="Nub. Día" type="monotone" dataKey="nubDia" stroke="#3b82f6" strokeWidth={1.5} dot={{ r: 2 }} />
                                                <Line name="Nub. Tarde" type="monotone" dataKey="nubNoche" stroke="#64748b" strokeWidth={1.5} dot={{ r: 2 }} />
                                            </AreaChart>
                                        )}
                                    </ResponsiveContainer>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </div>
            {/* Contenedor oculto para exportar a PDF */}
            {currentDoc && (
                <div style={{ position: 'absolute', left: '-9999px', top: '-9999px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
                    <div id="chart-pdf-temp" style={{ width: '800px', height: '400px', backgroundColor: '#ffffff', padding: '20px' }}>
                        <h4 style={{ margin: '0 0 10px 0', fontSize: '14px', fontWeight: 'bold', color: '#1e293b' }}>Temperatura (°C)</h4>
                        <AreaChart width={760} height={350} data={chartData}>
                            <defs>
                                <linearGradient id="pdfColorTempMax" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.2}/>
                                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                                </linearGradient>
                                <linearGradient id="pdfColorTempMin" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2}/>
                                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                            <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} tickLine={false} />
                            <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} />
                            <Legend iconType="circle" />
                            <Area name="Temp Máxima" type="monotone" dataKey="tempMax" stroke="#ef4444" strokeWidth={2} fillOpacity={1} fill="url(#pdfColorTempMax)" isAnimationActive={false} />
                            <Area name="Temp Mínima" type="monotone" dataKey="tempMin" stroke="#3b82f6" strokeWidth={2} fillOpacity={1} fill="url(#pdfColorTempMin)" isAnimationActive={false} />
                            <Line name="Temp Media" type="monotone" dataKey="tempMedia" stroke="#f59e0b" strokeWidth={2.5} dot={{ r: 3 }} isAnimationActive={false} />
                        </AreaChart>
                    </div>

                    <div id="chart-pdf-pressure" style={{ width: '800px', height: '400px', backgroundColor: '#ffffff', padding: '20px' }}>
                        <h4 style={{ margin: '0 0 10px 0', fontSize: '14px', fontWeight: 'bold', color: '#1e293b' }}>Presión Atmosférica (hPa)</h4>
                        <LineChart width={760} height={350} data={chartData}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                            <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} tickLine={false} />
                            <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} domain={['auto', 'auto']} />
                            <Legend iconType="circle" />
                            <Line name="P.NMM Máx" type="monotone" dataKey="presNmmMax" stroke="#ef4444" strokeWidth={1.5} dot={false} isAnimationActive={false} />
                            <Line name="P.NMM Mín" type="monotone" dataKey="presNmmMin" stroke="#3b82f6" strokeWidth={1.5} dot={false} isAnimationActive={false} />
                            <Line name="P.NMM Media" type="monotone" dataKey="presNmmMedia" stroke="#8b5cf6" strokeWidth={2} dot={{ r: 2 }} isAnimationActive={false} />
                            <Line name="Pres. Estación" type="monotone" dataKey="presEstMedia" stroke="#64748b" strokeWidth={1.5} strokeDasharray="5 5" dot={false} isAnimationActive={false} />
                        </LineChart>
                    </div>

                    <div id="chart-pdf-humidity" style={{ width: '800px', height: '400px', backgroundColor: '#ffffff', padding: '20px' }}>
                        <h4 style={{ margin: '0 0 10px 0', fontSize: '14px', fontWeight: 'bold', color: '#1e293b' }}>Humedad (%) y Punto de Rocío (°C)</h4>
                        <AreaChart width={760} height={350} data={chartData}>
                            <defs>
                                <linearGradient id="pdfColorHr" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#0d9488" stopOpacity={0.15}/>
                                    <stop offset="95%" stopColor="#0d9488" stopOpacity={0}/>
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                            <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} tickLine={false} />
                            <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} />
                            <Legend iconType="circle" />
                            <Area name="HR Media (%)" type="monotone" dataKey="hrMedia" stroke="#0d9488" strokeWidth={2} fillOpacity={1} fill="url(#pdfColorHr)" isAnimationActive={false} />
                            <Line name="HR Máx (%)" type="monotone" dataKey="hrMax" stroke="#3b82f6" strokeWidth={1.5} dot={false} isAnimationActive={false} />
                            <Line name="HR Mín (%)" type="monotone" dataKey="hrMin" stroke="#22d3ee" strokeWidth={1.5} dot={false} isAnimationActive={false} />
                            <Line name="Pto. Rocío (°C)" type="monotone" dataKey="rocio" stroke="#10b981" strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
                        </AreaChart>
                    </div>

                    <div id="chart-pdf-rain" style={{ width: '800px', height: '400px', backgroundColor: '#ffffff', padding: '20px' }}>
                        <h4 style={{ margin: '0 0 10px 0', fontSize: '14px', fontWeight: 'bold', color: '#1e293b' }}>Precipitación Diaria (mm)</h4>
                        <BarChart width={760} height={350} data={chartData}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                            <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} tickLine={false} />
                            <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} />
                            <Legend iconType="circle" />
                            <Bar name="Lluvia (mm)" dataKey="lluvia" fill="#3b82f6" radius={[4, 4, 0, 0]} maxBarSize={40} isAnimationActive={false} />
                        </BarChart>
                    </div>

                    <div id="chart-pdf-wind" style={{ width: '800px', height: '400px', backgroundColor: '#ffffff', padding: '20px' }}>
                        <h4 style={{ margin: '0 0 10px 0', fontSize: '14px', fontWeight: 'bold', color: '#1e293b' }}>Velocidad del Viento (km/h)</h4>
                        <LineChart width={760} height={350} data={chartData}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                            <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} tickLine={false} />
                            <YAxis yAxisId="left" stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} />
                            <YAxis yAxisId="right" orientation="right" stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} />
                            <Legend iconType="circle" />
                            <Line yAxisId="left" name="Vel. Viento (km/h)" type="monotone" dataKey="vientoVel" stroke="#06b6d4" strokeWidth={2.5} dot={{ r: 3 }} isAnimationActive={false} />
                            <Line yAxisId="right" name="Recorrido (km)" type="monotone" dataKey="vientoRecorrido" stroke="#6366f1" strokeWidth={1.5} dot={false} strokeDasharray="3 3" isAnimationActive={false} />
                        </LineChart>
                    </div>

                    <div id="chart-pdf-clouds" style={{ width: '800px', height: '400px', backgroundColor: '#ffffff', padding: '20px' }}>
                        <h4 style={{ margin: '0 0 10px 0', fontSize: '14px', fontWeight: 'bold', color: '#1e293b' }}>Nubosidad Total (Octas)</h4>
                        <AreaChart width={760} height={350} data={chartData}>
                            <defs>
                                <linearGradient id="pdfColorClouds" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.15}/>
                                    <stop offset="95%" stopColor="#f59e0b" stopOpacity={0}/>
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                            <XAxis dataKey="name" stroke="#94a3b8" fontSize={11} tickLine={false} />
                            <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} domain={[0, 8]} tickCount={9} />
                            <Legend iconType="circle" />
                            <Area name="Nub. Media" type="monotone" dataKey="nubMedia" stroke="#f59e0b" strokeWidth={2.5} fillOpacity={1} fill="url(#pdfColorClouds)" isAnimationActive={false} />
                            <Line name="Nub. Día" type="monotone" dataKey="nubDia" stroke="#3b82f6" strokeWidth={1.5} dot={{ r: 2 }} isAnimationActive={false} />
                            <Line name="Nub. Tarde" type="monotone" dataKey="nubNoche" stroke="#64748b" strokeWidth={1.5} dot={{ r: 2 }} isAnimationActive={false} />
                        </AreaChart>
                    </div>
                </div>
            )}
        </div>
    );
};

export default SummaryPage;
