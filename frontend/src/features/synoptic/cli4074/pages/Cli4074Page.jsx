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
import { toast } from 'react-hot-toast';
import { ArrowLeft, Save } from 'lucide-react';
import StationHeader from '../../../../shared/components/StationHeader';
import { spreadsheetStyles } from '../../config/synopticConfig';

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

const decimalFields4074 = [
    'lluvia_6h', 'temp_max', 'temp_min'
];

const enforceOneDecimal = (val, field) => {
    if (val === undefined || val === null || val === '') return '';
    if (decimalFields4074.includes(field)) {
        if (typeof val === 'number') val = val.toString();
        if (typeof val === 'string' && val.trim() !== '') {
            const parts = val.split('.');
            if (parts.length > 1 && parts[1].length > 1) {
                const num = parseFloat(val);
                if (!isNaN(num)) {
                    const rounded = num >= 0 
                        ? Math.ceil(num * 10) / 10 
                        : Math.floor(num * 10) / 10;
                    return rounded.toFixed(1);
                }
            }
        }
    }
    return val;
};

const Cli4074Page = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [stations, setStations] = useState({});
  const [selectedStation, setSelectedStation] = useState(location.state?.stationId || location.state?.station || '');
  const [isDataLoaded, setIsDataLoaded] = useState(false);

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
    setIsDataLoaded(false);
    try {
      const draft = sessionStorage.getItem(`cli4074_draft_${currentStation}_${currentDate}`);
      if (draft) {
        const parsedDraft = JSON.parse(draft);
        for (let i = 1; i <= 24; i++) {
          if (parsedDraft[i]) {
            Object.keys(parsedDraft[i]).forEach(k => {
              parsedDraft[i][k] = enforceOneDecimal(parsedDraft[i][k], k);
            });
          }
        }
        setRows(parsedDraft);
        setIsDataLoaded(true);
        return;
      }

      const data = await invoke('load_cli4074_json', { stationId: currentStation, date: currentDate });
      
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

      if (data && Object.keys(data).length > 0) {
        for (let i = 1; i <= 24; i++) {
          if (data[i]) {
            const formattedData = { ...data[i] };
            Object.keys(formattedData).forEach(k => {
              formattedData[k] = enforceOneDecimal(formattedData[k], k);
            });
            initial[i] = { ...initial[i], ...formattedData };
          }
        }
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
            const row = initial[rowNum];

            // Autocompletar solo si la nubosidad y tipos de nubes están vacíos
            const isEmpty = !row.nubosidad && !row.nb_tipo && !row.nm_tipo && !row.na_tipo && !row.temp_max && !row.temp_min;

            if (isEmpty) {
              // Recopilar todos los grupos 8 disponibles
              const grupos8 = [];
              const keysGrupo8 = ['meteo_8_5', 'meteo_8_6', 'extra_8ns_1', 'extra_8ns_2', 'meteo_10_0', 'meteo_10_1'];
              for (const k of keysGrupo8) {
                const val = horaData[k] || '';
                if (val && val.startsWith('8') && val.length >= 5) {
                  grupos8.push(val);
                }
              }

              // Procesar todos los grupos 8 y llenar la fila
              if (grupos8.length > 0) {
                initial[rowNum] = procesarGrupos8(initial[rowNum], grupos8);
              }

              // 1. NUBOSIDAD TOTAL: siempre usar N de Nddff (meteo_4_1) si está disponible,
              // de lo contrario usar lo calculado por procesarGrupos8 o dejar vacío
              const nddff = horaData.meteo_4_1 || horaData.Nddff || '';
              if (nddff.length >= 1 && nddff[0] !== '/') {
                initial[rowNum].nubosidad = nddff[0];
              }

              // 2. FALLBACK DE CANTIDADES Y TIPOS DESDE 8NhCLCMCH (meteo_6_0):
              // Si no se completó nubes bajas desde grupos 8 pero CL es mayor a 0 en meteo_6_0
              const meteo60 = horaData.meteo_6_0 || '';
              if (meteo60 && meteo60.startsWith('8') && meteo60.length === 5) {
                const Nh = meteo60[1]; // cantidad de nubes bajas/medias
                const CL = meteo60[2]; // tipo nubes bajas
                const CM = meteo60[3]; // tipo nubes medias
                const CH = meteo60[4]; // tipo nubes altas

                // Si hay nubes bajas y no se cargaron por grupos 8
                if (CL !== '0' && CL !== '/' && !initial[rowNum].nb_cant) {
                  initial[rowNum].nb_cant = Nh !== '/' ? Nh : '';
                  initial[rowNum].nb_tipo = CL;
                  initial[rowNum].nb_total = Nh !== '/' ? Nh : '';
                } 
                // Si no hay nubes bajas pero hay medias
                else if ((CL === '0' || CL === '/') && CM !== '0' && CM !== '/' && !initial[rowNum].nm_cant) {
                  initial[rowNum].nm_cant = Nh !== '/' ? Nh : '';
                  initial[rowNum].nm_tipo = CM;
                  initial[rowNum].nm_total = Nh !== '/' ? Nh : '';
                }

                // Tipos generales (si no se completaron)
                if (!initial[rowNum].nb_tipo && CL !== '/') initial[rowNum].nb_tipo = CL;
                if (!initial[rowNum].nm_tipo && CM !== '/') initial[rowNum].nm_tipo = CM;
                if (!initial[rowNum].na_tipo && CH !== '/') initial[rowNum].na_tipo = CH;
              }

              // 3. FALLBACK DE ALTURA DESDE IrIXHVV (meteo_4_irixhvv):
              // El tercer carácter (h) es la altura base de las nubes bajas/medias
              const irixhv = horaData.meteo_4_irixhvv || '';
              if (irixhv.length >= 3 && !initial[rowNum].nb_altura) {
                const hVal = irixhv[2];
                if (hVal !== '/' && hVal !== '9') {
                  // Mapeo oficial WMO h a metros
                  const hToMeters = {
                    '0': '25', '1': '75', '2': '150', '3': '250', '4': '450',
                    '5': '800', '6': '1250', '7': '1750', '8': '2250'
                  };
                  const height = hToMeters[hVal] || '';
                  if (height) {
                    if (initial[rowNum].nb_cant) {
                      initial[rowNum].nb_altura = height;
                    } else if (initial[rowNum].nm_cant) {
                      initial[rowNum].nm_altura = height;
                    }
                  }
                }
              }

              // DIRECCIÓN DE NUBES (Dir):
              let grupoDir = '';
              if (horaData.meteo_8_1 && horaData.meteo_8_1.startsWith('56') && horaData.meteo_8_1.length === 5) {
                grupoDir = horaData.meteo_8_1;
              } else if (horaData.meteo_6_2 && horaData.meteo_6_2.startsWith('0') && horaData.meteo_6_2.length === 5) {
                grupoDir = horaData.meteo_6_2;
              }
              if (grupoDir) {
                if (grupoDir[2] !== '/') initial[rowNum].nb_direc = grupoDir[2];
                if (grupoDir[3] !== '/') initial[rowNum].nm_direc = grupoDir[3];
                if (grupoDir[4] !== '/') initial[rowNum].na_direc = grupoDir[4];
              }

              // Lluvia
              if (horaData.LL) {
                initial[rowNum].lluvia_6h = enforceOneDecimal(horaData.LL, 'lluvia_6h');
              }

              // Estado del suelo (desde 3Ejjj)
              const meteo65 = horaData.meteo_6_5 || '';
              if (meteo65 && meteo65.startsWith('3') && meteo65.length >= 2) {
                const eVal = meteo65[1];
                if (eVal !== '/') {
                  initial[rowNum].estado_suelo = eVal;
                }
              }

              // Temperaturas (solo horas principales)
              if (tempHours.includes(horaKey)) {
                initial[rowNum].temp_max = enforceOneDecimal(horaData.Tmax || '', 'temp_max');
                initial[rowNum].temp_min = enforceOneDecimal(horaData.Tmin || '', 'temp_min');
              }
            }
          }
        }
      } catch (e) {
        console.log("No existe data sinóptica base para autocompletar.", e);
      }
      setRows(initial);
    } catch (e) {
      console.error("Error cargando formulario", e);
    } finally {
      setIsDataLoaded(true);
    }
  };

  // Auto-guardar borrador en sessionStorage al modificar datos
  useEffect(() => {
    if (isDataLoaded && selectedStation && date) {
      sessionStorage.setItem(`cli4074_draft_${selectedStation}_${date}`, JSON.stringify(rows));
    }
  }, [rows, selectedStation, date, isDataLoaded]);

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
      // eslint-disable-next-line react-hooks/set-state-in-effect
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
              const keysGrupo8 = ['meteo_8_5', 'meteo_8_6', 'extra_8ns_1', 'extra_8ns_2', 'meteo_10_0', 'meteo_10_1'];
              for (const k of keysGrupo8) {
                const val = horaData[k] || '';
                if (val && val.startsWith('8') && val.length >= 5) {
                  grupos8.push(val);
                }
              }

              if (grupos8.length > 0) {
                initial[rowNum] = procesarGrupos8(initial[rowNum], grupos8);
              }

              // DIRECCIÓN DE NUBES:
              let grupoDir = '';
              if (horaData.meteo_8_1 && horaData.meteo_8_1.startsWith('56') && horaData.meteo_8_1.length === 5) {
                grupoDir = horaData.meteo_8_1;
              } else if (horaData.meteo_6_2 && horaData.meteo_6_2.startsWith('0') && horaData.meteo_6_2.length === 5) {
                grupoDir = horaData.meteo_6_2;
              }
              if (grupoDir) {
                if (grupoDir[2] !== '/') initial[rowNum].nb_direc = grupoDir[2];
                if (grupoDir[3] !== '/') initial[rowNum].nm_direc = grupoDir[3];
                if (grupoDir[4] !== '/') initial[rowNum].na_direc = grupoDir[4];
              }

              // TIPO DE NUBES GENERAL:
              const meteo60 = horaData.meteo_6_0 || '';
              if (meteo60 && meteo60.startsWith('8') && meteo60.length === 5) {
                if (!initial[rowNum].nb_tipo && meteo60[2] !== '/') initial[rowNum].nb_tipo = meteo60[2];
                if (!initial[rowNum].nm_tipo && meteo60[3] !== '/') initial[rowNum].nm_tipo = meteo60[3];
                if (!initial[rowNum].na_tipo && meteo60[4] !== '/') initial[rowNum].na_tipo = meteo60[4];
              }

              // Temperaturas
              if (tempHours.includes(horaKey)) {
                initial[rowNum].temp_max = enforceOneDecimal(horaData.t_max || horaData.meteo_6_3?.substring(1) || '', 'temp_max');
                initial[rowNum].temp_min = enforceOneDecimal(horaData.t_min || horaData.meteo_6_4?.substring(1) || '', 'temp_min');
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



  const updateRowField = (rowNum, field, value) => {
    // Convertir automáticamente código de altura a metros
    const autoConvertHeight = (fieldName, newValue) => {
      // Buscar el campo de altura correspondiente
      if (fieldName.endsWith('_altura') || fieldName === 'cb_altura' || fieldName === 'nb_altura' || fieldName === 'nm_altura' || fieldName === 'na_altura') {
        return convertCloudHeight(newValue);
      }
      return newValue;
    };

    const valAfterHeight = autoConvertHeight(field, value);
    const formattedValue = enforceOneDecimal(valAfterHeight, field);

    setRows(prev => ({
      ...prev,
      [rowNum]: { 
        ...prev[rowNum], 
        [field]: formattedValue
      }
    }));
  };





  // Estilos heredados del CLI 3074
  const thClass = spreadsheetStyles.th;
  const subThClass = spreadsheetStyles.subTh;

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col font-sans relative overflow-hidden">
      {/* Aesthetic Background Effect */}
      <div className="absolute top-0 left-0 w-full h-96 bg-gradient-to-b from-emerald-600/10 to-transparent pointer-events-none"></div>

      <div className="px-6 py-4 flex items-center gap-4 z-10 w-full max-w-full">
        <button
          onClick={() => {
            if (location.state?.fromAudit) {
              navigate(`/audit/observation/${selectedStation}/${date}`);
            } else {
              navigate('/synoptic', { state: { stationId: selectedStation, date } });
            }
          }}
          className="w-10 h-10 rounded-full border border-slate-200 bg-white flex items-center justify-center text-slate-500 hover:text-emerald-600 hover:bg-emerald-50 hover:border-emerald-200 hover:scale-105 shadow-sm transition-all focus:outline-none focus:ring-2 focus:ring-emerald-500"
          title="Volver a Observaciones"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        
        <h1 className="text-2xl font-bold text-slate-800 tracking-tight">CLI 4074 - NUBOSIDAD Y TEMPERATURA</h1>

        {/* Navegación Intra-CLI */}
        <div className="bg-slate-200/60 p-1 rounded-lg inline-flex gap-1 shadow-inner ml-4">
          <button
            onClick={() => {
              if (!selectedStation) {
                toast.error("Seleccione una estación primero.");
                return;
              }
              navigate('/cli3074', { state: { stationId: selectedStation, date, fromAudit: location.state?.fromAudit } });
            }}
            className="px-3 py-1.5 rounded-md text-xs font-semibold transition-all text-slate-600 hover:bg-white/50"
          >
            3074
          </button>
          <button
            onClick={() => navigate('/cli4074', { state: { stationId: selectedStation, date, fromAudit: location.state?.fromAudit } })}
            className="px-3 py-1.5 rounded-md text-xs font-bold transition-all bg-white text-emerald-700 shadow-sm"
          >
            4074
          </button>
          <button
            onClick={() => {
              if (!selectedStation) {
                toast.error("Seleccione una estación primero.");
                return;
              }
              navigate('/cli5074', { state: { stationId: selectedStation, date, fromAudit: location.state?.fromAudit } });
            }}
            className="px-3 py-1.5 rounded-md text-xs font-semibold transition-all text-slate-600 hover:bg-white/50"
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
                if (location.state?.fromAudit) {
                  navigate(`/audit/observation/${selectedStation}/${date}`);
                } else {
                  navigate('/synoptic', { state: { stationId: selectedStation, date, activeHour: h } });
                }
              }}
              className="px-2 py-1 rounded bg-white hover:bg-emerald-50 hover:text-emerald-700 hover:scale-105 active:scale-95 transition-all text-[11px] font-bold text-slate-600 shadow-sm cursor-pointer"
            >
              {h}
            </button>
          ))}
        </div>


      </div>

      {/* HEADER BLOCK - Info de estación */}
      <StationHeader 
        selectedStation={selectedStation}
        setSelectedStation={setSelectedStation}
        date={date}
        setDate={setDate}
        stations={stations}
        colorTheme="emerald"
        isLocked={true}
      />

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

              const isTempInvalid = row.temp_max && row.temp_min && parseFloat(row.temp_max) < parseFloat(row.temp_min);
              const inputStyle = `${spreadsheetStyles.input.emerald} ${isMainHour ? "font-semibold text-slate-900" : ""}`;
              const invalidStyle = `${inputStyle} ${spreadsheetStyles.invalidInput}`;
              const tdBorder = spreadsheetStyles.tdBorder;

              return (
                <tr key={i} className={`transition-colors ${trClass}`}>
                  {/* Hora Local */}
                  <td className={`${spreadsheetStyles.stickyColBase} ${isMainHour ? 'bg-emerald-200 text-emerald-900' : 'bg-slate-100 text-slate-600'}`}>
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
                  <td className={`${tdBorder} ${tempHours.includes(Object.entries(synopRows).find(([, r]) => r === i)?.[0] || '') ? 'bg-orange-50' : 'bg-slate-100'}`}>
                    <input 
                      className={isTempInvalid ? invalidStyle : inputStyle} 
                      maxLength="5" 
                      value={row.temp_max} 
                      onChange={e => updateRowField(i, 'temp_max', e.target.value)}
                      disabled={!tempHours.includes(Object.entries(synopRows).find(([, r]) => r === i)?.[0] || '')}
                      title="Temperatura máxima (solo horas sinópticas)"
                    />
                  </td>
                  <td className={`${tdBorder} ${tempHours.includes(Object.entries(synopRows).find(([, r]) => r === i)?.[0] || '') ? 'bg-blue-50' : 'bg-slate-100'}`}>
                    <input 
                      className={isTempInvalid ? invalidStyle : inputStyle} 
                      maxLength="5" 
                      value={row.temp_min} 
                      onChange={e => updateRowField(i, 'temp_min', e.target.value)}
                      disabled={!tempHours.includes(Object.entries(synopRows).find(([, r]) => r === i)?.[0] || '')}
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
