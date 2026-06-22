import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { invoke } from '@tauri-apps/api/core';
import { 
    ArrowLeft, AlertTriangle, CheckCircle, Clock, 
    User, Calendar, HelpCircle, Save, X, Edit3, Trash2,
    BookOpen, ExternalLink, Radio
} from 'lucide-react';
import { toast } from 'react-hot-toast';

// Traducción de errores técnicos de Tauri a lenguaje humano
const humanizeError = (error) => {
    const msg = String(error);
    if (msg.includes('missing required key')) {
        return 'Error interno: faltan parámetros obligatorios en la solicitud. Verifica que hayas seleccionado un tipo de error y completado todos los campos requeridos antes de guardar.';
    }
    if (msg.includes('Este campo ya está marcado como error')) {
        return 'Este campo ya tiene una marca de error registrada para esta hora y fecha. Si necesitás modificarla, primero eliminá la marca existente.';
    }
    if (msg.includes('invalid type') || msg.includes('invalid args')) {
        return 'Error de comunicación con el backend. Intentá cerrar el modal y volver a abrirlo. Si persiste, reiniciá la aplicación.';
    }
    return msg;
};

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
    // Grupo 10
    "meteo_10_0": "8NsChs hs (5)",
    "meteo_10_1": "8NsChs hs (6)",
    "meteo_10_2": "9sp sp sp sp (1)",
    "meteo_10_3": "9sp sp sp sp (2)",
    "meteo_10_4": "9sp sp sp sp (3)",
    "meteo_10_5": "9sp sp sp sp (4)",
    "meteo_10_6": "9sp sp sp sp (5)",
    // Grupo 12
    "meteo_12_0": "9sp sp sp sp (6)",
    "meteo_12_1": "9sp sp sp sp (7)",
    "meteo_12_2": "9sp sp sp sp (8)",
    "meteo_12_3": "9sp sp sp sp (9)",
    "meteo_12_4": "9sp sp sp sp (10)",
    "meteo_12_5": "9sp sp sp sp (11)",
    "meteo_12_6": "9sp sp sp sp (12)",
    // Grupo 14
    "meteo_14_0": "9sp sp sp sp (13)",
    "meteo_14_1": "9sp sp sp sp (14)",
    "meteo_14_2": "9sp sp sp sp (15)",
    "meteo_14_3": "9sp sp sp sp (16)",
    "meteo_14_4": "9sp sp sp sp (17)",
    "meteo_14_5": "9sp sp sp sp (18)",
    "meteo_14_6": "9sp sp sp sp (19)",
    // Grupo 16
    "meteo_16_0": "9sp sp sp sp (20)",
    "meteo_16_1": "9sp sp sp sp (21)",
    "meteo_16_2": "9sp sp sp sp (22)",
    "meteo_16_3": "9sp sp sp sp (23)",
    "meteo_16_4": "9sp sp sp sp (24)",
    
    // Instrumentales / Cálculos
    "ts": "Temperatura Seca (Ts)",
    "th": "Temperatura Húmeda (Th)",
    "let_barom": "Lectura Barométrica",
    "correc_temp": "Corrección por Temperatura",
    "pres_est": "Presión de la Estación",
    "p3": "Presión hace 3 horas (P3)",
    "p24": "Presión hace 24 horas (P24)",
    "t_max": "Temperatura Máxima (Tx)",
    "t_min": "Temperatura Mínima (Tn)",
    "t_max_24h": "Temperatura Máxima 24h",
    "t_min_24h": "Temperatura Mínima 24h",
    "correc_alt": "Corrección por Altitud",
    "viento_dir": "Viento Dirección",
    "viento_vel": "Viento Velocidad",
    "LL": "Precipitación (Lluvia)",
    "LL_24h": "Precipitación 24h (Lluvia 24h)",
    
    // Calculados automáticos
    "punto_rocio": "Punto de Rocío (Td)",
    "tension_vapor": "Tensión de Vapor (Tv)",
    "humedad_relativa": "Humedad Relativa (Hr)",
    "diferencia": "Diferencia (Ts - Th)",
    "tend_dif": "Tendencia Diferencia",
    "tend_car": "Tendencia Car",
    "visibilidad": "Visibilidad (VV)",
    "tiempo_presente": "Tiempo Presente",
    "observador": "Nombre del Observador"
};

const AuditObservationPage = () => {
    const { station, date } = useParams();
    const navigate = useNavigate();
    
    const [loading, setLoading] = useState(true);
    const [observationData, setObservationData] = useState(null);
    const [activeHour, setActiveHour] = useState("06Z");
    const [stationName, setStationName] = useState("");
    
    // Seguridad y Roles
    const [currentUser, setCurrentUser] = useState({ email: '', roles: [] });
    const [canAudit, setCanAudit] = useState(false);

    // Modales y formularios
    const [selectedCell, setSelectedCell] = useState(null); // { hora, campo, valorActual }
    const [showErrorModal, setShowErrorModal] = useState(false);
    const [showCorrectionModal, setShowCorrectionModal] = useState(false);
    
    // Form data
    const [errorType, setErrorType] = useState("Sintaxis");
    const [errorNote, setErrorNote] = useState("");
    
    const [correctedValue, setCorrectedValue] = useState("");
    const [correctionJustification, setCorrectionJustification] = useState("");
    const [correctorName, setCorrectorName] = useState("");

    // Determinar horas disponibles
    const HOURS = ["00Z", "03Z", "06Z", "09Z", "12Z", "15Z", "18Z", "21Z"];

    useEffect(() => {
        // Cargar datos de usuario
        const email = localStorage.getItem('user_email') || 'auditor@arca.rd';
        const rolesRaw = localStorage.getItem('user_roles');
        const roles = rolesRaw ? JSON.parse(rolesRaw) : [];
        setCurrentUser({ email, roles });
        
        const hasPermission = roles.some(r => r === 'admin' || r.name === 'admin' || r === 'control_calidad' || r.name === 'control_calidad');
        setCanAudit(hasPermission);
        setCorrectorName(email.split('@')[0]); // Valor por defecto

        const fetchStationName = async () => {
            try {
                const stationsList = await invoke('get_stations');
                if (stationsList && stationsList[station]) {
                    setStationName(stationsList[station].name);
                } else {
                    setStationName(station);
                }
            } catch (err) {
                console.error("Error fetching station name:", err);
                setStationName(station);
            }
        };
        fetchStationName();

        loadObservation();
    }, [station, date]);

    const loadObservation = async (targetHour = activeHour) => {
        setLoading(true);
        try {
            const data = await invoke('audit_load_observation', { station, date });
            setObservationData(data);
            
            // Si ya hay una hora activa seleccionada con datos para este día, conservarla.
            // De lo contrario, buscar la primera hora con datos disponible.
            const obs = data.observation;
            const currentHourValid = targetHour && obs[targetHour] && Object.keys(obs[targetHour]).length > 0;
            if (!currentHourValid) {
                const hourWithData = HOURS.find(h => obs[h] && Object.keys(obs[h]).length > 0);
                if (hourWithData) {
                    setActiveHour(hourWithData);
                }
            } else {
                setActiveHour(targetHour);
            }
        } catch (error) {
            console.error("Error al cargar la observación:", error);
            toast.error("Error al cargar observación de auditoría: " + error);
        } finally {
            setLoading(false);
        }
    };

    const getCellValue = (hora, campo) => {
        if (!observationData || !observationData.observation) return "";
        const obsHora = observationData.observation[hora];
        if (!obsHora) return "";
        return obsHora[campo] !== undefined ? String(obsHora[campo]) : "";
    };

    // Verificar si el campo está marcado como error
    const getErrorMark = (hora, campo) => {
        if (!observationData || !observationData.error_marks) return null;
        return observationData.error_marks.find(m => m.hora === hora && m.campo === campo) || null;
    };

    // Verificar si el campo tiene una corrección activa
    const getCorrection = (hora, campo) => {
        if (!observationData || !observationData.corrections) return null;
        return observationData.corrections.find(c => c.hora === hora && c.campo === campo) || null;
    };

    const handleCellClick = (campo) => {
        if (!canAudit) {
            toast.error("Solo los administradores y control de calidad pueden realizar auditorías.");
            return;
        }
        
        const valorActual = getCellValue(activeHour, campo);
        setSelectedCell({ hora: activeHour, campo, valorActual });
        
        // Cargar datos si ya existe error/corrección
        const existingError = getErrorMark(activeHour, campo);
        if (existingError) {
            setErrorType(existingError.tipo_error);
            setErrorNote(existingError.nota || "");
        } else {
            setErrorType("Sintaxis");
            setErrorNote("");
        }

        const existingCorr = getCorrection(activeHour, campo);
        if (existingCorr) {
            setCorrectedValue(existingCorr.valor_corregido);
            setCorrectionJustification(existingCorr.justificacion);
        } else {
            setCorrectedValue(valorActual);
            setCorrectionJustification("");
        }

        setShowErrorModal(true);
    };

    const handleSaveErrorMark = async (e) => {
        e.preventDefault();
        if (!selectedCell) return;
        const currentHour = selectedCell.hora;
        try {
            await invoke('audit_mark_error', {
                stationId: station,
                fecha: date,
                hora: selectedCell.hora,
                campo: selectedCell.campo,
                tipoError: errorType,
                nota: errorNote ? errorNote : null,
                marcadoPor: currentUser.email
            });
            toast.success("Error marcado correctamente.");
            setShowErrorModal(false);
            loadObservation(currentHour);
        } catch (error) {
            toast.error(humanizeError(error));
        }
    };

    const handleRemoveErrorMark = async (markId) => {
        if (!window.confirm("¿Seguro que deseas quitar esta marca de error? Esto también eliminará cualquier propuesta de corrección asociada.")) return;
        const currentHour = activeHour;
        try {
            await invoke('audit_unmark_error', { id: markId });
            toast.success("Marca de error y corrección eliminadas.");
            setShowErrorModal(false);
            loadObservation(currentHour);
        } catch (error) {
            toast.error(humanizeError(error));
        }
    };

    const handleSaveCorrection = async (e) => {
        e.preventDefault();
        if (!selectedCell) return;
        if (!correctorName.trim()) {
            toast.error("Debe especificar su nombre para registrar la corrección.");
            return;
        }

        const currentHour = selectedCell.hora;
        try {
            await invoke('audit_propose_correction', {
                stationId: station,
                fecha: date,
                hora: selectedCell.hora,
                campo: selectedCell.campo,
                valorOriginal: selectedCell.valorActual,
                valorCorregido: correctedValue,
                justificacion: correctionJustification,
                corregidoPor: correctorName
            });
            toast.success("Corrección aplicada correctamente (Overlay activo).");
            setShowCorrectionModal(false);
            setShowErrorModal(false);
            loadObservation(currentHour);
        } catch (error) {
            toast.error(humanizeError(error));
        }
    };

    const renderDataField = (label, campo, placeholder = "") => {
        const valor = getCellValue(activeHour, campo);
        const error = getErrorMark(activeHour, campo);
        const corr = getCorrection(activeHour, campo);

        let cellClass = "bg-white border border-slate-200 text-slate-800 text-sm px-3 py-2 rounded-lg w-full text-center font-mono transition-all cursor-pointer hover:bg-orange-50/50";
        let tooltipText = FIELD_LABELS[campo] || label;

        if (error) {
            cellClass = "bg-red-50 border-2 border-red-500 text-red-700 font-bold text-sm px-3 py-2 rounded-lg w-full text-center font-mono cursor-pointer transition-all hover:bg-red-100";
            tooltipText += ` | Error: ${error.tipo_error} (${error.nota || 'Sin nota'})`;
        }
        
        if (corr) {
            cellClass = "bg-emerald-50 border-2 border-emerald-500 text-emerald-700 font-black text-sm px-3 py-2 rounded-lg w-full text-center font-mono cursor-pointer transition-all hover:bg-emerald-100";
            tooltipText += ` | Corregido por ${corr.corregido_por}: ${corr.valor_original} → ${corr.valor_corregido === "" ? "(Vacío)" : corr.valor_corregido}`;
        }

        return (
            <div className="flex flex-col gap-1" title={tooltipText}>
                <span className="text-[11px] font-bold text-slate-400 text-center truncate">{label}</span>
                <input 
                    type="text" 
                    className={cellClass} 
                    value={valor} 
                    placeholder={placeholder}
                    readOnly 
                    onClick={() => handleCellClick(campo)}
                />
            </div>
        );
    };

    const renderReadonlyField = (label, campo) => {
        const valor = getCellValue(activeHour, campo);
        return (
            <div className="flex flex-col gap-1" title={FIELD_LABELS[campo] || label}>
                <span className="text-[11px] font-bold text-slate-400 text-center truncate">{label}</span>
                <input 
                    type="text" 
                    className="bg-slate-100 border border-slate-200 text-slate-500 font-semibold text-sm px-3 py-2 rounded-lg w-full text-center font-mono" 
                    value={valor} 
                    readOnly 
                />
            </div>
        );
    };

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-slate-50">
                <div className="flex flex-col items-center gap-3">
                    <div className="w-12 h-12 border-4 border-orange-500 border-t-transparent rounded-full animate-spin"></div>
                    <span className="text-slate-600 font-bold">Cargando observación meteorológica...</span>
                </div>
            </div>
        );
    }

    const observadorGeneral = observationData?.observation?.observador || "";
    // Observador por hora: si existe en la hora activa, mostrar ese; si no, usar el general
    const observadorHora = getCellValue(activeHour, "observador");
    const observador = observadorHora || observadorGeneral || "Desconocido";
    const observadorFaltante = !observadorGeneral && !observadorHora;

    return (
        <div className="p-6 max-w-7xl mx-auto pb-16">
            {/* Header */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6">
                <div className="flex items-center gap-4">
                    <button
                        onClick={() => navigate('/audit')}
                        className="w-10 h-10 rounded-full bg-white border border-slate-200 shadow-sm transition-all hover:bg-orange-50 hover:scale-110 flex items-center justify-center text-slate-600 cursor-pointer"
                        title="Volver al Selector"
                    >
                        <ArrowLeft className="w-5 h-5" />
                    </button>
                    <div>
                        <div className="flex items-center gap-2 flex-wrap">
                            <span className="bg-orange-600 text-white font-bold text-xs px-2.5 py-1 rounded-md uppercase">Estación {stationName || station}</span>
                            <span className="bg-slate-200 text-slate-700 font-semibold text-xs px-2.5 py-1 rounded-md flex items-center gap-1">
                                <Calendar className="w-3.5 h-3.5" />
                                {date}
                            </span>
                        </div>
                        <h1 className="text-2xl font-black text-slate-900 mt-1">Auditoría de Datos Meteorológicos</h1>
                    </div>
                </div>

                <div className="flex flex-col items-end gap-2">
                    <div className="bg-white border border-slate-100 rounded-xl p-3 shadow-sm flex items-center gap-4 text-xs font-semibold text-slate-500">
                        <div className="flex items-center gap-1.5">
                            <User className="w-4 h-4 text-slate-400" />
                            Observador: <span className={`font-bold ${observadorFaltante ? 'text-red-600 animate-pulse' : 'text-slate-800'}`}>{observador}{observadorFaltante && ' ⚠ SIN NOMBRE'}</span>
                        </div>
                        <div className="h-4 w-px bg-slate-200"></div>
                        <div className="flex items-center gap-1.5">
                            <Clock className="w-4 h-4 text-slate-400" />
                            Auditor: <span className="text-orange-600 font-bold">{currentUser.email}</span>
                        </div>
                    </div>
                    {/* Acceso a CLIs para referencia cruzada del auditor y botón de exportar JSON corregido */}
                    <div className="flex gap-2 flex-wrap items-center">
                        <button
                            onClick={() => navigate('/cli3074', { state: { fromAudit: true, stationId: station, station, date } })}
                            className="flex items-center gap-1 bg-slate-100 hover:bg-blue-50 text-slate-600 hover:text-blue-700 font-bold text-[11px] px-3 py-1.5 rounded-lg transition-all cursor-pointer border border-slate-200 hover:border-blue-300"
                            title="Consultar CLI 3074 para referencia de corrección"
                        >
                            <BookOpen className="w-3.5 h-3.5" />
                            CLI 3074
                        </button>
                        <button
                            onClick={() => navigate('/cli4074', { state: { fromAudit: true, stationId: station, station, date } })}
                            className="flex items-center gap-1 bg-slate-100 hover:bg-blue-50 text-slate-600 hover:text-blue-700 font-bold text-[11px] px-3 py-1.5 rounded-lg transition-all cursor-pointer border border-slate-200 hover:border-blue-300"
                            title="Consultar CLI 4074 para referencia de corrección"
                        >
                            <BookOpen className="w-3.5 h-3.5" />
                            CLI 4074
                        </button>
                        <button
                            onClick={() => navigate('/cli5074', { state: { fromAudit: true, stationId: station, station, date } })}
                            className="flex items-center gap-1 bg-slate-100 hover:bg-blue-50 text-slate-600 hover:text-blue-700 font-bold text-[11px] px-3 py-1.5 rounded-lg transition-all cursor-pointer border border-slate-200 hover:border-blue-300"
                            title="Consultar CLI 5074 para referencia de corrección"
                        >
                            <BookOpen className="w-3.5 h-3.5" />
                            CLI 5074
                        </button>
                        <div className="h-6 w-px bg-slate-200"></div>
                        <button
                            onClick={async () => {
                                try {
                                    const path = await invoke('audit_export_corrected_json', { stationId: station, fecha: date });
                                    toast.success(`¡JSON Corregido guardado con éxito!\nGuardado en: ${path}`, { duration: 5000 });
                                } catch (error) {
                                    console.error(error);
                                    toast.error(`Error al exportar JSON corregido: ${error}`);
                                }
                            }}
                            className="flex items-center gap-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-sm px-5 py-2.5 rounded-xl transition-all cursor-pointer shadow-md shadow-emerald-500/20 border-0 transform hover:scale-105"
                            title="Guarda la observación permanentemente con todas las correcciones aplicadas"
                        >
                            <Save className="w-4 h-4" />
                            Guardar Correcciones
                        </button>
                    </div>
                </div>
            </div>

            {/* Alerta automática: Observador sin nombre */}
            {observadorFaltante && (
                <div className="flex items-center gap-3 bg-red-50 border border-red-200 rounded-xl p-4 mb-4 shadow-sm">
                    <AlertTriangle className="w-6 h-6 text-red-500 shrink-0" />
                    <div className="flex-1">
                        <p className="font-bold text-red-800 text-sm">⚠ Observador no identificado</p>
                        <p className="text-red-600 text-xs mt-0.5">
                            Esta observación no registra el nombre del observador de turno. 
                            Según el protocolo, toda observación DEBE incluir la identificación del personal responsable. 
                            Se recomienda marcar este dato como error de tipo "Falta de datos".
                        </p>
                    </div>
                </div>
            )}

            {/* Selector de Horas */}
            <div className="flex flex-wrap gap-2 mb-6 bg-white p-2 rounded-2xl border border-slate-100 shadow-sm">
                {HOURS.map((hora) => {
                    const hasData = observationData?.observation?.[hora] && Object.keys(observationData.observation[hora]).length > 0;
                    const errorInHour = observationData?.error_marks?.some(m => m.hora === hora);
                    const corrInHour = observationData?.corrections?.some(c => c.hora === hora);

                    let btnClass = "px-4 py-2.5 rounded-xl font-bold text-sm transition-all flex items-center gap-1.5 cursor-pointer ";
                    
                    if (activeHour === hora) {
                        btnClass += "bg-orange-600 text-white shadow-md scale-105";
                    } else if (hasData) {
                        btnClass += "bg-slate-100 text-slate-700 hover:bg-orange-50 hover:text-orange-600";
                    } else {
                        btnClass += "bg-slate-50 text-slate-300 cursor-not-allowed opacity-50";
                    }

                    return (
                        <button
                            key={hora}
                            onClick={() => hasData && setActiveHour(hora)}
                            disabled={!hasData}
                            className={btnClass}
                        >
                            <span>{hora}</span>
                            {errorInHour && <span className="w-2 h-2 rounded-full bg-red-500 animate-ping"></span>}
                            {corrInHour && !errorInHour && <span className="w-2 h-2 rounded-full bg-emerald-500"></span>}
                        </button>
                    );
                })}
            </div>

            {/* Contenedor de Formulario y Panel de Auditoría */}
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                {/* Formulario Espejo de Observación */}
                <div className="lg:col-span-3 space-y-6">
                    {/* Sección SYNOP */}
                    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                        <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-100">
                            <h2 className="text-lg font-black text-slate-800">Secciones SYNOP OMM</h2>
                            <span className="text-xs text-slate-400 font-semibold uppercase">Hacer click en un campo para marcar error o corregir</span>
                        </div>

                        <div className="space-y-4">
                            {/* Fila 2 & 4 */}
                            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
                                {renderReadonlyField("AAXX (MiMi MjMj)", "meteo_2_1_prefix")}
                                {renderDataField("YYGG Iw (Grupo 2)", "meteo_2_1", "YYGGiw")}
                                {renderDataField("Ir iX H VV (Grupo 4)", "meteo_4_irixhvv", "IrIXHVV")}
                                {renderDataField("N dd ff (Grupo 4)", "meteo_4_1", "Nddff")}
                            </div>

                            {/* Fila 6 (Temperaturas / Suelo) */}
                            <div className="grid grid-cols-1 sm:grid-cols-7 gap-4">
                                {renderDataField("8Nh CL CM CH", "meteo_6_0", "8NhCLCMCH")}
                                {renderDataField("0CS DL DM DH", "meteo_6_2", "0CSDLDMDH")}
                                {renderDataField("1sn Tx Tx Tx", "meteo_6_3", "1snTxTxTx")}
                                {renderDataField("2sn Tn Tn Tn", "meteo_6_4", "2snTnTnTn")}
                                {renderDataField("3 E E E j", "meteo_6_5", "3Ejjj")}
                                {renderDataField("5 E E E j", "meteo_6_6", "5EEEjE")}
                                {renderDataField("7 ww W1 W2", "meteo_4_6", "7wwW1W2")}
                            </div>

                            {/* Fila 8 (Precipitación / Nubes) */}
                            <div className="grid grid-cols-1 sm:grid-cols-6 gap-4">
                                {renderDataField("5n Fn Fn Fn", "meteo_8_0", "5nFnFnFn")}
                                {renderDataField("56 DL DM DH", "meteo_8_1", "56DLDMDH")}
                                {renderDataField("6 RRR tr", "meteo_8_3", "6RRRtr")}
                                {renderDataField("7 R24 R24 R24 R24", "meteo_8_4", "7R24R24R24R24")}
                                {renderDataField("8NsChs hs (1)", "meteo_8_5", "8NsChshs")}
                                {renderDataField("8NsChs hs (2)", "meteo_8_6", "8NsChshs")}
                            </div>

                            {/* Nubes adicionales (Extras) */}
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 bg-slate-50 p-3 rounded-xl border border-slate-100">
                                {renderDataField("8NsChs hs (3)", "extra_8ns_1", "8NsChshs")}
                                {renderDataField("8NsChs hs (4)", "extra_8ns_2", "8NsChshs")}
                                {renderDataField("8NsChs hs (5)", "meteo_10_0", "8NsChshs")}
                                {renderDataField("8NsChs hs (6)", "meteo_10_1", "8NsChshs")}
                            </div>

                            {/* Grupos 9sp */}
                            <div className="space-y-2">
                                <span className="text-[11px] font-bold text-slate-400 block uppercase">Fenómenos Especiales (Grupo 9sp)</span>
                                <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
                                    {renderDataField("9sp (1)", "meteo_10_2", "9spspsp")}
                                    {renderDataField("9sp (2)", "meteo_10_3", "9spspsp")}
                                    {renderDataField("9sp (3)", "meteo_10_4", "9spspsp")}
                                    {renderDataField("9sp (4)", "meteo_10_5", "9spspsp")}
                                    {renderDataField("9sp (5)", "meteo_10_6", "9spspsp")}
                                    {renderDataField("9sp (6)", "meteo_12_0", "9spspsp")}
                                </div>
                                <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
                                    {renderDataField("9sp (7)", "meteo_12_1", "9spspsp")}
                                    {renderDataField("9sp (8)", "meteo_12_2", "9spspsp")}
                                    {renderDataField("9sp (9)", "meteo_12_3", "9spspsp")}
                                    {renderDataField("9sp (10)", "meteo_12_4", "9spspsp")}
                                    {renderDataField("9sp (11)", "meteo_12_5", "9spspsp")}
                                    {renderDataField("9sp (12)", "meteo_12_6", "9spspsp")}
                                </div>
                                <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
                                    {renderDataField("9sp (13)", "meteo_14_0", "9spspsp")}
                                    {renderDataField("9sp (14)", "meteo_14_1", "9spspsp")}
                                    {renderDataField("9sp (15)", "meteo_14_2", "9spspsp")}
                                    {renderDataField("9sp (16)", "meteo_14_3", "9spspsp")}
                                    {renderDataField("9sp (17)", "meteo_14_4", "9spspsp")}
                                    {renderDataField("9sp (18)", "meteo_14_5", "9spspsp")}
                                </div>
                                <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
                                    {renderDataField("9sp (19)", "meteo_14_6", "9spspsp")}
                                    {renderDataField("9sp (20)", "meteo_16_0", "9spspsp")}
                                    {renderDataField("9sp (21)", "meteo_16_1", "9spspsp")}
                                    {renderDataField("9sp (22)", "meteo_16_2", "9spspsp")}
                                    {renderDataField("9sp (23)", "meteo_16_3", "9spspsp")}
                                    {renderDataField("9sp (24)", "meteo_16_4", "9spspsp")}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Cálculos e Instrumentales */}
                    <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                        <h2 className="text-lg font-black text-slate-800 mb-4 pb-2 border-b border-slate-100">Cálculos e Instrumentales de Estación</h2>
                        
                        <div className="space-y-4">
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                                {renderDataField("Temp. Seca (Ts)", "ts", "°C")}
                                {renderDataField("Temp. Húmeda (Th)", "th", "°C")}
                                {renderReadonlyField("Punto Rocío (Td)", "punto_rocio")}
                                {renderReadonlyField("Humedad Relativa (Hr)", "humedad_relativa")}
                            </div>

                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                                {renderDataField("Lectura Barométrica", "let_barom", "hPa")}
                                {renderDataField("Presión Estación (Pres_est)", "pres_est", "hPa")}
                                {renderDataField("Presión 3h (P3)", "p3", "hPa")}
                                {renderDataField("Presión 24h (P24)", "p24", "hPa")}
                            </div>

                            <div className="grid grid-cols-2 sm:grid-cols-6 gap-4">
                                {renderDataField("Temp. Máxima (Tx)", "t_max", "°C")}
                                {renderDataField("Temp. Mínima (Tn)", "t_min", "°C")}
                                {renderDataField("Tx 24h", "t_max_24h", "°C")}
                                {renderDataField("Tn 24h", "t_min_24h", "°C")}
                                {renderDataField("Lluvia (LL)", "LL", "mm")}
                                {renderDataField("Lluvia 24h (LL_24h)", "LL_24h", "mm")}
                            </div>

                            <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 bg-slate-50 p-3 rounded-xl border border-slate-100">
                                {renderReadonlyField("Presión NMM", "pres_nmm")}
                                {renderReadonlyField("Tensión Vapor", "tension_vapor")}
                                {renderReadonlyField("Diferencia (Ts-Th)", "diferencia")}
                                {renderDataField("Viento Dirección", "viento_dir", "dd")}
                                {renderDataField("Viento Velocidad", "viento_vel", "ff")}
                            </div>

                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 bg-slate-50 p-3 rounded-xl border border-slate-100">
                                {renderReadonlyField("Visibilidad (VV)", "visibilidad")}
                                {renderReadonlyField("Tiempo Presente", "tiempo_presente")}
                                {renderReadonlyField("Tendencia Dif.", "tend_dif")}
                                {renderReadonlyField("Tendencia Car", "tend_car")}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Panel Lateral de Auditoría */}
                <div className="space-y-6">
                    {/* Estadísticas de la Observación */}
                    <div className="bg-gradient-to-br from-orange-500 to-amber-600 text-white rounded-2xl p-5 shadow-md border border-orange-400/20 relative overflow-hidden">
                        {/* Círculos decorativos translúcidos de fondo */}
                        <div className="absolute -right-6 -bottom-6 w-24 h-24 bg-white/10 rounded-full blur-xl" />
                        <div className="absolute -left-6 -top-6 w-20 h-20 bg-white/10 rounded-full blur-lg" />
                        
                        <h3 className="font-bold text-xs text-orange-100 uppercase tracking-widest mb-4 flex items-center gap-1.5 relative z-10">
                            <Radio className="w-3.5 h-3.5 animate-pulse" /> Estado de Auditoría
                        </h3>
                        
                        <div className="grid grid-cols-2 gap-3 relative z-10">
                            <div className="bg-white/10 backdrop-blur-md p-3.5 rounded-xl border border-white/15 flex flex-col justify-between">
                                <span className="text-[11px] text-orange-100 font-semibold">Inconsistencias</span>
                                <span className="text-2xl font-black mt-1.5 flex items-baseline gap-1">
                                    {observationData?.error_marks?.length || 0}
                                    <span className="text-[10px] font-normal text-orange-200">campos</span>
                                </span>
                            </div>

                            <div className="bg-white/10 backdrop-blur-md p-3.5 rounded-xl border border-white/15 flex flex-col justify-between">
                                <span className="text-[11px] text-orange-100 font-semibold">Corregidos</span>
                                <span className="text-2xl font-black mt-1.5 flex items-baseline gap-1">
                                    {observationData?.corrections?.length || 0}
                                    <span className="text-[10px] font-normal text-orange-200">campos</span>
                                </span>
                            </div>
                        </div>
                        <p className="text-[10px] text-orange-100/80 leading-normal text-center mt-3 pt-3 border-t border-white/10 relative z-10">
                            Correcciones activas mediante <strong>Overlay dinámico</strong>.
                        </p>
                    </div>

                    {/* Historial de Errores Marcados */}
                    <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
                        <h3 className="font-bold text-sm text-slate-800 mb-3 uppercase tracking-wider border-b border-slate-100 pb-2">Marcas en este día</h3>
                        
                        {observationData?.error_marks?.length === 0 ? (
                            <div className="text-center py-8 text-slate-400 text-sm">
                                <CheckCircle className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                                Sin marcas de error registradas.
                            </div>
                        ) : (
                            <div className="space-y-3 max-h-[300px] overflow-y-auto pr-1">
                                {observationData?.error_marks?.map((mark) => {
                                    const corr = getCorrection(mark.hora, mark.campo);
                                    return (
                                        <div key={mark.id} className="p-3 bg-slate-50 border border-slate-100 rounded-xl text-xs space-y-1 relative group">
                                            <div className="flex justify-between font-bold">
                                                <span className="text-orange-600">{mark.hora} - {FIELD_LABELS[mark.campo] || mark.campo}</span>
                                                <span className="bg-red-100 text-red-700 px-1.5 py-0.5 rounded text-[10px]">{mark.tipo_error}</span>
                                            </div>
                                            {mark.nota && <p className="text-slate-600 italic">"{mark.nota}"</p>}
                                            <div className="text-[10px] text-slate-400 pt-1 flex justify-between items-center">
                                                <span>Por: {mark.marcado_por.split('@')[0]}</span>
                                                {canAudit && (
                                                    <button 
                                                        onClick={() => handleRemoveErrorMark(mark.id)}
                                                        className="text-red-500 hover:text-red-700 cursor-pointer transition-colors"
                                                        title="Eliminar marca"
                                                    >
                                                        <Trash2 className="w-3.5 h-3.5" />
                                                    </button>
                                                )}
                                            </div>
                                            {corr && (
                                                <div className="mt-2 pt-2 border-t border-slate-200 text-emerald-700 font-semibold flex items-center gap-1">
                                                    <CheckCircle className="w-3 h-3" />
                                                    Corregido: {corr.valor_corregido}
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                </div>
            </div>

            {/* MODAL 1: OPCIONES DE AUDITORÍA (Marcado de Error) */}
            {showErrorModal && selectedCell && (
                <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
                    <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full border border-slate-100 overflow-hidden transform transition-all">
                        {/* Cabecera Modal */}
                        <div className="bg-slate-900 text-white p-4 flex justify-between items-center">
                            <div>
                                <span className="bg-orange-600 text-white font-bold text-[10px] px-2 py-0.5 rounded uppercase">{selectedCell.hora}</span>
                                <h3 className="font-bold text-lg mt-1 truncate">{FIELD_LABELS[selectedCell.campo] || selectedCell.campo}</h3>
                            </div>
                            <button 
                                onClick={() => setShowErrorModal(false)}
                                className="text-slate-400 hover:text-white transition-colors"
                            >
                                <X className="w-6 h-6" />
                            </button>
                        </div>

                        <div className="p-6 space-y-4">
                            {/* Información de Celda */}
                            <div className="bg-slate-50 p-3 rounded-xl border border-slate-100 text-sm flex justify-between items-center">
                                <span className="font-semibold text-slate-500">Valor actual en observación:</span>
                                <span className="font-mono bg-white border border-slate-200 px-3 py-1 rounded-lg text-slate-800 font-bold">
                                    {selectedCell.valorActual || "(Vacío)"}
                                </span>
                            </div>

                            {/* Mostrar si ya está corregido */}
                            {getCorrection(selectedCell.hora, selectedCell.campo) && (
                                <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 p-3 rounded-xl text-xs space-y-1">
                                    <div className="font-bold flex items-center gap-1">
                                        <CheckCircle className="w-4 h-4 text-emerald-600" />
                                        Corrección activa aplicada
                                    </div>
                                    <p>Valor corregido: <span className="font-mono font-bold bg-white px-1.5 py-0.5 rounded border border-emerald-100">{getCorrection(selectedCell.hora, selectedCell.campo).valor_corregido}</span></p>
                                    <p>Justificación: "{getCorrection(selectedCell.hora, selectedCell.campo).justificacion}"</p>
                                    <p className="text-[10px] text-slate-400 pt-1">Corregido por: {getCorrection(selectedCell.hora, selectedCell.campo).corregido_por}</p>
                                </div>
                            )}

                            {/* Formulario para Marcar Error */}
                            <form onSubmit={handleSaveErrorMark} className="space-y-3 pt-2">
                                <h4 className="font-extrabold text-sm text-slate-800 flex items-center gap-1.5">
                                    <AlertTriangle className="w-4 h-4 text-red-500" />
                                    Marcar o Editar Error
                                </h4>
                                
                                <div>
                                    <label className="block text-xs font-bold text-slate-400 mb-1">Tipo de Error</label>
                                    <select 
                                        value={errorType}
                                        onChange={(e) => setErrorType(e.target.value)}
                                        className="bg-white border border-slate-200 text-slate-800 text-sm px-3 py-2 rounded-lg w-full focus:outline-none focus:ring-2 focus:ring-orange-500"
                                    >
                                        <option value="Sintaxis">Error de Sintaxis / Formato</option>
                                        <option value="Cálculo">Error de Cálculo / Matemático</option>
                                        <option value="Consistencia">Inconsistencia entre grupos</option>
                                        <option value="Falta de datos">Datos Faltantes / Omitidos</option>
                                        <option value="Otro">Otro / Observación manual</option>
                                    </select>
                                </div>

                                <div>
                                    <label className="block text-xs font-bold text-slate-400 mb-1">Nota Aclaratoria / Comentario</label>
                                    <textarea 
                                        value={errorNote}
                                        onChange={(e) => setErrorNote(e.target.value)}
                                        rows={2}
                                        placeholder="Escribe por qué este campo está incorrecto..."
                                        className="bg-white border border-slate-200 text-slate-800 text-sm px-3 py-2 rounded-lg w-full focus:outline-none focus:ring-2 focus:ring-orange-500"
                                    />
                                </div>

                                <div className="flex gap-2 pt-2">
                                    {getErrorMark(selectedCell.hora, selectedCell.campo) && (
                                        <button
                                            type="button"
                                            onClick={() => handleRemoveErrorMark(getErrorMark(selectedCell.hora, selectedCell.campo).id)}
                                            className="flex-1 bg-red-100 hover:bg-red-200 text-red-700 font-bold py-2.5 px-4 rounded-xl text-xs transition-colors flex items-center justify-center gap-1 cursor-pointer"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                            Quitar Marca
                                        </button>
                                    )}
                                    <button
                                        type="submit"
                                        className="flex-1 bg-slate-900 hover:bg-slate-800 text-white font-bold py-2.5 px-4 rounded-xl text-xs transition-colors flex items-center justify-center gap-1 cursor-pointer"
                                    >
                                        <Save className="w-4 h-4" />
                                        Guardar Marca
                                    </button>
                                </div>
                            </form>
                            
                            {/* Botón de transición a Corrección */}
                            <div className="pt-4 border-t border-slate-100 flex justify-end">
                                <button
                                    onClick={() => {
                                        setShowErrorModal(false);
                                        setShowCorrectionModal(true);
                                    }}
                                    className="flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-2.5 px-5 rounded-xl text-xs transition-colors shadow-sm cursor-pointer"
                                >
                                    <Edit3 className="w-4 h-4" />
                                    Aplicar Corrección
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* MODAL 2: APLICAR CORRECCIÓN (OVERLAY) */}
            {showCorrectionModal && selectedCell && (
                <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
                    <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full border border-slate-100 overflow-hidden transform transition-all">
                        {/* Cabecera Modal */}
                        <div className="bg-emerald-600 text-white p-4 flex justify-between items-center">
                            <div>
                                <span className="bg-white text-emerald-700 font-extrabold text-[10px] px-2 py-0.5 rounded uppercase">Corrección Overlay</span>
                                <h3 className="font-bold text-lg mt-1 truncate">{FIELD_LABELS[selectedCell.campo] || selectedCell.campo}</h3>
                            </div>
                            <button 
                                onClick={() => setShowCorrectionModal(false)}
                                className="text-emerald-100 hover:text-white transition-colors"
                            >
                                <X className="w-6 h-6" />
                            </button>
                        </div>

                        <form onSubmit={handleSaveCorrection} className="p-6 space-y-4">
                            {/* Info de valores */}
                            <div className="grid grid-cols-2 gap-4">
                                <div className="bg-slate-50 p-3 rounded-xl border border-slate-100">
                                    <span className="block text-[10px] font-bold text-slate-400 mb-1 uppercase">Valor Original</span>
                                    <span className="font-mono text-slate-700 font-bold block truncate">
                                        {selectedCell.valorActual || "(Vacío)"}
                                    </span>
                                </div>
                                <div className="bg-emerald-50/50 p-3 rounded-xl border border-emerald-100">
                                    <span className="block text-[10px] font-bold text-emerald-600 mb-1 uppercase">Valor Corregido</span>
                                    <input 
                                        type="text" 
                                        value={correctedValue}
                                        onChange={(e) => setCorrectedValue(e.target.value)}
                                        className="font-mono bg-white border border-emerald-300 px-2 py-1 rounded w-full text-emerald-800 font-bold focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 text-center"
                                        placeholder="Valor..."
                                        autoFocus
                                    />
                                </div>
                            </div>

                            {/* Justificación */}
                            <div>
                                <label className="block text-xs font-bold text-slate-400 mb-1">Justificación del Cambio</label>
                                <textarea 
                                    required
                                    value={correctionJustification}
                                    onChange={(e) => setCorrectionJustification(e.target.value)}
                                    rows={3}
                                    placeholder="Explica técnicamente por qué se corrige este valor..."
                                    className="bg-white border border-slate-200 text-slate-800 text-sm px-3 py-2 rounded-lg w-full focus:outline-none focus:ring-2 focus:ring-emerald-500"
                                />
                            </div>

                            {/* Nombre del corrector */}
                            <div>
                                <label className="block text-xs font-bold text-slate-400 mb-1">Nombre del Auditor / Corrector</label>
                                <input 
                                    type="text" 
                                    required
                                    value={correctorName}
                                    onChange={(e) => setCorrectorName(e.target.value)}
                                    className="bg-white border border-slate-200 text-slate-800 text-sm px-3 py-2 rounded-lg w-full focus:outline-none focus:ring-2 focus:ring-emerald-500 font-semibold"
                                    placeholder="Nombre completo..."
                                />
                            </div>

                            <div className="flex gap-2 pt-2">
                                <button
                                    type="button"
                                    onClick={() => {
                                        setShowCorrectionModal(false);
                                        setShowErrorModal(true);
                                    }}
                                    className="flex-1 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold py-2.5 px-4 rounded-xl text-xs transition-colors cursor-pointer"
                                >
                                    Volver a Marcas
                                </button>
                                <button
                                    type="submit"
                                    className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white font-bold py-2.5 px-4 rounded-xl text-xs transition-colors flex items-center justify-center gap-1 shadow-md cursor-pointer"
                                >
                                    <Save className="w-4 h-4" />
                                    Aplicar Cambio
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
};

export default AuditObservationPage;
