/**
 * CLI 4074 - Formulario de Nubosidad y Temperatura
 * 
 * Estructura basada en CSV oficial del CLI 4074:
 * - Nubosidad total (N)
 * - Cúmulonimbos: Cantidad, Tipo, Altura base
 * - Nubes Bajas: Cantidad, Tipo, Dirección, Altura base
 * - Nubes Medias: Cantidad, Tipo, Dirección, Altura base
 * - Nubes Altas: Cantidad, Tipo, Dirección, Altura base
 * - Lluvia 6H (mm)
 * - Temperaturas: Máx, Mín (solo horas sinópticas principales)
 * - Estado del suelo
 * - Iniciales del observador
 */

import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { invoke } from '@tauri-apps/api/core';

/**
 * Mapeo de horas sinópticas UTC a filas del formulario (horas locales)
 * Horas con T_max/T_min: 00Z, 06Z, 12Z, 18Z (filas 20, 2, 8, 14)
 */
const synopRows = {
  "06Z": 2, "09Z": 5, "12Z": 8, "15Z": 11,
  "18Z": 14, "21Z": 17, "00Z": 20, "03Z": 23
};

// Horas donde se registran T_max y T_min (sinópticas principales)
const tempHours = ["00Z", "06Z", "12Z", "18Z"];

const Cli4074Page = () => {
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
        // Nubosidad total
        nubosidad: '',

        // Cúmulonimbos
        cb_cant: '',
        cb_tipo: '',
        cb_altura: '',

        // Nubes Bajas (CL)
        nb_cant: '',
        nb_tipo: '',
        nb_direc: '',
        nb_altura: '',
        nb_total: '', // TOTAL nubes bajas

        // Nubes Medias (CM)
        nm_cant: '',
        nm_tipo: '',
        nm_direc: '',
        nm_altura: '',
        nm_total: '', // TOTAL nubes medias

        // Nubes Altas (CH)
        na_cant: '',
        na_tipo: '',
        na_direc: '',
        na_altura: '',
        na_total: '', // TOTAL nubes altas

        // Lluvia y Temperaturas
        lluvia_6h: '',
        temp_max: '',
        temp_min: '',

        // Estado del suelo y observador
        estado_suelo: '',
        observador: ''
      };
    }
    return initial;
  });

  /**
   * Parsear grupo 8NsChshs y llenar datos de nubes
   * 
   * Estructura del grupo: 8NsChshs
   * - 8 = indicador de grupo
   * - Ns = cantidad de nubes (1-8 octavos)
   * - C = tipo de nube:
   *   - 9 = Cumulonimbus (CB)
   *   - 8, 7, 6 = Nubes Bajas (CL)
   *   - 5, 4, 3 = Nubes Medias (CM)
   *   - 2, 1, 0 = Nubes Altas (CH)
   * - hshs = altura en código (convertir a metros)
   * 
   * @param {string} grupo8 - Grupo 8NsChshs (ej: "81918", "81080")
   * @returns {Object} - Datos parseados de nubes
   */
  const parseGrupo8 = (grupo8) => {
    if (!grupo8 || grupo8.length < 5 || grupo8[0] !== '8') {
      return null;
    }

    const Ns = grupo8[1]; // Cantidad (1-8)
    const C = grupo8[2]; // Tipo de nube
    const hshs = grupo8.substring(3, 5); // Altura código

    const resultado = {
      cantidad: Ns,
      tipo: C,
      alturaCodigo: hshs,
      alturaMetros: convertCloudHeight(hshs)
    };

    // Clasificar por tipo de nube
    if (C === '9') {
      resultado.categoria = 'cb'; // Cumulonimbus
    } else if (['8', '7', '6'].includes(C)) {
      resultado.categoria = 'nb'; // Nubes Bajas (CL)
    } else if (['5', '4', '3'].includes(C)) {
      resultado.categoria = 'nm'; // Nubes Medias (CM)
    } else if (['2', '1', '0'].includes(C)) {
      resultado.categoria = 'na'; // Nubes Altas (CH)
    } else {
      resultado.categoria = 'unknown';
    }

    return resultado;
  };

  /**
   * Procesar múltiples grupos 8 y llenar una fila del CLI 4074
   * 
   * @param {Object} rowData - Fila a llenar
   * @param {Array} grupos8 - Array de grupos 8 (ej: ["81918", "81080"])
   * @returns {Object} - Fila con datos de nubes
   */
  const procesarGrupos8 = (rowData, grupos8) => {
    const datos = { ...rowData };

    // Reinicializar campos de nubes
    datos.cb_cant = ''; datos.cb_tipo = ''; datos.cb_altura = '';
    datos.nb_cant = ''; datos.nb_tipo = ''; datos.nb_altura = ''; datos.nb_total = '';
    datos.nm_cant = ''; datos.nm_tipo = ''; datos.nm_altura = ''; datos.nm_total = '';
    datos.na_cant = ''; datos.na_tipo = ''; datos.na_altura = ''; datos.na_total = '';

    // Contadores para los TOTAL
    let totalCB = 0;
    let totalNB = 0;
    let totalNM = 0;
    let totalNA = 0;

    // Procesar cada grupo 8
    for (const grupo of grupos8) {
      const parsed = parseGrupo8(grupo);
      if (!parsed) continue;

      const cant = parseInt(parsed.cantidad, 10) || 0;

      switch (parsed.categoria) {
        case 'cb':
          // Solo guardar el último Cumulonimbus (generalmente hay uno solo)
          datos.cb_cant = parsed.cantidad;
          datos.cb_tipo = parsed.tipo;
          datos.cb_altura = parsed.alturaMetros;
          totalCB += cant;
          break;

        case 'nb':
          // Nubes Bajas
          datos.nb_cant = parsed.cantidad;
          datos.nb_tipo = parsed.tipo;
          datos.nb_altura = parsed.alturaMetros;
          totalNB += cant;
          break;

        case 'nm':
          // Nubes Medias
          datos.nm_cant = parsed.cantidad;
          datos.nm_tipo = parsed.tipo;
          datos.nm_altura = parsed.alturaMetros;
          totalNM += cant;
          break;

        case 'na':
          // Nubes Altas
          datos.na_cant = parsed.cantidad;
          datos.na_tipo = parsed.tipo;
          datos.na_altura = parsed.alturaMetros;
          totalNA += cant;
          break;
      }
    }

    // Asignar totales
    datos.nb_total = totalNB > 0 ? totalNB.toString() : '';
    datos.nm_total = totalNM > 0 ? totalNM.toString() : '';
    datos.na_total = totalNA > 0 ? totalNA.toString() : '';

    // Nubosidad total = suma de todas las cantidades
    const nubosidadTotal = totalCB + totalNB + totalNM + totalNA;
    datos.nubosidad = nubosidadTotal > 0 ? Math.min(nubosidadTotal, 8).toString() : '';

    return datos;
  };

  const loadFormData = async (currentStation, currentDate) => {
    if (!currentStation || !currentDate) return;
    try {
      const data = await invoke('load_cli4074_json', { stationId: currentStation, date: currentDate });
      if (data && Object.keys(data).length > 0) {
        setRows(data);
      } else {
        // Initialize empty
        const initial = {};
        for (let i = 1; i <= 24; i++) {
        initial[i] = {
          nubosidad: '',
          cb_cant: '', cb_tipo: '', cb_altura: '',
          nb_cant: '', nb_tipo: '', nb_direc: '', nb_altura: '', nb_total: '',
          nm_cant: '', nm_tipo: '', nm_direc: '', nm_altura: '', nm_total: '',
          na_cant: '', na_tipo: '', na_direc: '', na_altura: '', na_total: '',
          lluvia_6h: '', temp_max: '', temp_min: '',
          estado_suelo: '', observador: ''
        };
        }

        // Autocompletar desde observación sinóptica
        try {
          const synopData = await invoke('get_observation', {
            stationCode: currentStation,
            fecha: currentDate
          });

          if (synopData) {
            const validHours = Object.keys(synopRows);
            for (const horaKey of validHours) {
              const horaData = synopData[horaKey];
              if (!horaData) continue;

              const rowNum = synopRows[horaKey];

              // Recopilar todos los grupos 8 disponibles
              // Puede haber hasta 6 grupos 8: meteo_8_1, meteo_8_2, etc.
              const grupos8 = [];
              
              // Buscar grupos 8 en diferentes formatos posibles
              for (let g = 1; g <= 6; g++) {
                const grupoKey = `meteo_8_${g}`;
                const grupoValue = horaData[grupoKey] || horaData[`8NsChshs_${g}`] || '';
                if (grupoValue && grupoValue.startsWith('8') && grupoValue.length >= 5) {
                  grupos8.push(grupoValue);
                }
              }

              // También buscar un grupo 8 único
              const grupo8Unico = horaData.meteo_8 || horaData['8NsChshs'] || '';
              if (grupo8Unico && grupo8Unico.startsWith('8') && grupo8Unico.length >= 5) {
                // Verificar si no está ya en la lista
                if (!grupos8.includes(grupo8Unico)) {
                  grupos8.push(grupo8Unico);
                }
              }

              // Procesar todos los grupos 8 y llenar la fila
              if (grupos8.length > 0) {
                initial[rowNum] = procesarGrupos8(initial[rowNum], grupos8);
              } else {
                // Si no hay grupos 8, usar nubosidad desde Nddff
                const nddff = horaData.meteo_4_1 || horaData.Nddff || '';
                if (nddff.length >= 1 && nddff[0] !== '/') {
                  initial[rowNum].nubosidad = nddff[0];
                }
              }

              // Temperaturas (solo horas principales)
              if (tempHours.includes(horaKey)) {
                initial[rowNum].temp_max = horaData.t_max || '';
                initial[rowNum].temp_min = horaData.t_min || '';
              }
            }
          }
        } catch (e) {
          console.log("No existe data sinóptica base para autocompletar.", e);
        }
        setRows(initial);
      }
    } catch (e) {
      console.error("Error cargando formulario", e);
    }
  };

  useEffect(() => {
    const init = async () => {
      try {
        const stationData = await invoke('get_stations');
        setStations(stationData);
        await loadFormData(selectedStation, date);
      } catch (error) {
        console.error("Error en inicialización:", error);
      }
    };
    init();
  }, []);

  useEffect(() => {
    if (Object.keys(stations).length > 0) {
      loadFormData(selectedStation, date);
    }
  }, [selectedStation, date]);

  /**
   * Escuchar cambios en el draft del formulario sinóptico
   * Cuando se actualiza el sinóptico, recargar datos automáticamente
   */
  useEffect(() => {
    const DRAFT_KEY = 'synoptic_draft';

    const checkDraftUpdate = (e) => {
      if (e.key === DRAFT_KEY && e.newValue) {
        try {
          const draft = JSON.parse(e.newValue);
          if (draft?.observations && selectedStation && date) {
            // Procesar las observaciones del draft
            const initial = {};
            for (let i = 1; i <= 24; i++) {
              initial[i] = {
                nubosidad: '',
                cb_cant: '', cb_tipo: '', cb_altura: '',
                nb_cant: '', nb_tipo: '', nb_direc: '', nb_altura: '', nb_total: '',
                nm_cant: '', nm_tipo: '', nm_direc: '', nm_altura: '', nm_total: '',
                na_cant: '', na_tipo: '', na_direc: '', na_altura: '', na_total: '',
                lluvia_6h: '', temp_max: '', temp_min: '',
                estado_suelo: '', observador: ''
              };
            }

            const validHours = Object.keys(synopRows);
            for (const horaKey of validHours) {
              const horaData = draft.observations[horaKey];
              if (!horaData) continue;

              const rowNum = synopRows[horaKey];

              // Recopilar grupos 8
              const grupos8 = [];
              for (let g = 0; g <= 6; g++) {
                const grupoKey = g === 0 ? 'meteo_8' : `meteo_8_${g}`;
                const grupoValue = horaData[grupoKey] || '';
                if (grupoValue && grupoValue.startsWith('8') && grupoValue.length >= 5) {
                  grupos8.push(grupoValue);
                }
              }

              if (grupos8.length > 0) {
                initial[rowNum] = procesarGrupos8(initial[rowNum], grupos8);
              }

              // Temperaturas
              if (tempHours.includes(horaKey)) {
                initial[rowNum].temp_max = horaData.t_max || horaData.meteo_6_3?.substring(1) || '';
                initial[rowNum].temp_min = horaData.t_min || horaData.meteo_6_4?.substring(1) || '';
              }
            }

            setRows(prev => ({ ...prev, ...initial }));
          }
        } catch (err) {
          console.warn('Error procesando draft actualizado:', err);
        }
      }
    };

    window.addEventListener('storage', checkDraftUpdate);
    return () => window.removeEventListener('storage', checkDraftUpdate);
  }, [selectedStation, date]);

  const stInfo = selectedStation && stations[selectedStation] ? stations[selectedStation] : null;

  const updateRowField = (rowNum, field, value) => {
    // Convertir automáticamente código de altura a metros
    const autoConvertHeight = (fieldName, newValue) => {
      // Buscar el campo de altura correspondiente
      if (fieldName.endsWith('_altura') || fieldName === 'cb_altura' || fieldName === 'nb_altura' || fieldName === 'nm_altura' || fieldName === 'na_altura') {
        return convertCloudHeight(newValue);
      }
      return newValue;
    };

    setRows(prev => ({
      ...prev,
      [rowNum]: { 
        ...prev[rowNum], 
        [field]: autoConvertHeight(field, value)
      }
    }));
  };

  /**
   * Convertir código de altura de nubes (h) a metros
   * Basado en WMO Code Table 1677
   * 
   * Nubes Bajas (CL): códigos 3-50 → 300-5000 pies
   * Nubes Medias (CM): códigos 56-68 → 6000-18000 pies
   * Nubes Altas (CH): códigos 69-80 → 19000-30000 pies
   * 
   * @param {string} code - Código de altura (h)
   * @returns {string} - Altura en metros
   */
  const convertCloudHeight = (code) => {
    if (!code || code === '/') return '';
    
    const h = parseInt(code, 10);
    if (isNaN(h)) return '';
    
    let feet;
    if (h >= 3 && h <= 50) {
      // Nubes Bajas: 300-5000 pies (incrementos de ~100 pies)
      feet = 300 + (h - 3) * 100;
    } else if (h >= 56 && h <= 68) {
      // Nubes Medias: 6000-18000 pies (incrementos de ~1000 pies)
      feet = 6000 + (h - 56) * 1000;
    } else if (h >= 69 && h <= 80) {
      // Nubes Altas: 19000-30000 pies
      feet = 19000 + (h - 69) * 1000;
    } else {
      return code; // Código fuera de rango, retornar tal cual
    }
    
    // Convertir pies a metros (1 pie = 0.3048 m)
    // Usar truncado (Math.floor) sin decimales
    const meters = Math.floor(feet * 0.3048);
    return meters.toString();
  };

  const handleSave = async () => {
    if (!selectedStation) {
      alert("Seleccione una estación primero.");
      return;
    }
    try {
      await invoke('save_cli4074_json', { stationId: selectedStation, date, data: rows });
      alert("✓ Formulario CLI 4074 guardado exitosamente");
    } catch (err) {
      alert("✗ Error al guardar el formulario: " + err);
    }
  };

  // Estilos heredados del CLI 3074
  const thClass = "border border-slate-700 bg-slate-800/90 text-white font-bold text-sm py-2 px-1 align-middle whitespace-nowrap overflow-hidden";
  const subThClass = "border border-slate-600 bg-slate-700/80 text-white text-xs font-semibold py-1 px-1";

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col font-sans relative overflow-hidden">
      {/* Aesthetic Background Effect */}
      <div className="absolute top-0 left-0 w-full h-96 bg-gradient-to-b from-emerald-600/10 to-transparent pointer-events-none"></div>

      {/* Header */}
      <div className="px-6 py-4 flex items-center gap-4 z-10 w-full max-w-full">
        <button
          onClick={() => navigate('/synoptic')}
          className="px-4 py-2 bg-white border border-slate-300 rounded-lg shadow-sm text-sm font-medium hover:bg-slate-50 transition-colors text-slate-700 flex items-center gap-2"
        >
          <span>←</span> Volver a Observaciones
        </button>
        <h1 className="text-2xl font-bold text-slate-800 tracking-tight">CLI 4074 - NUBOSIDAD Y TEMPERATURA</h1>

        <button onClick={handleSave} className="ml-auto px-6 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-bold rounded-lg shadow-md transition-all">
          Guardar Formulario
        </button>
      </div>

      {/* HEADER BLOCK - Info de estación */}
      <div className="mx-6 mb-4 p-4 bg-white border border-slate-200 border-t-4 border-t-emerald-500 shadow-sm rounded-lg z-10 max-w-full overflow-x-auto">
        <div className="flex flex-wrap items-center gap-x-8 gap-y-4">
          <div className="flex items-center gap-2">
            <label className="text-sm font-bold text-slate-700 uppercase">Estación:</label>
            <select
              value={selectedStation}
              onChange={(e) => setSelectedStation(e.target.value)}
              className="bg-slate-50 border border-slate-300 text-slate-800 text-sm rounded-md px-3 py-1.5 focus:ring-2 focus:ring-emerald-500"
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
              className="bg-slate-50 border border-slate-300 text-slate-800 text-sm rounded-md px-3 py-1.5 focus:ring-2 focus:ring-emerald-500"
            />
          </div>
        </div>
      </div>

      {/* SPREADSHEET CONTAINER */}
      <div className="mx-6 flex-1 z-10 bg-white rounded-lg shadow-[0px_4px_20px_rgba(0,0,0,0.1)] border border-slate-300 overflow-x-auto overflow-y-auto mb-6 max-h-[70vh] custom-scrollbar">
        <table className="w-full text-center border-collapse">
          <thead className="sticky top-0 z-20 shadow-sm bg-slate-900">
            <tr>
              <th rowSpan="2" className={`${thClass} min-w-[50px]`}>HORA<br/>LOCAL</th>
              <th rowSpan="2" className={`${thClass} min-w-[40px] bg-gray-700`}>N</th>
              
      {/* Cúmulonimbos */}
      <th colSpan="3" className={`${thClass} bg-purple-800/80`}>CÚMULONIMBOS</th>

      {/* Nubes Bajas */}
      <th colSpan="5" className={`${thClass} bg-slate-600`}>NUBES BAJAS (CL)</th>

      {/* Nubes Medias */}
      <th colSpan="5" className={`${thClass} bg-sky-800/80`}>NUBES MEDIAS (CM)</th>

      {/* Nubes Altas */}
      <th colSpan="5" className={`${thClass} bg-indigo-800/80`}>NUBES ALTAS (CH)</th>
              
              {/* Lluvia y Temps */}
              <th rowSpan="2" className={`${thClass} min-w-[60px] bg-cyan-800/80`}>LLUVIA<br/>6H (mm)</th>
              <th colSpan="2" className={`${thClass} bg-orange-800/80`}>TEMPS.</th>
              
              {/* Estado y Observador */}
              <th rowSpan="2" className={`${thClass} min-w-[50px] bg-amber-800/80`}>EST.<br/>SUELO</th>
              <th rowSpan="2" className={`${thClass} min-w-[50px] bg-teal-800/80`}>OBS.</th>
            </tr>
            <tr className="bg-slate-800">
              {/* Cúmulonimbos sub-headers */}
              <th className={subThClass}>Cant</th>
              <th className={subThClass}>Tipo</th>
              <th className={subThClass}>Altura</th>
              
      {/* Nubes Bajas sub-headers */}
      <th className={subThClass}>Cant</th>
      <th className={subThClass}>Tipo</th>
      <th className={subThClass}>Dir</th>
      <th className={subThClass}>Altura</th>
      <th className={`${subThClass} bg-green-700`}>TOTAL</th>

      {/* Nubes Medias sub-headers */}
      <th className={subThClass}>Cant</th>
      <th className={subThClass}>Tipo</th>
      <th className={subThClass}>Dir</th>
      <th className={subThClass}>Altura</th>
      <th className={`${subThClass} bg-blue-700`}>TOTAL</th>

      {/* Nubes Altas sub-headers */}
      <th className={subThClass}>Cant</th>
      <th className={subThClass}>Tipo</th>
      <th className={subThClass}>Dir</th>
      <th className={subThClass}>Altura</th>
      <th className={`${subThClass} bg-indigo-700`}>TOTAL</th>
              
              {/* Temps sub-headers */}
              <th className={subThClass}>Máx</th>
              <th className={subThClass}>Mín</th>
            </tr>
          </thead>
          <tbody className="bg-white">
            {Object.keys(rows).map((rowStr) => {
              const i = parseInt(rowStr);
              const row = rows[i];

              // Resaltar filas sinópticas (cada 3 horas desde la 2)
              const isMainHour = (i - 2) % 3 === 0;
              const trClass = isMainHour 
                ? 'bg-emerald-50 shadow-[inset_0_1px_2px_rgba(0,0,0,0.05)] font-medium' 
                : 'bg-white hover:bg-slate-50';

              const inputStyle = `w-full text-center bg-transparent border-none focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:bg-emerald-100/50 text-slate-800 text-[13px] font-mono h-[30px] ${isMainHour ? "font-semibold text-slate-900" : ""}`;
              const tdBorder = "border-[1px] border-slate-200 p-0 m-0 h-[30px] overflow-hidden";

              return (
                <tr key={i} className={`transition-colors ${trClass}`}>
                  {/* Hora Local */}
                  <td className={`border border-slate-300 font-bold text-sm sticky left-0 z-10 shadow-[2px_0_5px_-2px_rgba(0,0,0,0.1)] ${isMainHour ? 'bg-emerald-200 text-emerald-900' : 'bg-slate-100 text-slate-600'}`}>
                    {i}
                  </td>
                  
                  {/* N - Nubosidad */}
                  <td className={`${tdBorder} ${isMainHour ? 'bg-emerald-100/50' : ''}`}>
                    <input 
                      className={inputStyle} 
                      maxLength="1"
                      value={row.nubosidad} 
                      onChange={e => updateRowField(i, 'nubosidad', e.target.value)} 
                      title="Nubosidad total (0-8 octavos)"
                    />
                  </td>
                  
                  {/* Cúmulonimbos */}
                  <td className={tdBorder}>
                    <input className={inputStyle} maxLength="1" value={row.cb_cant} onChange={e => updateRowField(i, 'cb_cant', e.target.value)} />
                  </td>
                  <td className={tdBorder}>
                    <input className={inputStyle} maxLength="2" value={row.cb_tipo} onChange={e => updateRowField(i, 'cb_tipo', e.target.value)} />
                  </td>
                  <td className={tdBorder}>
                    <input className={inputStyle} maxLength="4" value={row.cb_altura} onChange={e => updateRowField(i, 'cb_altura', e.target.value)} />
                  </td>
                  
      {/* Nubes Bajas */}
      <td className={tdBorder}>
        <input className={inputStyle} maxLength="1" value={row.nb_cant} onChange={e => updateRowField(i, 'nb_cant', e.target.value)} />
      </td>
      <td className={tdBorder}>
        <input className={inputStyle} maxLength="2" value={row.nb_tipo} onChange={e => updateRowField(i, 'nb_tipo', e.target.value)} title="Código CL (OMM)" />
      </td>
      <td className={tdBorder}>
        <input className={inputStyle} maxLength="2" value={row.nb_direc} onChange={e => updateRowField(i, 'nb_direc', e.target.value)} />
      </td>
      <td className={tdBorder}>
        <input className={inputStyle} maxLength="4" value={row.nb_altura} onChange={e => updateRowField(i, 'nb_altura', e.target.value)} />
      </td>
      {/* TOTAL Nubes Bajas */}
      <td className={`${tdBorder} bg-green-100`}>
        <input 
          className={`${inputStyle} font-bold text-green-800`} 
          maxLength="1" 
          value={row.nb_total} 
          onChange={e => updateRowField(i, 'nb_total', e.target.value)} 
          title="Total nubes bajas (0-8)"
        />
      </td>

      {/* Nubes Medias */}
      <td className={tdBorder}>
        <input className={inputStyle} maxLength="1" value={row.nm_cant} onChange={e => updateRowField(i, 'nm_cant', e.target.value)} />
      </td>
      <td className={tdBorder}>
        <input className={inputStyle} maxLength="2" value={row.nm_tipo} onChange={e => updateRowField(i, 'nm_tipo', e.target.value)} title="Código CM (OMM)" />
      </td>
      <td className={tdBorder}>
        <input className={inputStyle} maxLength="2" value={row.nm_direc} onChange={e => updateRowField(i, 'nm_direc', e.target.value)} />
      </td>
      <td className={tdBorder}>
        <input className={inputStyle} maxLength="4" value={row.nm_altura} onChange={e => updateRowField(i, 'nm_altura', e.target.value)} />
      </td>
      {/* TOTAL Nubes Medias */}
      <td className={`${tdBorder} bg-blue-100`}>
        <input 
          className={`${inputStyle} font-bold text-blue-800`} 
          maxLength="1" 
          value={row.nm_total} 
          onChange={e => updateRowField(i, 'nm_total', e.target.value)} 
          title="Total nubes medias (0-8)"
        />
      </td>

      {/* Nubes Altas */}
      <td className={tdBorder}>
        <input className={inputStyle} maxLength="1" value={row.na_cant} onChange={e => updateRowField(i, 'na_cant', e.target.value)} />
      </td>
      <td className={tdBorder}>
        <input className={inputStyle} maxLength="2" value={row.na_tipo} onChange={e => updateRowField(i, 'na_tipo', e.target.value)} title="Código CH (OMM)" />
      </td>
      <td className={tdBorder}>
        <input className={inputStyle} maxLength="2" value={row.na_direc} onChange={e => updateRowField(i, 'na_direc', e.target.value)} />
      </td>
      <td className={tdBorder}>
        <input className={inputStyle} maxLength="4" value={row.na_altura} onChange={e => updateRowField(i, 'na_altura', e.target.value)} />
      </td>
      {/* TOTAL Nubes Altas */}
      <td className={`${tdBorder} bg-indigo-100`}>
        <input 
          className={`${inputStyle} font-bold text-indigo-800`} 
          maxLength="1" 
          value={row.na_total} 
          onChange={e => updateRowField(i, 'na_total', e.target.value)} 
          title="Total nubes altas (0-8)"
        />
      </td>
                  
                  {/* Lluvia 6H */}
                  <td className={`${tdBorder} bg-cyan-50/50`}>
                    <input className={inputStyle} maxLength="5" value={row.lluvia_6h} onChange={e => updateRowField(i, 'lluvia_6h', e.target.value)} />
                  </td>
                  
                  {/* Temperaturas (solo horas sinópticas principales) */}
                  <td className={`${tdBorder} ${tempHours.includes(Object.entries(synopRows).find(([h, r]) => r === i)?.[0] || '') ? 'bg-orange-50' : 'bg-slate-100'}`}>
                    <input 
                      className={inputStyle} 
                      maxLength="5" 
                      value={row.temp_max} 
                      onChange={e => updateRowField(i, 'temp_max', e.target.value)}
                      disabled={!tempHours.includes(Object.entries(synopRows).find(([h, r]) => r === i)?.[0] || '')}
                      title="Temperatura máxima (solo horas sinópticas)"
                    />
                  </td>
                  <td className={`${tdBorder} ${tempHours.includes(Object.entries(synopRows).find(([h, r]) => r === i)?.[0] || '') ? 'bg-blue-50' : 'bg-slate-100'}`}>
                    <input 
                      className={inputStyle} 
                      maxLength="5" 
                      value={row.temp_min} 
                      onChange={e => updateRowField(i, 'temp_min', e.target.value)}
                      disabled={!tempHours.includes(Object.entries(synopRows).find(([h, r]) => r === i)?.[0] || '')}
                      title="Temperatura mínima (solo horas sinópticas)"
                    />
                  </td>
                  
                  {/* Estado del suelo */}
                  <td className={tdBorder}>
                    <input className={inputStyle} maxLength="5" value={row.estado_suelo} onChange={e => updateRowField(i, 'estado_suelo', e.target.value)} title="Código estado del suelo" />
                  </td>
                  
                  {/* Observador */}
                  <td className={tdBorder}>
                    <input className={inputStyle} maxLength="5" value={row.observador} onChange={e => updateRowField(i, 'observador', e.target.value)} title="Iniciales del observador" />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Custom scrollbar styles */}
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

export default Cli4074Page;
