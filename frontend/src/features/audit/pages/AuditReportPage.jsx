import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { invoke } from '@tauri-apps/api/core';
import { 
    ArrowLeft, Printer, Search, FileText, AlertTriangle, 
    CheckCircle, Calendar, Edit3, Save, Radio
} from 'lucide-react';
import { toast } from 'react-hot-toast';

// Claves de campos legibles
const FIELD_LABELS = {
    // Grupo 2
    "meteo_2_1": "YYGGiw (Grupo 2)",
    // Grupo 4
    "meteo_4_irixhvv": "Ir iX H VV (Grupo 4)",
    "meteo_4_1": "N dd ff",
    "meteo_4_6": "7 ww W1 W2",
    // Grupo 6
    "meteo_6_0": "8Nh CL CM CH",
    "meteo_6_2": "0CS DL DM DH",
    "meteo_6_3": "1sn Tx Tx Tx",
    "meteo_6_4": "2sn Tn Tn Tn",
    "meteo_6_5": "3E j j j",
    "meteo_6_6": "5 EEEjE",
    // Grupo 8
    "meteo_8_0": "5n Fn Fn Fn",
    "meteo_8_1": "56 DL DM DH",
    "meteo_8_3": "6 RRR tr",
    "meteo_8_4": "7 R24 R24 R24 R24",
    "meteo_8_5": "8NsChs hs (1)",
    "meteo_8_6": "8NsChs hs (2)",
    "extra_8ns_1": "8NsChs hs (3)",
    "extra_8ns_2": "8NsChs hs (4)",
    "meteo_10_0": "8NsChs hs (5)",
    "meteo_10_1": "8NsChs hs (6)",
    
    // Instrumentales / Cálculos
    "ts": "Temp. Seca (Ts)",
    "th": "Temp. Húmeda (Th)",
    "let_barom": "Lectura Barométrica",
    "correc_temp": "Corrección Temp.",
    "pres_est": "Presión Estación",
    "p3": "Presión 3h (P3)",
    "p24": "Presión 24h (P24)",
    "t_max": "Temp. Máxima (Tx)",
    "t_min": "Temp. Mínima (Tn)",
    "t_max_24h": "Temp. Máxima 24h",
    "t_min_24h": "Temp. Mínima 24h",
    "correc_alt": "Corrección Altitud"
};

const AuditReportPage = () => {
    const navigate = useNavigate();
    const [loading, setLoading] = useState(false);
    const [reportRows, setReportRows] = useState([]);
    const [activeReportTab, setActiveReportTab] = useState("detailed"); // "detailed" | "person"
    const [personSummary, setPersonSummary] = useState([]);
    
    // Filtros
    const [filterStation, setFilterStation] = useState("");
    const [filterYear, setFilterYear] = useState("");
    const [filterMonth, setFilterMonth] = useState("");

    // Notas Generales del Reporte (para escribir antes de exportar a PDF)
    const [reportNotes, setReportNotes] = useState(
        "El presente informe consolida los errores y las correcciones de calidad realizadas sobre las observaciones meteorológicas en el periodo evaluado. " +
        "Las correcciones se han aplicado de forma digital mediante un overlay de base de datos local SQLite, garantizando la inmutabilidad de los registros históricos originales en formato JSON."
    );

    // Edición de notas específicas en línea
    const [editingNoteId, setEditingNoteId] = useState(null);
    const [editingNoteValue, setEditingNoteValue] = useState("");

    useEffect(() => {
        loadReport();
    }, []);

    const loadReport = async () => {
        setLoading(true);
        try {
            const stationId = filterStation ? filterStation : null;
            const year = filterYear ? filterYear : null;
            const month = filterMonth ? filterMonth : null;

            const data = await invoke('audit_get_error_report', { stationId, year, month });
            setReportRows(data || []);

            const summary = await invoke('audit_get_person_summary', { stationId, year, month });
            setPersonSummary(summary || []);
        } catch (error) {
            console.error("Error al cargar reporte:", error);
            toast.error("Error al generar reporte de inconsistencias: " + error);
        } finally {
            setLoading(false);
        }
    };

    const handleSearch = (e) => {
        e.preventDefault();
        loadReport();
    };

    const handleStartEditNote = (row) => {
        setEditingNoteId(row.error_id);
        setEditingNoteValue(row.nota || "");
    };

    const handleSaveNote = async (id) => {
        try {
            await invoke('audit_update_error_mark_note', {
                id: id,
                nota: editingNoteValue ? editingNoteValue : null
            });
            toast.success("Nota de error actualizada.");
            setEditingNoteId(null);
            
            // Actualizar fila localmente
            setReportRows(prev => prev.map(row => 
                row.error_id === id ? { ...row, nota: editingNoteValue } : row
            ));
        } catch (error) {
            toast.error("Error al guardar nota: " + error);
        }
    };

    const handlePrintPDF = () => {
        window.print();
    };

    return (
        <div className="p-6 max-w-7xl mx-auto pb-16">
            {/* Cabecera — Ocultar en Impresión */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6 print:hidden">
                <div className="flex items-center gap-4">
                    <button
                        onClick={() => navigate('/audit')}
                        className="w-10 h-10 rounded-full bg-white border border-slate-200 shadow-sm transition-all hover:bg-orange-50 hover:scale-110 flex items-center justify-center text-slate-600 cursor-pointer"
                        title="Volver a Auditoría"
                    >
                        <ArrowLeft className="w-5 h-5" />
                    </button>
                    <div>
                        <h1 className="text-2xl font-black text-slate-900">
                            Reporte de Inconsistencias
                        </h1>
                        <p className="text-slate-500 text-sm">
                            Consulta, edita notas y exporta a PDF el listado de errores detectados.
                        </p>
                    </div>
                </div>

                <button
                    onClick={handlePrintPDF}
                    className="flex items-center gap-2 bg-orange-600 hover:bg-orange-700 text-white font-bold py-2.5 px-5 rounded-xl shadow-md hover:shadow-lg transition-all duration-300 hover:scale-[1.02] cursor-pointer"
                >
                    <Printer className="w-5 h-5" />
                    Exportar Reporte a PDF
                </button>
            </div>

            {/* Bloque de Filtros — Ocultar en Impresión */}
            <form onSubmit={handleSearch} className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm mb-6 print:hidden flex flex-wrap gap-4 items-end">
                <div className="flex-1 min-w-[200px] flex flex-col gap-1.5">
                    <label className="text-xs font-bold text-slate-500 flex items-center gap-1">
                        <Radio className="w-3.5 h-3.5 text-orange-500" />
                        Código de Estación
                    </label>
                    <input 
                        type="text" 
                        value={filterStation}
                        onChange={(e) => setFilterStation(e.target.value)}
                        placeholder="Ej: 78484 (Opcional)"
                        className="bg-slate-50 border border-slate-200 text-slate-800 text-sm px-3 py-2 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-500"
                    />
                </div>

                <div className="w-[120px] flex flex-col gap-1.5">
                    <label className="text-xs font-bold text-slate-500">Año (YYYY)</label>
                    <input 
                        type="text" 
                        value={filterYear}
                        onChange={(e) => setFilterYear(e.target.value)}
                        placeholder="2026"
                        className="bg-slate-50 border border-slate-200 text-slate-800 text-sm px-3 py-2 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-500 text-center font-mono"
                    />
                </div>

                <div className="w-[120px] flex flex-col gap-1.5">
                    <label className="text-xs font-bold text-slate-500">Mes (MM)</label>
                    <select
                        value={filterMonth}
                        onChange={(e) => setFilterMonth(e.target.value)}
                        className="bg-slate-50 border border-slate-200 text-slate-800 text-sm px-3 py-2 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-500 text-center"
                    >
                        <option value="">(Todos)</option>
                        <option value="01">Enero</option>
                        <option value="02">Febrero</option>
                        <option value="03">Marzo</option>
                        <option value="04">Abril</option>
                        <option value="05">Mayo</option>
                        <option value="06">Junio</option>
                        <option value="07">Julio</option>
                        <option value="08">Agosto</option>
                        <option value="09">Septiembre</option>
                        <option value="10">Octubre</option>
                        <option value="11">Noviembre</option>
                        <option value="12">Diciembre</option>
                    </select>
                </div>

                <button
                    type="submit"
                    className="bg-slate-900 hover:bg-slate-800 text-white font-bold py-2 px-5 rounded-xl text-sm transition-colors flex items-center gap-1.5 h-[38px] cursor-pointer"
                >
                    <Search className="w-4 h-4" />
                    Filtrar
                </button>
            </form>

            {/* SECCIÓN DEL INFORME (MEMBRETE DE IMPRESIÓN Y CONTENIDO) */}
            <div className="bg-white border border-slate-200 rounded-3xl p-8 shadow-sm print:shadow-none print:border-none print:p-0">
                
                {/* Membrete exclusivo para PDF/Impresión */}
                <div className="hidden print:flex flex-col gap-2 border-b-2 border-orange-600 pb-4 mb-6">
                    <div className="flex justify-between items-start">
                        <div>
                            <span className="text-[10px] font-bold text-orange-600 uppercase tracking-widest block">Proyecto ARCA</span>
                            <h1 className="text-3xl font-black text-slate-900 tracking-tight">Reporte de Auditoría Meteorológica</h1>
                            <p className="text-xs text-slate-500">Sistema ERP de Consistencia de Datos Climatológicos</p>
                        </div>
                        <div className="text-right text-xs text-slate-400 font-mono">
                            <div>Fecha Impresión: {new Date().toLocaleDateString()}</div>
                            <div>Hora: {new Date().toLocaleTimeString()}</div>
                        </div>
                    </div>
                </div>

                {/* Notas generales (redactables antes de exportar) */}
                <div className="mb-8 space-y-2">
                    <h3 className="text-sm font-bold text-slate-500 uppercase tracking-wider print:text-slate-800 flex items-center gap-1">
                        <FileText className="w-4.5 h-4.5 text-orange-600 print:hidden" />
                        Notas Generales del Reporte
                    </h3>
                    <textarea 
                        value={reportNotes}
                        onChange={(e) => setReportNotes(e.target.value)}
                        rows={3}
                        className="bg-slate-50 hover:bg-slate-100/50 focus:bg-white border border-slate-200 text-slate-700 text-sm px-4 py-3 rounded-2xl w-full focus:outline-none focus:ring-2 focus:ring-orange-500 transition-all font-medium print:bg-transparent print:border-none print:p-0 print:text-slate-700 print:resize-none"
                        placeholder="Escribe comentarios generales para este reporte..."
                    />
                </div>

                {/* Tabs de tipo de reporte */}
                <div className="flex gap-2 mb-6 border-b border-slate-100 pb-3 print:hidden">
                    <button
                        type="button"
                        onClick={() => setActiveReportTab('detailed')}
                        className={`px-4 py-2 rounded-xl font-bold text-xs transition-all cursor-pointer ${
                            activeReportTab === 'detailed'
                                ? 'bg-orange-600 text-white shadow-sm'
                                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                        }`}
                    >
                        Detalle de Inconsistencias
                    </button>
                    <button
                        type="button"
                        onClick={() => setActiveReportTab('person')}
                        className={`px-4 py-2 rounded-xl font-bold text-xs transition-all cursor-pointer ${
                            activeReportTab === 'person'
                                ? 'bg-orange-600 text-white shadow-sm'
                                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                        }`}
                    >
                        Resumen por Persona (Auditor/Corrector)
                    </button>
                </div>

                {/* Tabla de Consistencia */}
                <div className="space-y-4">
                    <h3 className="text-sm font-bold text-slate-500 uppercase tracking-wider print:text-slate-800">
                        {activeReportTab === 'detailed' 
                            ? `Detalle de Inconsistencias Marcadas (${reportRows.length})`
                            : `Resumen de Errores y Correcciones por Persona (${personSummary.length})`
                        }
                    </h3>

                    {loading ? (
                        <div className="text-center py-12">
                            <div className="w-8 h-8 border-4 border-orange-500 border-t-transparent rounded-full animate-spin mx-auto mb-2"></div>
                            <span className="text-slate-500 text-sm">Cargando datos...</span>
                        </div>
                    ) : activeReportTab === 'detailed' ? (
                        reportRows.length === 0 ? (
                            <div className="text-center py-16 bg-slate-50 border border-slate-200 rounded-2xl">
                                <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-3" />
                                <p className="text-slate-500 font-bold">¡Excelente consistencia!</p>
                                <p className="text-slate-400 text-xs mt-1">No se encontraron marcas de error en los filtros seleccionados.</p>
                            </div>
                        ) : (
                            <div className="overflow-x-auto border border-slate-200 rounded-2xl shadow-sm">
                                <table className="min-w-full leading-normal border-collapse">
                                    <thead>
                                        <tr className="bg-slate-900 text-white font-bold text-xs uppercase">
                                            <th className="px-4 py-3 text-center border-b border-slate-200">Estación</th>
                                            <th className="px-4 py-3 text-center border-b border-slate-200">Fecha / Hora</th>
                                            <th className="px-4 py-3 text-center border-b border-slate-200">Campo</th>
                                            <th className="px-4 py-3 text-center border-b border-slate-200">Tipo de Error</th>
                                            <th className="px-4 py-3 text-center border-b border-slate-200">Datos (Orig → Corr)</th>
                                            <th className="px-4 py-3 text-left border-b border-slate-200 w-1/3">Nota Aclaratoria / Comentario</th>
                                            <th className="px-4 py-3 text-center border-b border-slate-200 print:hidden">Acción</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {reportRows.map((row) => {
                                            const hasCorr = row.valor_corregido !== null;
                                            return (
                                                <tr key={row.error_id} className="hover:bg-slate-50/50 transition-colors text-sm text-slate-800 border-b border-slate-100">
                                                    {/* Estación */}
                                                    <td className="px-4 py-4 text-center font-bold font-mono text-slate-700">{row.station_id}</td>
                                                    
                                                    {/* Fecha / Hora */}
                                                    <td className="px-4 py-4 text-center whitespace-nowrap">
                                                        <span className="block font-semibold">{row.fecha}</span>
                                                        <span className="text-xs text-orange-600 font-bold bg-orange-50 px-1.5 py-0.5 rounded">{row.hora}</span>
                                                    </td>

                                                    {/* Campo */}
                                                    <td className="px-4 py-4 text-center font-semibold text-slate-600">
                                                        {FIELD_LABELS[row.campo] || row.campo}
                                                    </td>

                                                    {/* Tipo de Error */}
                                                    <td className="px-4 py-4 text-center">
                                                        <span className="bg-red-50 text-red-700 font-bold text-[11px] px-2.5 py-1 rounded-full border border-red-200">
                                                            {row.tipo_error}
                                                        </span>
                                                    </td>

                                                    {/* Datos (Orig -> Corr) */}
                                                    <td className="px-4 py-4 text-center font-mono">
                                                        {hasCorr ? (
                                                            <div className="flex flex-col items-center gap-0.5">
                                                                <span className="text-red-500 line-through text-xs font-semibold">{row.valor_original || '(vacío)'}</span>
                                                                <span className="text-emerald-700 font-black text-sm">{row.valor_corregido}</span>
                                                            </div>
                                                        ) : (
                                                            <span className="text-slate-600 bg-slate-100 px-2 py-0.5 rounded text-xs">
                                                                {row.valor_original || '(vacío)'}
                                                            </span>
                                                        )}
                                                    </td>

                                                    {/* Nota Aclaratoria (Editable) */}
                                                    <td className="px-4 py-4 text-left">
                                                        {editingNoteId === row.error_id ? (
                                                            <div className="flex gap-2 items-center">
                                                                <textarea 
                                                                    value={editingNoteValue}
                                                                    onChange={(e) => setEditingNoteValue(e.target.value)}
                                                                    rows={1}
                                                                    className="bg-white border border-orange-300 text-slate-800 text-xs px-2 py-1.5 rounded-lg w-full focus:outline-none focus:ring-1 focus:ring-orange-500"
                                                                />
                                                                <button 
                                                                    onClick={() => handleSaveNote(row.error_id)}
                                                                    className="bg-orange-600 hover:bg-orange-700 text-white p-1.5 rounded-lg transition-colors cursor-pointer"
                                                                    title="Guardar Nota"
                                                                >
                                                                    <Save className="w-4 h-4" />
                                                                </button>
                                                            </div>
                                                        ) : (
                                                            <div className="flex items-center justify-between gap-2 group/note">
                                                                <span className="text-xs text-slate-600 italic">
                                                                    {row.nota ? `"${row.nota}"` : "(Sin observaciones escritas)"}
                                                                </span>
                                                                <button 
                                                                    onClick={() => handleSaveNote(row.error_id)}
                                                                    style={{ display: 'none' }} // Ocultamos el botón nativo no estilizado
                                                                />
                                                                <button
                                                                    onClick={() => handleStartEditNote(row)}
                                                                    className="text-slate-400 hover:text-orange-600 p-1 rounded hover:bg-slate-100 transition-colors opacity-0 group-hover/note:opacity-100 print:hidden cursor-pointer"
                                                                    title="Editar Nota en Reporte"
                                                                >
                                                                    <Edit3 className="w-3.5 h-3.5" />
                                                                </button>
                                                            </div>
                                                        )}
                                                    </td>

                                                    {/* Acción (Ocultar en Impresión) */}
                                                    <td className="px-4 py-4 text-center print:hidden">
                                                        <button
                                                            onClick={() => navigate(`/audit/observation/${row.station_id}/${row.fecha}`)}
                                                            className="bg-slate-100 hover:bg-orange-600 text-slate-600 hover:text-white font-bold py-1.5 px-3 rounded-lg text-xs transition-colors cursor-pointer"
                                                        >
                                                            Ver Celda
                                                        </button>
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        )
                    ) : (
                        personSummary.length === 0 ? (
                            <div className="text-center py-16 bg-slate-50 border border-slate-200 rounded-2xl">
                                <CheckCircle className="w-12 h-12 text-emerald-400 mx-auto mb-3" />
                                <p className="text-slate-500 font-bold">¡Sin actividad!</p>
                                <p className="text-slate-400 text-xs mt-1">No hay registros de auditoría por persona en este periodo.</p>
                            </div>
                        ) : (
                            <div className="overflow-x-auto border border-slate-200 rounded-2xl shadow-sm">
                                <table className="min-w-full leading-normal border-collapse">
                                    <thead>
                                        <tr className="bg-slate-900 text-white font-bold text-xs uppercase">
                                            <th className="px-6 py-3 text-left border-b border-slate-200">Usuario / Auditor</th>
                                            <th className="px-6 py-3 text-center border-b border-slate-200">Errores Marcados</th>
                                            <th className="px-6 py-3 text-center border-b border-slate-200">Correcciones Propuestas</th>
                                            <th className="px-6 py-3 text-center border-b border-slate-200">Correcciones Aprobadas</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {personSummary.map((row) => (
                                            <tr key={row.persona} className="hover:bg-slate-50/50 transition-colors text-sm text-slate-800 border-b border-slate-100">
                                                <td className="px-6 py-4 text-left font-bold text-slate-700">{row.persona}</td>
                                                <td className="px-6 py-4 text-center font-bold text-red-600">{row.errores_marcados}</td>
                                                <td className="px-6 py-4 text-center font-bold text-amber-600">{row.correcciones_propuestas}</td>
                                                <td className="px-6 py-4 text-center font-bold text-emerald-600">{row.correcciones_aprobadas}</td>
                                            </tr>
                                        ))}
                                        <tr className="bg-slate-100 font-extrabold text-sm text-slate-900 border-t border-slate-300">
                                            <td className="px-6 py-4 text-left uppercase">Total Acumulado</td>
                                            <td className="px-6 py-4 text-center text-red-700">
                                                {personSummary.reduce((acc, curr) => acc + curr.errores_marcados, 0)}
                                            </td>
                                            <td className="px-6 py-4 text-center text-amber-700">
                                                {personSummary.reduce((acc, curr) => acc + curr.correcciones_propuestas, 0)}
                                            </td>
                                            <td className="px-6 py-4 text-center text-emerald-700">
                                                {personSummary.reduce((acc, curr) => acc + curr.correcciones_aprobadas, 0)}
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        )
                    )}
                </div>
            </div>

            </div>
    );
};

export default AuditReportPage;
