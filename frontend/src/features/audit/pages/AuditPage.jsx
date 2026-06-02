import React, { useState, useEffect } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { useNavigate } from 'react-router-dom';
import { 
    ArrowLeft, Radio, Calendar, CalendarDays, FileText, 
    CheckCircle, AlertTriangle, ChevronRight, Clock, User 
} from 'lucide-react';

const AuditPage = () => {
    const navigate = useNavigate();
    const [loading, setLoading] = useState(false);
    
    // Estados del drill-down
    const [step, setStep] = useState(1); // 1: Estaciones, 2: Años, 3: Meses, 4: Días
    const [selectedStation, setSelectedStation] = useState(null);
    const [selectedYear, setSelectedYear] = useState(null);
    const [selectedMonth, setSelectedMonth] = useState(null);

    // Datos cargados desde Tauri
    const [stations, setStations] = useState([]);
    const [years, setYears] = useState([]);
    const [months, setMonths] = useState([]);
    const [days, setDays] = useState([]);

    // Cargar estaciones iniciales
    useEffect(() => {
        loadStations();
    }, []);

    const loadStations = async () => {
        setLoading(true);
        try {
            const data = await invoke('audit_browse_stations');
            setStations(data || []);
        } catch (error) {
            console.error("Error cargando estaciones:", error);
        } finally {
            setLoading(false);
        }
    };

    const getStationName = (code) => {
        if (!code) return "";
        const st = stations.find(s => s.code === code);
        return st ? st.name : code;
    };

    const handleSelectStation = async (stationCode) => {
        setSelectedStation(stationCode);
        setLoading(true);
        try {
            const data = await invoke('audit_browse_years', { station: stationCode });
            setYears(data || []);
            setStep(2);
        } catch (error) {
            console.error("Error cargando años:", error);
        } finally {
            setLoading(false);
        }
    };

    const handleSelectYear = async (year) => {
        setSelectedYear(year);
        setLoading(true);
        try {
            const data = await invoke('audit_browse_months', { 
                station: selectedStation, 
                year: year 
            });
            setMonths(data || []);
            setStep(3);
        } catch (error) {
            console.error("Error cargando meses:", error);
        } finally {
            setLoading(false);
        }
    };

    const handleSelectMonth = async (month) => {
        setSelectedMonth(month);
        setLoading(true);
        try {
            const data = await invoke('audit_browse_days', { 
                station: selectedStation, 
                year: selectedYear, 
                month: month 
            });
            setDays(data || []);
            setStep(4);
        } catch (error) {
            console.error("Error cargando días:", error);
        } finally {
            setLoading(false);
        }
    };

    const getNombreMes = (numMes) => {
        const nombres = {
            "01": "Enero", "02": "Febrero", "03": "Marzo", "04": "Abril",
            "05": "Mayo", "06": "Junio", "07": "Julio", "08": "Agosto",
            "09": "Septiembre", "10": "Octubre", "11": "Noviembre", "12": "Diciembre"
        };
        return nombres[numMes] || `Mes ${numMes}`;
    };

    return (
        <div className="p-6 max-w-7xl mx-auto">
            {/* Header del Módulo */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6">
                <div className="flex items-center gap-4">
                    <button
                        onClick={() => {
                            if (step > 1) {
                                setStep(step - 1);
                            } else {
                                navigate('/dashboard');
                            }
                        }}
                        className="w-10 h-10 rounded-full bg-white border border-orange-200 shadow-sm transition-all hover:bg-orange-50 hover:scale-110 flex items-center justify-center text-orange-600 focus:outline-none focus:ring-2 focus:ring-orange-200 cursor-pointer"
                        title={step > 1 ? "Volver al nivel anterior" : "Volver al Dashboard"}
                    >
                        <ArrowLeft className="w-5 h-5" />
                    </button>
                    <div>
                        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">
                            Módulo de Auditoría
                        </h1>
                        <p className="text-slate-500 text-sm">
                            Control de Calidad, Marcado de Errores y Superposición de Correcciones
                        </p>
                    </div>
                </div>

                <div className="flex gap-3">
                    <button
                        onClick={() => navigate('/audit/report')}
                        className="flex items-center gap-2 bg-orange-600 hover:bg-orange-700 text-white font-semibold py-2.5 px-4 rounded-xl shadow-md hover:shadow-lg transition-all duration-300 hover:scale-[1.02] cursor-pointer"
                    >
                        <FileText className="w-5 h-5" />
                        Reporte General de Errores
                    </button>
                </div>
            </div>

            {/* Breadcrumbs de Navegación Drill-down */}
            <div className="bg-white border border-slate-100 rounded-xl p-3 shadow-sm mb-6 flex items-center flex-wrap gap-2 text-sm text-slate-600 font-medium">
                <button 
                    onClick={() => { setStep(1); setSelectedStation(null); }}
                    className={`hover:text-orange-600 transition-colors ${step === 1 ? 'text-orange-600 font-bold' : ''}`}
                >
                    Estaciones
                </button>
                
                {selectedStation && (
                    <>
                        <ChevronRight className="w-4 h-4 text-slate-400" />
                        <button 
                            onClick={() => { setStep(2); setSelectedYear(null); }}
                            className={`hover:text-orange-600 transition-colors ${step === 2 ? 'text-orange-600 font-bold' : ''}`}
                        >
                            Estación {getStationName(selectedStation)}
                        </button>
                    </>
                )}

                {selectedYear && (
                    <>
                        <ChevronRight className="w-4 h-4 text-slate-400" />
                        <button 
                            onClick={() => { setStep(3); setSelectedMonth(null); }}
                            className={`hover:text-orange-600 transition-colors ${step === 3 ? 'text-orange-600 font-bold' : ''}`}
                        >
                            {selectedYear}
                        </button>
                    </>
                )}

                {selectedMonth && (
                    <>
                        <ChevronRight className="w-4 h-4 text-slate-400" />
                        <span className="text-slate-400 font-normal">
                            {getNombreMes(selectedMonth)}
                        </span>
                    </>
                )}
            </div>

            {/* Contenido Principal */}
            <div className="bg-slate-50 border border-slate-200/50 rounded-2xl p-6 min-h-[400px] shadow-inner relative">
                {loading ? (
                    <div className="absolute inset-0 flex items-center justify-center bg-slate-50/80 rounded-2xl">
                        <div className="flex flex-col items-center gap-3">
                            <div className="w-12 h-12 border-4 border-orange-500 border-t-transparent rounded-full animate-spin"></div>
                            <span className="text-slate-600 font-semibold text-sm">Cargando datos...</span>
                        </div>
                    </div>
                ) : null}

                {/* Paso 1: Selección de Estación */}
                {step === 1 && (
                    <div>
                        <h2 className="text-xl font-bold text-slate-800 mb-4 flex items-center gap-2">
                            <Radio className="w-5 h-5 text-orange-500 animate-pulse" />
                            Seleccione una Estación Meteorológica
                        </h2>
                        {stations.length === 0 ? (
                            <div className="text-center py-16 bg-white border border-slate-200 rounded-xl shadow-sm">
                                <Radio className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                                <p className="text-slate-500 font-medium">No se encontraron directorios de estaciones en synop.</p>
                            </div>
                        ) : (
                            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                                {stations.map((st) => (
                                    <div 
                                        key={st.code}
                                        onClick={() => handleSelectStation(st.code)}
                                        className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm hover:shadow-md hover:border-orange-300 transition-all duration-300 hover:scale-[1.02] cursor-pointer flex flex-col justify-between group"
                                    >
                                        <div>
                                            <span className="text-xs font-bold text-orange-500 uppercase tracking-wider block mb-1">Estación</span>
                                            <h3 className="text-lg font-bold text-slate-800 tracking-tight group-hover:text-orange-600 transition-colors">
                                                {st.name || st.code}
                                            </h3>
                                        </div>
                                        <div className="mt-4 pt-3 border-t border-slate-100 flex justify-between items-center text-sm font-semibold text-slate-500 group-hover:text-orange-500 transition-colors">
                                            <span>Explorar años</span>
                                            <ChevronRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {/* Paso 2: Selección de Año */}
                {step === 2 && (
                    <div>
                        <h2 className="text-xl font-bold text-slate-800 mb-4 flex items-center gap-2">
                            <Calendar className="w-5 h-5 text-orange-500" />
                            Seleccione el Año de Observación
                        </h2>
                        {years.length === 0 ? (
                            <div className="text-center py-16 bg-white border border-slate-200 rounded-xl shadow-sm">
                                <Calendar className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                                <p className="text-slate-500 font-medium">No hay carpetas de años para esta estación.</p>
                            </div>
                        ) : (
                            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
                                {years.map((year) => (
                                    <div 
                                        key={year}
                                        onClick={() => handleSelectYear(year)}
                                        className="bg-white border border-slate-200 rounded-xl p-6 text-center shadow-sm hover:shadow-md hover:border-orange-300 transition-all duration-300 hover:scale-[1.02] cursor-pointer group"
                                    >
                                        <Calendar className="w-8 h-8 text-slate-400 group-hover:text-orange-500 transition-colors mx-auto mb-2" />
                                        <span className="text-2xl font-extrabold text-slate-800 tracking-tight block group-hover:text-orange-600 transition-colors">
                                            {year}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {/* Paso 3: Selección de Mes */}
                {step === 3 && (
                    <div>
                        <h2 className="text-xl font-bold text-slate-800 mb-4 flex items-center gap-2">
                            <CalendarDays className="w-5 h-5 text-orange-500" />
                            Seleccione el Mes
                        </h2>
                        {months.length === 0 ? (
                            <div className="text-center py-16 bg-white border border-slate-200 rounded-xl shadow-sm">
                                <CalendarDays className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                                <p className="text-slate-500 font-medium">No hay carpetas de meses registradas en este año.</p>
                            </div>
                        ) : (
                            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
                                {months.map((month) => (
                                    <div 
                                        key={month}
                                        onClick={() => handleSelectMonth(month)}
                                        className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm hover:shadow-md hover:border-orange-300 transition-all duration-300 hover:scale-[1.02] cursor-pointer group"
                                    >
                                        <span className="text-sm font-bold text-slate-400 block mb-1">Mes {month}</span>
                                        <h3 className="text-xl font-bold text-slate-800 group-hover:text-orange-600 transition-colors">
                                            {getNombreMes(month)}
                                        </h3>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {/* Paso 4: Selección de Día */}
                {step === 4 && (
                    <div>
                        <h2 className="text-xl font-bold text-slate-800 mb-4 flex items-center gap-2">
                            <FileText className="w-5 h-5 text-orange-500" />
                            Listado de Días — Estación {getStationName(selectedStation)} ({getNombreMes(selectedMonth)} {selectedYear})
                        </h2>
                        {days.length === 0 ? (
                            <div className="text-center py-16 bg-white border border-slate-200 rounded-xl shadow-sm">
                                <FileText className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                                <p className="text-slate-500 font-medium">No se encontraron observaciones persistidas en este mes.</p>
                            </div>
                        ) : (
                            <div className="space-y-3">
                                {days.map((day) => (
                                    <div 
                                        key={day.filename}
                                        className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm hover:shadow-md hover:border-orange-300 transition-all duration-300 flex flex-col md:flex-row justify-between items-start md:items-center gap-4"
                                    >
                                        <div className="flex flex-col gap-1">
                                            <span className="text-lg font-bold text-slate-800">
                                                Día {day.date.split('-')[2]} ({day.date})
                                            </span>
                                            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-500">
                                                {day.observador && day.observador !== 'Desconocido' && (
                                                    <span className="flex items-center gap-1">
                                                        <User className="w-4 h-4 text-slate-400" />
                                                        Obs: <span className="font-semibold text-slate-700">{day.observador}</span>
                                                    </span>
                                                )}
                                                <span className="flex items-center gap-1">
                                                    <Clock className="w-4 h-4 text-slate-400" />
                                                    Horas: <span className="font-semibold text-slate-700">{day.horas_registradas}</span>
                                                </span>
                                            </div>
                                        </div>

                                        <div className="flex items-center gap-3 flex-wrap">
                                            {/* Badges de Errores y Correcciones */}
                                            {day.error_count > 0 && (
                                                <span className="flex items-center gap-1 bg-red-50 text-red-700 px-2.5 py-1 rounded-full text-xs font-bold border border-red-200 shadow-sm animate-pulse">
                                                    <AlertTriangle className="w-3.5 h-3.5" />
                                                    {day.error_count} {day.error_count === 1 ? 'Error' : 'Errores'}
                                                </span>
                                            )}

                                            {day.correction_count > 0 && (
                                                <span className="flex items-center gap-1 bg-emerald-50 text-emerald-700 px-2.5 py-1 rounded-full text-xs font-bold border border-emerald-200 shadow-sm">
                                                    <CheckCircle className="w-3.5 h-3.5" />
                                                    {day.correction_count} {day.correction_count === 1 ? 'Corrección' : 'Correcciones'}
                                                </span>
                                            )}

                                            {day.error_count === 0 && day.correction_count === 0 && (
                                                <span className="text-xs font-semibold text-slate-400 bg-slate-100 px-2.5 py-1 rounded-full">
                                                    Sin auditar
                                                </span>
                                            )}

                                            <button
                                                onClick={() => navigate(`/audit/observation/${selectedStation}/${day.date}`)}
                                                className="bg-orange-100 hover:bg-orange-600 text-orange-700 hover:text-white font-bold py-2 px-4 rounded-lg text-sm transition-all duration-300 hover:scale-105 cursor-pointer flex items-center gap-1"
                                            >
                                                Auditar
                                                <ChevronRight className="w-4 h-4" />
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};

export default AuditPage;
