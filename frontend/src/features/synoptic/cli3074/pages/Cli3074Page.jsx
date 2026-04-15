/**
 * CLI 3074 - Formulario de observación meteorológica horaria
 *
 * FLUJO DE DATOS:
 * 1. load_cli3074_json: Carga JSON guardado del CLI 3074
 *    - Si existe, usa esos datos (ya tienen cálculos aplicados)
 *
 * 2. get_observation: Carga JSON sinóptico (si no hay CLI guardado)
 *    - Retorna datos con campos calculados: tend_dif, visibilidad, tiempo_presente
 *    - Ver json_handler.rs funciones: calc_dif(), get_visibilidad_from_irixhv(), calc_tiempo_presente()
 *
 * 3. calculate_observations: Cálculos meteorológicos adicionales
 *    - NMM (presión nivel medio mar)
 *    - Humedad relativa, punto rocío, tensión de vapor
 *    - Ver calculations.rs función realizar_calculos()
 *
 * CAMPOS AUTO-CALCULADOS:
 * - tend_dif (DIF): Diferencia de presión en formato "00.0"
 * - visibilidad: Desde código VV de IrIxHVV
 * - tiempo_presente (ww): Desde 7wwW1W2 o comparación Nddff
 * - pres_nmm: Presión reducida al nivel del mar
 * - hum_hr, hum_ptor, hum_tvap: Parámetros de humedad
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { invoke } from '@tauri-apps/api/core';

/**
 * Mapeo de horas sinópticas UTC a filas del formulario (horas locales)
 * El CLI 3074 tiene 24 filas (1 por cada hora local)
 * Las observaciones sinópticas se hacen cada 3 horas UTC
 */
const synopRows = {
  "06Z": 2, "09Z": 5, "12Z": 8, "15Z": 11,
  "18Z": 14, "21Z": 17, "00Z": 20, "03Z": 23
};

const Cli3074Page = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [stations, setStations] = useState({});
  const [selectedStation, setSelectedStation] = useState(location.state?.stationId || '');
  
  const [date, setDate] = useState(() => {
    if (location.state?.date) return location.state.date;
    const today = new Date();
    return today.toISOString().split('T')[0];
  });

  // State for the 24 rows
  const [rows, setRows] = useState(() => {
    const initial = {};
    for (let i = 1; i <= 24; i++) {
        initial[i] = {
            pres_est: '', // Agregado: Presion Estación
            pres_nmm: '',
            pres_alti: '',
            tend_car: '',
            tend_dif: '',
            temp_seco: '',
            temp_humedo: '',
            hum_ptor: '',
            hum_tvap: '',
            hum_hr: '',
            viento_dir: '',
            viento_vel: '',
            visibilidad: '',
            fenomenos: {
                tiempo_presente: '', granizo: false, ventarron: false, neblina: false, trueno: false, relampago: false, 
                rocio: false, polvo: false, calima: false, niebla: false, tornado: false
            }
        };
    }
    return initial;
  });

  const loadFormData = async (currentStation, currentDate) => {
      if (!currentStation || !currentDate) return;
      try {
          const data = await invoke('load_cli3074_json', { stationId: currentStation, date: currentDate });
          if (data && Object.keys(data).length > 0) {
              setRows(data);
          } else {
              // Initialize empty
              const initial = {};
              for (let i = 1; i <= 24; i++) {
                  initial[i] = {
                      pres_est: '', pres_nmm: '', pres_alti: '', tend_car: '', tend_dif: '', temp_seco: '', temp_humedo: '', hum_ptor: '', hum_tvap: '', hum_hr: '', viento_dir: '', viento_vel: '', visibilidad: '',
                      fenomenos: { tiempo_presente: '', granizo: false, ventarron: false, neblina: false, trueno: false, relampago: false, rocio: false, polvo: false, calima: false, niebla: false, tornado: false }
                  };
              }

              // Intentar autocompletar desde la observación sinóptica guardada
              try {
                  const synopData = await invoke('get_observation', { 
                      stationCode: currentStation, 
                      fecha: currentDate  // get_observation acepta YYYY-MM-DD directamente
                  });
                  
                  // get_observation retorna un objeto plano: { "06Z": {...}, "09Z": {...}, station_id, fecha }
                  if (synopData) {
                      const validHours = Object.keys(synopRows); // ["06Z", "09Z", ...]
                      
                      for (const horaKey of validHours) {
                          const horaData = synopData[horaKey];
                          if (!horaData) continue;
                          
                          const rowNum = synopRows[horaKey];
                          
                          // Asignaciones directas desde los datos flattened
                          initial[rowNum].pres_est = horaData.pres_est || '';
                          initial[rowNum].temp_seco = horaData.ts || '';
                          initial[rowNum].temp_humedo = horaData.th || '';
                          initial[rowNum].visibilidad = horaData.visibilidad || '';

                          // Extraer Viento = Nddff (igual que la formula Excel M11)
                          const nddff = horaData.meteo_4_1 || horaData.Nddff || '';
                          if (horaData.viento_dir) {
                              initial[rowNum].viento_dir = horaData.viento_dir;
                          } else if (nddff.length >= 3 && nddff[1] !== '/' && nddff[2] !== '/') {
                              const dd = parseInt(nddff.substring(1, 3), 10);
                              if (!isNaN(dd)) initial[rowNum].viento_dir = (dd * 10).toString();
                          }
                          
                          if (horaData.viento_vel) {
                              initial[rowNum].viento_vel = horaData.viento_vel;
                          } else if (nddff.length >= 5 && nddff[3] !== '/' && nddff[4] !== '/') {
                              const ff = parseInt(nddff.substring(3, 5), 10);
                              // Velocidad en m/s (1 nudo = 0.514444 m/s)
                              if (!isNaN(ff)) initial[rowNum].viento_vel = (ff * 0.514444).toFixed(1);
                          }

            // Tiempo Presente: el backend ya lo calcula desde 7wwW1W2 o comparando Nddff
            // Ver función calc_tiempo_presente() en json_handler.rs
            initial[rowNum].fenomenos.tiempo_presente = horaData.tiempo_presente || '';

            // DIF y CAR: el backend ya los calcula en get_observation
            // Ver calc_dif() y format_dif() en json_handler.rs
            initial[rowNum].tend_dif = horaData.tend_dif || '';
            initial[rowNum].tend_car = horaData.tend_car || '';

            // Auto-calcular NMM, HR via backend Rust (cálculos meteorológicos)
            if (horaData.ts && horaData.th) {
              try {
                const stationCh = stations[currentStation]?.ch;
                const calcData = await invoke('calculate_observations', {
                  data: {
                    ts: horaData.ts || '',
                    th: horaData.th || '',
                    pres_est: horaData.pres_est || '',
                    p3: horaData.p3 || '',
                    p24: horaData.p24 || '',
                    correc_alt: stationCh != null ? stationCh.toString() : '',
                    station_id: currentStation,
                    ir: '', ix: ''
                  }
                });

                if (!calcData.error_message) {
                  initial[rowNum].pres_nmm = calcData.pres_nmm || '';
                  initial[rowNum].hum_ptor = calcData.punto_rocio || '';
                  initial[rowNum].hum_tvap = calcData.tension_vapor || '';
                  initial[rowNum].hum_hr = calcData.humedad_relativa || '';
                }
              } catch (calcErr) {
                console.warn(`Error calculando hora ${horaKey}:`, calcErr);
              }
            }
          }
        }
      } catch(e) {
        console.log("No existe data sinóptica base para autocompletar.", e);
      }
      setRows(initial);
    }
  } catch (e) {
    console.error("Error cargando formulario", e);
  }
};

  // Se inicializan estaciones y luego se carga el formulario
  useEffect(() => {
    const init = async () => {
      try {
        const stationData = await invoke('get_stations');
        setStations(stationData);
        // Despues de tener las estaciones cargamos el excel (para que el correc_alt exista)
        await loadFormData(selectedStation, date);
      } catch (error) {
        console.error("Error en inicialización:", error);
      }
    };
    init();
  }, []); // Solo al montar

  // Escuchar por si cambian los dropdowns de CLI
  useEffect(() => {
     if (Object.keys(stations).length > 0) {
        loadFormData(selectedStation, date);
     }
  }, [selectedStation, date]);

  const stInfo = selectedStation && stations[selectedStation] ? stations[selectedStation] : null;

// Real-time Calculation Trigger
const updateRowField = async (rowNum, fieldPath, value) => {
  setRows(prev => {
    const newRows = { ...prev };

    // Handle nested phenomenos object
    if (fieldPath.startsWith('fenomenos.')) {
      const subField = fieldPath.split('.')[1];
      newRows[rowNum] = { ...newRows[rowNum], fenomenos: { ...newRows[rowNum].fenomenos, [subField]: value } };
    } else {
      newRows[rowNum] = { ...newRows[rowNum], [fieldPath]: value };
    }

    // Calcular DIF y CAR automáticamente cuando cambian pres_est o p3
    if (fieldPath === 'pres_est' || fieldPath === 'p3') {
      const row = newRows[rowNum];
      const presEst = parseFloat(fieldPath === 'pres_est' ? value : row.pres_est);
      const p3Val = parseFloat(fieldPath === 'p3' ? value : row.p3);

      if (!isNaN(presEst) && !isNaN(p3Val)) {
        // Calcular DIF = |pres_est - p3| con formato "00.0"
        const dif = Math.abs(presEst - p3Val);
        newRows[rowNum].tend_dif = dif.toFixed(1);

        // Calcular CAR según código WMO 0266
        newRows[rowNum].tend_car = calcCAR(presEst, p3Val);
      } else {
        // Si no hay valores válidos, limpiar
        newRows[rowNum].tend_dif = '';
        newRows[rowNum].tend_car = '';
      }
    }

    return newRows;
  });
};

/**
 * Calcular CAR (Característica de la tendencia de presión)
 * Código WMO 0266 para el grupo 5appp
 *
 * @param {number} presEst - Presión de estación
 * @param {number} p3 - Presión hace 3 horas
 * @returns {string} - Código CAR (0-8)
 */
const calcCAR = (presEst, p3) => {
  const dif = presEst - p3; // NOTA: no usar abs, necesitamos el signo
  const absDif = Math.abs(dif);

  if (dif === 0) return '4';

  if (dif > 0) {
    // Presión aumentó
    if (absDif >= 0.1 && absDif <= 0.5) return '0';
    if (absDif >= 0.6 && absDif <= 1.4) return '1';
    if (absDif >= 1.5 && absDif <= 1.9) return '2';
    if (absDif >= 2.0) return '3';
  } else {
    // Presión disminuyó
    if (absDif >= 0.1 && absDif <= 0.5) return '5';
    if (absDif >= 0.6 && absDif <= 1.4) return '6';
    if (absDif >= 1.5 && absDif <= 1.9) return '7';
    if (absDif >= 2.0) return '8';
  }

  return '';
};

  const calculateRow = useCallback(async (rowNum) => {
    const row = rows[rowNum];
    if (row.temp_seco && row.temp_humedo) {
         try {
            const calcData = await invoke('calculate_observations', {
                data: {
                    ts: row.temp_seco.toString(),
                    th: row.temp_humedo.toString(),
                    pres_est: '', p3: '', p24: '',
                    correc_alt: stInfo ? stInfo.ch.toString() : '',
                    station_id: selectedStation,
                    ir: '', ix: ''
                }
            });
            // Auto update calculated humidity/dew point based on calculations.rs
            if (!calcData.error_message) {
                setRows(prev => ({
                    ...prev,
                    [rowNum]: {
                        ...prev[rowNum],
                        hum_ptor: calcData.punto_rocio || preservedRowState(prev, rowNum, 'hum_ptor'),
                        hum_tvap: calcData.tension_vapor || preservedRowState(prev, rowNum, 'hum_tvap'),
                        hum_hr: calcData.humedad_relativa || preservedRowState(prev, rowNum, 'hum_hr')
                    }
                }));
            }
         } catch (error) {
             console.error("Error calculando fila ", rowNum, error);
         }
    }
  }, [rows, selectedStation, stInfo]);

  const handleBlur = (rowNum, key) => {
      if (key === 'temp_seco' || key === 'temp_humedo') {
          calculateRow(rowNum);
      }
  };

  const preservedRowState = (prev, rowNum, key) => {
      return prev[rowNum][key];
  };

  const handleSave = async () => {
      if (!selectedStation) {
          alert("Seleccione una estación primero.");
          return;
      }
      try {
          await invoke('save_cli3074_json', { stationId: selectedStation, date, data: rows });
          alert("✓ Formulario CLI 3074 guardado exitosamente");
      } catch (err) {
          alert("X Error al guardar el formulario: " + err);
      }
  };

  const thClass = "border border-slate-700 bg-slate-800/90 text-white font-bold text-sm py-2 px-1 align-middle whitespace-nowrap overflow-hidden";
  const subThClass = "border border-slate-600 bg-slate-700/80 text-white text-xs font-semibold py-1 px-1";
  
  // Fenómenos con códigos OMM (WMO Table 020003)
  // Formato: [abreviatura, descripción completa para tooltip]
  const fenomenosList = [
    { key: 'granizo', abbr: 'GR', label: 'Granizo (tormenta con granules)' },
    { key: 'ventarron', abbr: 'SQ', label: 'Ventarrón (Squalls)' },
    { key: 'neblina', abbr: 'FG', label: 'Neblina/Niebla (Fog)' },
    { key: 'trueno', abbr: 'TS', label: 'Trueno (Thunderstorm)' },
    { key: 'relampago', abbr: 'LT', label: 'Relámpago (Lightning visible)' },
    { key: 'rocio', abbr: 'RD', label: 'Rocío (Dew)' },
    { key: 'polvo', abbr: 'DS', label: 'Polvo (Duststorm)' },
    { key: 'calima', abbr: 'HZ', label: 'Calima (Haze)' },
    { key: 'niebla', abbr: 'FG', label: 'Niebla (Fog)' },
    { key: 'tornado', abbr: 'FC', label: 'Tornado (Funnel cloud)' }
  ];

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col font-sans relative overflow-hidden">
        {/* Aesthetic Background Effect */}
        <div className="absolute top-0 left-0 w-full h-96 bg-gradient-to-b from-sky-600/10 to-transparent pointer-events-none"></div>
        
        <div className="px-6 py-4 flex items-center gap-4 z-10 w-full max-w-full">
             <button
                onClick={() => navigate('/synoptic')}
                className="px-4 py-2 bg-white border border-slate-300 rounded-lg shadow-sm text-sm font-medium hover:bg-slate-50 transition-colors text-slate-700 flex items-center gap-2"
            >
                <span>&larr;</span> Volver a Observaciones
            </button>
            <h1 className="text-2xl font-bold text-slate-800 tracking-tight">CLI 3074 - OBSERVACIONES DE SUPERFICIE</h1>
            
            <button onClick={handleSave} className="ml-auto px-6 py-2 bg-sky-600 hover:bg-sky-700 text-white text-sm font-bold rounded-lg shadow-md transition-all">
                Guardar Formulario
            </button>
        </div>

        {/* HEADER BLOCK */}
        <div className="mx-6 mb-4 p-4 bg-white border border-slate-200 border-t-4 border-t-sky-500 shadow-sm rounded-lg z-10 mx-w-full overflow-x-auto">
            <div className="flex flex-wrap items-center gap-x-8 gap-y-4">
                <div className="flex items-center gap-2">
                    <label className="text-sm font-bold text-slate-700 uppercase">Estación:</label>
                    <select 
                        value={selectedStation} 
                        onChange={(e) => setSelectedStation(e.target.value)}
                        className="bg-slate-50 border border-slate-300 text-slate-800 text-sm rounded-md px-3 py-1.5 focus:ring-2 focus:ring-sky-500"
                    >
                        <option value="">Seleccione Estación</option>
                        {Object.entries(stations).map(([id, info]) => (
                            <option key={id} value={id}>{info.name} ({id})</option>
                        ))}
                    </select>
                </div>

                {stInfo && (
                    <>
                        <div className="flex items-center gap-2 text-sm text-slate-700">
                            <span className="font-bold uppercase">Latitud:</span>
                            <span className="bg-slate-100 px-3 py-1 rounded font-mono border border-slate-200">{stInfo.lat}°</span>
                        </div>
                        <div className="flex items-center gap-2 text-sm text-slate-700">
                            <span className="font-bold uppercase">Longitud:</span>
                            <span className="bg-slate-100 px-3 py-1 rounded font-mono border border-slate-200">{stInfo.lon}°</span>
                        </div>
                        <div className="flex items-center gap-2 text-sm text-slate-700">
                            <span className="font-bold uppercase">Altura:</span>
                            <span className="bg-slate-100 px-3 py-1 rounded font-mono border border-slate-200">{stInfo.h} M</span>
                        </div>
                    </>
                )}

                <div className="flex items-center gap-2 ml-auto">
                    <label className="text-sm font-bold text-slate-700 uppercase">Fecha:</label>
                    <input 
                        type="date"
                        value={date}
                        onChange={(e) => setDate(e.target.value)}
                        className="bg-slate-50 border border-slate-300 text-slate-800 text-sm rounded-md px-3 py-1.5 focus:ring-2 focus:ring-sky-500"
                    />
                </div>
            </div>
        </div>

{/* SPREADSHEET TIER CONTAINER */}
        <div className="mx-6 flex-1 z-10 bg-white rounded-lg shadow-[0px_4px_20px_rgba(0,0,0,0.1)] border border-slate-300 overflow-x-auto overflow-y-auto mb-6 max-h-[70vh] custom-scrollbar">
            <table className="w-full text-center border-collapse">
                <thead className="sticky top-0 z-20 shadow-sm bg-slate-900">
                    <tr>
                        <th rowSpan="2" className={`${thClass} min-w-[50px]`}>HORA<br/>LOCAL</th>
                        <th colSpan="3" className={`${thClass} bg-sky-800/80`}>PRESIÓN (hPa)</th>
                        <th colSpan="2" className={`${thClass} bg-blue-800/80`}>3 H. TEND</th>
                        <th colSpan="2" className={`${thClass} bg-indigo-800/80`}>TEMPERATURA<br/><span className="text-[10px] font-normal text-indigo-200">TERMÓMETROS</span></th>
                        <th colSpan="3" className={`${thClass} bg-violet-800/80`}>HUMEDAD</th>
                        <th colSpan="2" className={`${thClass} bg-fuchsia-800/80`}>VIENTO</th>
                        <th rowSpan="2" className={`${thClass} min-w-[70px]`}>VISIBILIDAD<br/>(km)</th>
                        <th colSpan={1 + fenomenosList.length} className={`${thClass} bg-slate-700`}>FENÓMENOS</th>
                    </tr>
                    <tr className="bg-slate-800">
                        <th className={subThClass}>Esta.</th>
                        <th className={subThClass}>NMM</th>
                        <th className={subThClass}>Altímetro</th>
                        
                        <th className={subThClass} title="Característica">C.A.R</th>
                        <th className={subThClass}>Dif</th>
                        
                        <th className={subThClass}>SECO</th>
                        <th className={subThClass}>HÚMEDO</th>
                        
                        <th className={subThClass}>PTO R (°C)</th>
                        <th className={subThClass}>T VAP (hPa)</th>
                        <th className={subThClass}>HR %</th>
                        
                        <th className={subThClass}>DIR (16-P)</th>
                        <th className={subThClass}>VEL (m/s)</th>

                        <th className={`${subThClass} whitespace-normal min-w-[60px] text-[10px]`}>TIEMPO PRES.</th>
                        {fenomenosList.map(f => (
                           <th key={f.key} 
                               className={`${subThClass} min-w-[20px] max-w-[25px] cursor-help`}
                               title={f.label}
                           >
                               <div className="w-full flex items-center justify-center -rotate-90 text-[9px] tracking-tighter uppercase overflow-hidden h-[40px] leading-none">
                                   {f.abbr}
                               </div>
                           </th>
                        ))}
                    </tr>
                </thead>
                <tbody className="bg-white">
                    {Object.keys(rows).map((rowStr) => {
                        const i = parseInt(rowStr);
                        const row = rows[i];
                        
                        // Resaltar la fila cada 3 horas, empezando desde la 2 (2, 5, 8, 11...)
                        const isMainHour = (i - 2) % 3 === 0;
                        const trClass = isMainHour ? 'bg-sky-50 shadow-[inset_0_1px_2px_rgba(0,0,0,0.05)] font-medium' : 'bg-white hover:bg-slate-50';
                        
                        const inputStyle = `w-full text-center bg-transparent border-none focus:outline-none focus:ring-1 focus:ring-sky-500 focus:bg-sky-100/50 text-slate-800 text-[13px] font-mono h-[30px] ${isMainHour ? "font-semibold text-slate-900" : ""}`;
                        const readonlyStyle = `w-full text-center bg-transparent border-none text-sky-700 font-bold font-mono text-[13px] ${isMainHour ? "text-sky-800" : ""}`;
                        const chkStyle = "w-[14px] h-[14px] text-sky-600 bg-white border-slate-400 rounded focus:ring-sky-500 cursor-pointer shadow-sm";
                        const tdBorder = "border-[1px] border-slate-200 p-0 m-0 h-[30px] overflow-hidden";

                        return (
                            <tr key={i} className={`transition-colors ${trClass}`}>
                                <td className={`border border-slate-300 font-bold text-sm sticky left-0 z-10 shadow-[2px_0_5px_-2px_rgba(0,0,0,0.1)] ${isMainHour ? 'bg-sky-200 text-sky-900' : 'bg-slate-100 text-slate-600'}`}>{i}</td>
                                
                                <td className={`${tdBorder} ${isMainHour ? 'bg-sky-100/50' : ''}`}><input className={inputStyle} value={row.pres_est} onChange={e => updateRowField(i, 'pres_est', e.target.value)} /></td>
                                <td className={tdBorder}><input className={inputStyle} value={row.pres_nmm} onChange={e => updateRowField(i, 'pres_nmm', e.target.value)} /></td>
                                <td className={tdBorder}><input className={inputStyle} value={row.pres_alti} onChange={e => updateRowField(i, 'pres_alti', e.target.value)} /></td>
                                
                                <td className={tdBorder}><input className={inputStyle} value={row.tend_car} onChange={e => updateRowField(i, 'tend_car', e.target.value)} /></td>
                                <td className={tdBorder}><input className={inputStyle} value={row.tend_dif} onChange={e => updateRowField(i, 'tend_dif', e.target.value)} /></td>
                                
                                <td className={tdBorder}><input className={inputStyle} value={row.temp_seco} onChange={e => updateRowField(i, 'temp_seco', e.target.value)} onBlur={() => handleBlur(i, 'temp_seco')} /></td>
                                <td className={tdBorder}><input className={inputStyle} value={row.temp_humedo} onChange={e => updateRowField(i, 'temp_humedo', e.target.value)} onBlur={() => handleBlur(i, 'temp_humedo')} /></td>
                                
                                <td className={`${tdBorder} bg-blue-50/50`}><input className={readonlyStyle} value={row.hum_ptor} readOnly /></td>
                                <td className={`${tdBorder} bg-blue-50/50`}><input className={readonlyStyle} value={row.hum_tvap} readOnly /></td>
                                <td className={`${tdBorder} bg-blue-50/50`}><input className={readonlyStyle} value={row.hum_hr} readOnly /></td>
                                
                                <td className={tdBorder}><input className={inputStyle} value={row.viento_dir} onChange={e => updateRowField(i, 'viento_dir', e.target.value)} /></td>
                                <td className={tdBorder}><input className={inputStyle} value={row.viento_vel} onChange={e => updateRowField(i, 'viento_vel', e.target.value)} /></td>
                                
                                <td className={tdBorder}><input className={inputStyle} value={row.visibilidad} onChange={e => updateRowField(i, 'visibilidad', e.target.value)} /></td>
                                
                                <td className={tdBorder}><input className={inputStyle} value={row.fenomenos.tiempo_presente} onChange={e => updateRowField(i, 'fenomenos.tiempo_presente', e.target.value)} /></td>
                                {fenomenosList.map(f => (
                                    <td key={f.key} className={tdBorder}>
                                        <div className="flex items-center justify-center w-full h-full">
                                           <input type="checkbox" className={chkStyle} checked={row.fenomenos[f.key]} onChange={e => updateRowField(i, `fenomenos.${f.key}`, e.target.checked)} />
                                        </div>
                                    </td>
                                ))}
                            </tr>
                        );
                    })}
                </tbody>
            </table>
        </div>
        
        {/* Ad hoc inline style for custom scrollbars */}
        <style dangerouslySetInnerHTML={{__html: `
            .custom-scrollbar::-webkit-scrollbar {
                width: 10px;
                height: 10px;
            }
            .custom-scrollbar::-webkit-scrollbar-track {
                background: #f1f5f9;
                border-radius: 8px;
            }
            .custom-scrollbar::-webkit-scrollbar-thumb {
                background: #cbd5e1;
                border-radius: 8px;
            }
            .custom-scrollbar::-webkit-scrollbar-thumb:hover {
                background: #94a3b8;
            }
        `}} />
    </div>
  );
};

export default Cli3074Page;
