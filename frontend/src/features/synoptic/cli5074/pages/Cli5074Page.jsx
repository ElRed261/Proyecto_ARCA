import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { invoke } from '@tauri-apps/api/core';
import { toast } from 'react-hot-toast';
import { ArrowLeft, Save } from 'lucide-react';
import StationHeader from '../../../../shared/components/StationHeader';
import { spreadsheetStyles } from '../../config/synopticConfig';

// Horas sinopticas UTC a filas locales (aproximado)
const synopRows = {
  "06Z": 2, "09Z": 5, "12Z": 8, "15Z": 11,
  "18Z": 14, "21Z": 17, "00Z": 20, "03Z": 23
};

function getInitialState() {
  return {
    daily: {
      temp_max: '', temp_min: '',
      rafaga_dir: '', rafaga_vel: '', rafaga_hora: '',
      hum_max: '', hum_min: '',
      pres_max: '', pres_min: '',
      insolac: '', radiac: '', lluvia: '',
      evap_tanque_a: '', punto_rocio: '', recorrido_viento: ''
    },
    hourly: {
      2: { lect_bar: '', term_anexo: '', correc_temp: '', pres_est: '', correc_alt: '', pres_nmm: '' },
      8: { lect_bar: '', term_anexo: '', correc_temp: '', pres_est: '', correc_alt: '', pres_nmm: '' },
      14: { lect_bar: '', term_anexo: '', correc_temp: '', pres_est: '', correc_alt: '', pres_nmm: '' },
      20: { lect_bar: '', term_anexo: '', correc_temp: '', pres_est: '', correc_alt: '', pres_nmm: '' }
    },
    subsuelo: { d5: '', d10: '', d15: '', d20: '', d25: '', d50: '', d100: '' },
    evaporimetros: { piche: '', tanque_c: '', evaporigrafo: '' },
    iniciales_obs: '',
    observaciones_manuales: '',
    fenomenos: Array(12).fill(null).map(() => ({
      hora: '', min: '', raf_dir: '', raf_vel: '', intensidad: '',
      fenomeno: '', inicio: '', final: '', duracion: '', iniciales: ''
    }))
  };
}

const Cli5074Page = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [stations, setStations] = useState({});
  const [selectedStation, setSelectedStation] = useState(location.state?.stationId || '');
  const [isDataLoaded, setIsDataLoaded] = useState(false);

  const [date, setDate] = useState(() => {
    if (location.state?.date) return location.state.date;
    const today = new Date();
    return today.toISOString().split('T')[0];
  });

  const [formData, setFormData] = useState(() => getInitialState());

  const loadFormData = async (currentStation, currentDate) => {
    if (!currentStation || !currentDate) return;
    setIsDataLoaded(false);
    try {
      const draft = sessionStorage.getItem(`cli5074_draft_${currentStation}_${currentDate}`);
      if (draft) {
        setFormData(JSON.parse(draft));
        setIsDataLoaded(true);
        return;
      }

      const data = await invoke('load_cli5074_json', { stationId: currentStation, date: currentDate });
      if (data && Object.keys(data).length > 0 && data.daily) {
        setFormData(data);
      } else {
        const initial = getInitialState();
        
        // Autocompletar desde observacion sinoptica
        try {
          const synopData = await invoke('get_observation', {
            stationCode: currentStation,
            fecha: currentDate
          });

          if (synopData) {
            // Extraer T_max, T_min de las horas donde se reportan
            let maxT = -999, minT = 999;
            Object.values(synopData).forEach(horaData => {
              if (typeof horaData === 'object' && horaData !== null) {
                if (horaData.Tmax) {
                  const val = parseFloat(horaData.Tmax);
                  if (!isNaN(val) && val > maxT) maxT = val;
                }
                if (horaData.Tmin) {
                  const val = parseFloat(horaData.Tmin);
                  if (!isNaN(val) && val < minT) minT = val;
                }
              }
            });
            if (maxT !== -999) initial.daily.temp_max = maxT.toString();
            if (minT !== 999) initial.daily.temp_min = minT.toString();

            // Autocompletar Presiones (Horas 2, 8, 14, 20)
            const targetHours = [2, 8, 14, 20];
            Object.entries(synopRows).forEach(([horaZ, localH]) => {
              if (targetHours.includes(localH) && synopData[horaZ]) {
                const hd = synopData[horaZ];
                const presEst = hd.pres_est || '';
                const presNmm = hd.pres_nmm || '';
                
                // Si la correccion de altura no viene directamente, se calcula
                let correcAlt = hd.correc_alt || '';
                if (!correcAlt && presEst && presNmm) {
                  const pE = parseFloat(presEst);
                  const pN = parseFloat(presNmm);
                  if (!isNaN(pE) && !isNaN(pN)) {
                    correcAlt = (pN - pE).toFixed(1).replace('.0', '');
                  }
                }

                initial.hourly[localH] = {
                  ...initial.hourly[localH],
                  pres_est: presEst,
                  pres_nmm: presNmm,
                  correc_alt: correcAlt
                };
              }
            });

            // Mapeo basico a fenomenos
            const validHours = Object.keys(synopRows);
            let fIdx = 0;
            for (const horaKey of validHours) {
              const horaData = synopData[horaKey];
              if (!horaData) continue;
              
              const sevenWW = horaData.meteo_4_6 || horaData['7wwW1W2'] || '';
              if (sevenWW.length >= 5 && fIdx < 12) {
                const ww = sevenWW.substring(1, 3);
                const wwNum = parseInt(ww, 10);
                if (!isNaN(wwNum)) {
                  initial.fenomenos[fIdx].fenomeno = ww; // Guardar codigo
                  initial.fenomenos[fIdx].hora = synopRows[horaKey].toString();
                  initial.fenomenos[fIdx].min = '00';
                  fIdx++;
                }
              }
            }
          }
        } catch (e) {
          console.log("No existe data sinoptica base para autocompletar.", e);
        }
        setFormData(initial);
      }
    } catch (e) {
      console.error("Error cargando formulario", e);
    } finally {
      setIsDataLoaded(true);
    }
  };

  // Auto-guardar borrador en sessionStorage al modificar datos
  useEffect(() => {
    if (isDataLoaded && selectedStation && date) {
      sessionStorage.setItem(`cli5074_draft_${selectedStation}_${date}`, JSON.stringify(formData));
    }
  }, [formData, selectedStation, date, isDataLoaded]);

  useEffect(() => {
    const init = async () => {
      try {
        const stationData = await invoke('get_stations');
        setStations(stationData);
        await loadFormData(selectedStation, date);
      } catch (error) {
        console.error("Error en inicializacion:", error);
      }
    };
    init();
  }, []);

  useEffect(() => {
    if (Object.keys(stations).length > 0) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      loadFormData(selectedStation, date);
    }
  }, [selectedStation, date]);



  const updateSection = (section, field, value) => {
    setFormData(prev => ({
      ...prev,
      [section]: { ...prev[section], [field]: value }
    }));
  };

  const updateHourly = (hour, field, value) => {
    setFormData(prev => ({
      ...prev,
      hourly: {
        ...prev.hourly,
        [hour]: { ...prev.hourly[hour], [field]: value }
      }
    }));
  };

  const updateFenomeno = (index, field, value) => {
    setFormData(prev => {
      const newFenomenos = [...prev.fenomenos];
      newFenomenos[index] = { ...newFenomenos[index], [field]: value };
      return { ...prev, fenomenos: newFenomenos };
    });
  };



  // Clases CSS reutilizables
  const thClass = spreadsheetStyles.th;
  const subThClass = spreadsheetStyles.subTh;
  const tdHeaderClass = spreadsheetStyles.tdHeader;
  const inputStyle = spreadsheetStyles.input.rose;
  const tdBorder = spreadsheetStyles.tdBorder;

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col font-sans relative overflow-hidden pb-10">
      <div className="absolute top-0 left-0 w-full h-96 bg-gradient-to-b from-rose-600/10 to-transparent pointer-events-none"></div>

      {/* Header Info */}
      <div className="px-6 py-4 flex items-center gap-4 z-10 w-full max-w-full">
        <button
          onClick={() => navigate('/synoptic', { state: { stationId: selectedStation, date } })}
          className="w-10 h-10 rounded-full border border-slate-200 bg-white flex items-center justify-center text-slate-500 hover:text-rose-600 hover:bg-rose-50 hover:border-rose-200 hover:scale-105 shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-rose-500"
          title="Volver a Observaciones"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        
        <h1 className="text-2xl font-bold text-slate-800 tracking-tight">CLI 5074 - OBSERVACIONES EXTREMAS Y FENÓMENOS</h1>

        {/* Navegación Intra-CLI */}
        <div className="bg-slate-200/60 p-1 rounded-lg inline-flex gap-1 shadow-inner ml-4">
          <button
            onClick={() => {
              if (!selectedStation) {
                toast.error("Seleccione una estación primero.");
                return;
              }
              navigate('/cli3074', { state: { stationId: selectedStation, date } });
            }}
            className="px-3 py-1.5 rounded-md text-xs font-semibold transition-all text-slate-600 hover:bg-white/50"
          >
            3074
          </button>
          <button
            onClick={() => {
              if (!selectedStation) {
                toast.error("Seleccione una estación primero.");
                return;
              }
              navigate('/cli4074', { state: { stationId: selectedStation, date } });
            }}
            className="px-3 py-1.5 rounded-md text-xs font-semibold transition-all text-slate-600 hover:bg-white/50"
          >
            4074
          </button>
          <button
            onClick={() => navigate('/cli5074', { state: { stationId: selectedStation, date } })}
            className="px-3 py-1.5 rounded-md text-xs font-bold transition-all bg-white text-rose-700 shadow-sm"
          >
            5074
          </button>
        </div>

        {/* Acceso Rápido Horas Synop */}
        <div className="bg-slate-200/60 p-1 rounded-lg inline-flex gap-1 shadow-inner ml-4 items-center flex-wrap">
          <span className="text-[10px] font-bold text-slate-500 uppercase px-2">Ver Hora Synop:</span>
          {['00Z', '03Z', '06Z', '09Z', '12Z', '15Z', '18Z', '21Z'].map(h => (
            <button
              key={h}
              onClick={() => {
                if (!selectedStation) {
                  toast.error("Seleccione una estación primero.");
                  return;
                }
                navigate('/synoptic', { state: { stationId: selectedStation, date, activeHour: h } });
              }}
              className="px-2 py-1 rounded bg-white hover:bg-rose-50 hover:text-rose-700 hover:scale-105 active:scale-95 transition-all text-[11px] font-bold text-slate-600 shadow-sm cursor-pointer"
            >
              {h}
            </button>
          ))}
        </div>


      </div>

      {/* Metadatos Estacion */}
      <StationHeader 
        selectedStation={selectedStation}
        setSelectedStation={setSelectedStation}
        date={date}
        setDate={setDate}
        stations={stations}
        colorTheme="rose"
        isLocked={true}
      />

      <div className="mx-6 flex flex-col gap-6 z-10">
        
        {/* TABLA SUPERIOR (Daily Summary) */}
        <div className="bg-white rounded-lg shadow-md border border-slate-300 overflow-x-auto">
          <table className="w-full text-center border-collapse">
            <thead className="bg-slate-900">
              <tr>
                <th colSpan="2" className={`${thClass} bg-rose-800/80`}>TEMPERATURA ºC</th>
                <th colSpan="2" className={`${thClass} bg-orange-800/80`}>RÁFAGA MÁXIMA</th>
                <th colSpan="2" className={`${thClass} bg-sky-800/80`}>HUM. REL. (%)</th>
                <th colSpan="2" className={`${thClass} bg-indigo-800/80`}>PRESIÓN ESTACIÓN (hPa)</th>
                <th className={`${thClass} bg-amber-600/80`}>INSOLAC</th>
                <th className={`${thClass} bg-amber-700/80`}>RADIAC</th>
                <th className={`${thClass} bg-cyan-700/80`}>LLUVIA</th>
                <th className={`${thClass} bg-blue-700/80`}>EVAPOR.<br/>TANQUE A</th>
                <th className={`${thClass} bg-teal-700/80`}>PUNTO<br/>DE ROCÍO</th>
                <th className={`${thClass} bg-slate-700`}>RECORRIDO<br/>DEL VIENTO</th>
              </tr>
              <tr className="bg-slate-800">
                <th className={subThClass}>Máxima</th>
                <th className={subThClass}>Mínima</th>
                <th className={subThClass}>DIR.-VEL. (M/S)</th>
                <th className={subThClass}>Hora Local</th>
                <th className={subThClass}>Máx</th>
                <th className={subThClass}>Mín</th>
                <th className={subThClass}>Máxima</th>
                <th className={subThClass}>Mínima</th>
                <th className={subThClass}>HORA</th>
                <th className={subThClass}>CAL/CM²</th>
                <th className={subThClass}>(mm)</th>
                <th className={subThClass}>(mm)</th>
                <th className={subThClass}>(ºC)</th>
                <th className={subThClass}>(km)</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className={tdBorder}><input className={inputStyle} value={formData.daily.temp_max} onChange={e => updateSection('daily', 'temp_max', e.target.value)} /></td>
                <td className={tdBorder}><input className={inputStyle} value={formData.daily.temp_min} onChange={e => updateSection('daily', 'temp_min', e.target.value)} /></td>
                
                <td className={tdBorder}>
                  <div className="flex h-full">
                    <input className={`${inputStyle} border-r border-slate-200`} placeholder="Dir" value={formData.daily.rafaga_dir} onChange={e => updateSection('daily', 'rafaga_dir', e.target.value)} />
                    <input className={inputStyle} placeholder="Vel" value={formData.daily.rafaga_vel} onChange={e => updateSection('daily', 'rafaga_vel', e.target.value)} />
                  </div>
                </td>
                <td className={tdBorder}><input className={inputStyle} value={formData.daily.rafaga_hora} onChange={e => updateSection('daily', 'rafaga_hora', e.target.value)} placeholder="HH:MM" /></td>
                
                <td className={tdBorder}><input className={inputStyle} value={formData.daily.hum_max} onChange={e => updateSection('daily', 'hum_max', e.target.value)} /></td>
                <td className={tdBorder}><input className={inputStyle} value={formData.daily.hum_min} onChange={e => updateSection('daily', 'hum_min', e.target.value)} /></td>
                
                <td className={tdBorder}><input className={inputStyle} value={formData.daily.pres_max} onChange={e => updateSection('daily', 'pres_max', e.target.value)} /></td>
                <td className={tdBorder}><input className={inputStyle} value={formData.daily.pres_min} onChange={e => updateSection('daily', 'pres_min', e.target.value)} /></td>
                
                <td className={tdBorder}><input className={inputStyle} value={formData.daily.insolac} onChange={e => updateSection('daily', 'insolac', e.target.value)} /></td>
                <td className={tdBorder}><input className={inputStyle} value={formData.daily.radiac} onChange={e => updateSection('daily', 'radiac', e.target.value)} /></td>
                <td className={tdBorder}><input className={inputStyle} value={formData.daily.lluvia} onChange={e => updateSection('daily', 'lluvia', e.target.value)} /></td>
                <td className={tdBorder}><input className={inputStyle} value={formData.daily.evap_tanque_a} onChange={e => updateSection('daily', 'evap_tanque_a', e.target.value)} /></td>
                <td className={tdBorder}><input className={inputStyle} value={formData.daily.punto_rocio} onChange={e => updateSection('daily', 'punto_rocio', e.target.value)} /></td>
                <td className={tdBorder}><input className={inputStyle} value={formData.daily.recorrido_viento} onChange={e => updateSection('daily', 'recorrido_viento', e.target.value)} /></td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* CONTENEDOR MEDIO: 3 bloques */}
        <div className="flex flex-col xl:flex-row gap-6">
          
          {/* Bloque Izquierdo: Hourly (Transpuesto) */}
          <div className="bg-white rounded-lg shadow-md border border-slate-300 overflow-hidden flex-1 max-w-2xl">
            <table className="w-full border-collapse">
              <thead>
                <tr>
                  <th className={`${thClass} bg-slate-700 w-1/3`}>HORA LOCAL</th>
                  <th className={`${thClass} bg-rose-800/90 w-1/6`}>2</th>
                  <th className={`${thClass} bg-rose-800/90 w-1/6`}>8</th>
                  <th className={`${thClass} bg-rose-800/90 w-1/6`}>14</th>
                  <th className={`${thClass} bg-rose-800/90 w-1/6`}>20</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { label: "LECT. BAR (mmHg)", key: "lect_bar" },
                  { label: "TERM. ANEXO (ºC)", key: "term_anexo" },
                  { label: "CORREC. TEMP.", key: "correc_temp" },
                  { label: "PRES. EST. (hPa)", key: "pres_est" },
                  { label: "CORREC. ALT.", key: "correc_alt" },
                  { label: "PRES. NMM (hPa)", key: "pres_nmm" }
                ].map((row) => (
                  <tr key={row.key} className="border-b border-slate-200">
                    <th className={tdHeaderClass}>{row.label}</th>
                    {[2, 8, 14, 20].map(h => (
                      <td key={h} className={tdBorder}>
                        <input className={inputStyle} value={formData.hourly[h][row.key]} onChange={e => updateHourly(h, row.key, e.target.value)} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Bloque Derecho: Subsuelo y Evap */}
          <div className="flex flex-col gap-6 flex-1">
            
            {/* Subsuelo */}
            <div className="bg-white rounded-lg shadow-md border border-slate-300 overflow-hidden">
              <table className="w-full text-center border-collapse">
                <thead>
                  <tr>
                    <th colSpan="8" className={`${thClass} bg-amber-800/90`}>TEMPERATURA SUBSUELO</th>
                  </tr>
                  <tr>
                    <th className={`${subThClass} bg-slate-200 text-slate-700 w-16`}>(cm)</th>
                    <th className={subThClass}>5</th>
                    <th className={subThClass}>10</th>
                    <th className={subThClass}>15</th>
                    <th className={subThClass}>20</th>
                    <th className={subThClass}>25</th>
                    <th className={subThClass}>50</th>
                    <th className={subThClass}>100</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <th className={`${tdHeaderClass} text-center`}>(ºC)</th>
                    {['d5', 'd10', 'd15', 'd20', 'd25', 'd50', 'd100'].map(d => (
                      <td key={d} className={tdBorder}>
                        <input className={inputStyle} value={formData.subsuelo[d]} onChange={e => updateSection('subsuelo', d, e.target.value)} />
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Evaporimetros & Iniciales */}
            <div className="flex gap-4">
              <div className="bg-white rounded-lg shadow-md border border-slate-300 overflow-hidden flex-1">
                <table className="w-full text-center border-collapse">
                  <thead>
                    <tr>
                      <th colSpan="3" className={`${thClass} bg-blue-800/90 text-xs py-1`}>EVAP. 0.00 A 0.00 HL</th>
                    </tr>
                    <tr>
                      <th className={subThClass}>PICHE</th>
                      <th className={subThClass}>TANQUE C.</th>
                      <th className={`${subThClass} text-[10px]`}>EVAPORÍGRAFO</th>
                    </tr>
                    <tr>
                      <th className={`${subThClass} bg-slate-200 text-slate-700`}>(mm)</th>
                      <th className={`${subThClass} bg-slate-200 text-slate-700`}>(mm)</th>
                      <th className={`${subThClass} bg-slate-200 text-slate-700`}>(mm)</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td className={tdBorder}><input className={inputStyle} value={formData.evaporimetros.piche} onChange={e => updateSection('evaporimetros', 'piche', e.target.value)} /></td>
                      <td className={tdBorder}><input className={inputStyle} value={formData.evaporimetros.tanque_c} onChange={e => updateSection('evaporimetros', 'tanque_c', e.target.value)} /></td>
                      <td className={tdBorder}><input className={inputStyle} value={formData.evaporimetros.evaporigrafo} onChange={e => updateSection('evaporimetros', 'evaporigrafo', e.target.value)} /></td>
                    </tr>
                  </tbody>
                </table>
              </div>
              
              <div className="bg-white rounded-lg shadow-md border border-slate-300 flex-1 flex flex-col overflow-hidden">
                 <div className={`${thClass} bg-slate-700 h-1/2 flex items-center justify-center`}>
                    INICIALES OBS.
                 </div>
                 <div className="flex-1">
                    <input 
                      className={`${inputStyle} text-lg font-bold tracking-widest text-slate-700 bg-slate-50`} 
                      maxLength="5" 
                      value={formData.iniciales_obs} 
                      onChange={e => setFormData(prev => ({...prev, iniciales_obs: e.target.value}))} 
                    />
                 </div>
              </div>
            </div>

          </div>
        </div>

        {/* PARTE INFERIOR: Notas y Ráfagas */}
        <div className="flex flex-col lg:flex-row gap-6">
          
          {/* Área en Blanco (Notas Manuales) */}
          <div className="bg-white rounded-lg shadow-md border border-slate-300 flex-1 flex flex-col overflow-hidden min-w-[300px]">
            <div className={`${thClass} bg-slate-700`}>
              OBSERVACIONES Y DETALLES DEL FENÓMENO
            </div>
            <textarea 
              className="w-full flex-1 bg-transparent p-4 text-slate-700 text-[13px] font-mono focus:ring-inset focus:ring-2 focus:ring-rose-500 focus:outline-none resize-none min-h-[300px]"
              placeholder="Espacio destinado a detallar más información de forma manual..."
              value={formData.observaciones_manuales}
              onChange={e => setFormData(prev => ({ ...prev, observaciones_manuales: e.target.value }))}
            />
          </div>

          {/* TABLA INFERIOR: RÁFAGAS Y FENÓMENOS */}
          <div className="bg-white rounded-lg shadow-md border border-slate-300 overflow-x-auto flex-[3]">
            <table className="w-full text-center border-collapse">
              <thead className="bg-slate-900">
                <tr>
                  <th colSpan="2" className={`${thClass} bg-slate-700 w-16`}>HORA LOCAL</th>
                  <th colSpan="2" className={`${thClass} bg-rose-800/80 w-24`}>RÁFAGAS DE VIENTO</th>
                  <th rowSpan="2" className={`${thClass} bg-orange-700/80 w-14`}>INTENSIDAD</th>
                  <th rowSpan="2" className={`${thClass} bg-indigo-700/80 min-w-[120px] w-auto`}>FENÓMENOS<br/>METEOROLÓGICOS</th>
                  <th rowSpan="2" className={`${thClass} bg-teal-700/80 w-16`}>INICIO<br/>(HH:MM)</th>
                  <th rowSpan="2" className={`${thClass} bg-sky-700/80 w-16`}>FINAL<br/>(HH:MM)</th>
                  <th rowSpan="2" className={`${thClass} bg-fuchsia-700/80 w-16`}>DURACIÓN</th>
                  <th rowSpan="2" className={`${thClass} bg-slate-600 w-16`}>INICIALES<br/>OBSERV.</th>
                </tr>
                <tr className="bg-slate-800">
                  <th className={subThClass}>HORAS</th>
                  <th className={subThClass}>MINUTOS</th>
                  <th className={subThClass}>dd 16-P</th>
                  <th className={subThClass}>ff (m/s)</th>
                </tr>
              </thead>
              <tbody>
                {formData.fenomenos.map((row, i) => (
                  <tr key={i} className="hover:bg-rose-50 transition-colors">
                    <td className={tdBorder}><input className={inputStyle} maxLength="2" value={row.hora} onChange={e => updateFenomeno(i, 'hora', e.target.value)} /></td>
                    <td className={tdBorder}><input className={inputStyle} maxLength="2" value={row.min} onChange={e => updateFenomeno(i, 'min', e.target.value)} /></td>
                    
                    <td className={tdBorder}><input className={inputStyle} maxLength="2" value={row.raf_dir} onChange={e => updateFenomeno(i, 'raf_dir', e.target.value)} /></td>
                    <td className={tdBorder}><input className={inputStyle} maxLength="5" value={row.raf_vel} onChange={e => updateFenomeno(i, 'raf_vel', e.target.value)} /></td>
                    
                    <td className={tdBorder}><input className={inputStyle} value={row.intensidad} onChange={e => updateFenomeno(i, 'intensidad', e.target.value)} /></td>
                    <td className={tdBorder}><input className={`${inputStyle} text-left px-2`} value={row.fenomeno} onChange={e => updateFenomeno(i, 'fenomeno', e.target.value)} placeholder="Ej: Tormenta, Granizo..." /></td>
                    
                    <td className={tdBorder}><input className={inputStyle} maxLength="5" value={row.inicio} onChange={e => updateFenomeno(i, 'inicio', e.target.value)} /></td>
                    <td className={tdBorder}><input className={inputStyle} maxLength="5" value={row.final} onChange={e => updateFenomeno(i, 'final', e.target.value)} /></td>
                    <td className={tdBorder}><input className={inputStyle} maxLength="5" value={row.duracion} onChange={e => updateFenomeno(i, 'duracion', e.target.value)} /></td>
                    
                    <td className={tdBorder}><input className={inputStyle} maxLength="5" value={row.iniciales} onChange={e => updateFenomeno(i, 'iniciales', e.target.value)} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </div>
  );
};

export default Cli5074Page;
