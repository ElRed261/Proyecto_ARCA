import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from '../../../shared/api/axiosConfig';
import { isAdmin } from '../../../shared/utils/auth';

// =============================================================================
// CONSTANTES
// =============================================================================

const AAXX = "AAXX";        // Constante que no varía
const CONST_333 = "333";    // Sección 3 - Constante
const CONST_555 = "555";    // Sección 5 - Constante

// =============================================================================
// FUNCIONES DE NORMALIZACIÓN
// =============================================================================

/**
 * Normaliza la entrada de presión.
 * Si el valor es menor a 100, asume que es formato corto (15.3 → 1015.3)
 * @param {string} input - Valor ingresado
 * @returns {string} - Valor normalizado con 1000 añadido si es necesario
 */
const normalizePressure = (input) => {
  if (!input || input.trim() === '') return '';
  const num = parseFloat(input);
  if (isNaN(num)) return input;
  // Si es menor a 100, añadir 1000 (ej: 15.3 → 1015.3)
  if (num < 100) {
    return (1000 + num).toFixed(1);
  }
  return input;
};

// =============================================================================
// COMPONENTE PRINCIPAL
// =============================================================================

const SynopticPage = () => {
  const navigate = useNavigate();
  const hours = ["06Z", "09Z", "12Z", "15Z", "18Z", "21Z", "00Z", "03Z"];

  // Horas pares (tienen T_max/T_min y grupos 1snTx/2snTn)
  const evenHours = ["00Z", "06Z", "12Z", "18Z"];
  // Horas impares (NO tienen T_max/T_min)
  const oddHours = ["03Z", "09Z", "15Z", "21Z"];

  // Estado inicial: objeto con claves para cada hora
  const [observations, setObservations] = useState(
    hours.reduce((acc, hour) => ({ ...acc, [hour]: {} }), {})
  );

  // Hora activa por defecto: 06Z
  const [activeHour, setActiveHour] = useState('06Z');
  const [results, setResults] = useState({});
  const [errorMessage, setErrorMessage] = useState('');
  const [stations, setStations] = useState({});
  const [isCalculating, setIsCalculating] = useState(false);
  const [isLoading, setIsLoading] = useState(false); // Flag para evitar cálculos durante carga
  const [isStationLocked, setIsStationLocked] = useState(false); // Bloquear estación después de guardar

  // Determinar si la hora activa es par (tiene T_max/T_min)
  const isEvenHour = evenHours.includes(activeHour);

  // Cargar lista de estaciones al montar
  useEffect(() => {
    const fetchStations = async () => {
      try {
        const response = await axios.get('/synoptic/stations');
        setStations(response.data);
      } catch (error) {
        console.error('Error al cargar estaciones:', error);
      }
    };
    fetchStations();
  }, []);

  // Llamar al backend cuando cambian los datos
  const performCalculations = useCallback(async (data) => {
    setIsCalculating(true);
    setErrorMessage('');

    try {
      const response = await axios.post('/synoptic/calculate', {
        ts: data.ts || '',
        th: data.th || '',
        pres_est: data.pres_est || '',
        p3: data.p3 || '',
        p24: data.p24 || '',
        correc_alt: data.correc_alt || '',
        station_id: data.station_id || '',
        ir: data.ir || '',
        ix: data.ix || ''
      });

      const calcResults = response.data;

      // Si hay error del backend, mostrarlo
      if (calcResults.error_message) {
        setErrorMessage(calcResults.error_message);
      }

      // Actualizar correc_alt si vino de la estación - COMENTADO para evitar loop de renders
      /*
      if (calcResults.correc_alt && !data.correc_alt) {
        setObservations(prev => ({
          ...prev,
          [activeHour]: {
            ...prev[activeHour],
            correc_alt: calcResults.correc_alt
          }
        }));
      }
      */

      setResults(calcResults);
    } catch (error) {
      console.error('Error en cálculos:', error);
      // Fallback: resultados vacíos
      setResults({});
    } finally {
      setIsCalculating(false);
    }
  }, [activeHour]);

  // Efecto para recalcular resultados cuando cambia la hora o los datos
  useEffect(() => {
    // No calcular mientras se está cargando un archivo
    if (isLoading) return;

    const currentData = observations[activeHour] || {};

    // Debounce para evitar muchas llamadas
    const timeoutId = setTimeout(() => {
      performCalculations(currentData);
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [activeHour, observations, performCalculations, isLoading]);

  const handleChange = (key, value) => {
    setObservations(prev => ({
      ...prev,
      [activeHour]: {
        ...prev[activeHour],
        [key]: value
      }
    }));
  };

  // Handler especial para cambio de estación
  const handleStationChange = (stationId) => {
    handleChange('station_id', stationId);

    // Si existe la estación, actualizar correc_alt automáticamente
    if (stations[stationId]) {
      handleChange('correc_alt', stations[stationId].ch.toString());
    }
  };

  // Handler para normalizar presiones al perder foco (15.3 → 1015.3)
  const handlePressureBlur = (key) => {
    const currentValue = observations[activeHour]?.[key] || '';
    const normalizedValue = normalizePressure(currentValue);
    if (normalizedValue !== currentValue) {
      handleChange(key, normalizedValue);
    }
  };

  // Handler para Enter - aplica cambios (quita foco del campo)
  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.target.blur();
    }
  };

  // Handler para Enter en campos de presión - normaliza y aplica
  const handlePressureKeyDown = (e, key) => {
    if (e.key === 'Enter') {
      handlePressureBlur(key);
      e.target.blur();
    }
  };

  // Guardar observación como JSON
  const handleSave = async () => {
    try {
      const stationId = getValue('station_id');
      const fecha = getValue('fecha');

      // Validar estación y fecha
      if (!stationId) {
        alert('⚠️ Debe seleccionar una estación antes de guardar');
        return;
      }
      if (!fecha) {
        alert('⚠️ Debe seleccionar una fecha antes de guardar');
        return;
      }

      // Removida restricción de hora - se puede guardar desde cualquier hora

      // Preparar datos de todas las horas con los resultados calculados
      const observationsWithResults = {};
      for (const hora of hours) {
        const horaData = observations[hora] || {};
        observationsWithResults[hora] = {
          ...horaData,
          // Incluir resultados calculados si corresponde a la hora activa
          pres_nmm: results.pres_nmm,
          punto_rocio: results.punto_rocio,
          tension_vapor: results.tension_vapor,
          humedad_relativa: results.humedad_relativa
        };
      }

      const response = await axios.post('/synoptic/save-json', {
        station_code: stationId,
        fecha: fecha,
        observations: observationsWithResults,
        observer_name: getValue('observador') || null
      });

      if (response.data.success) {
        // Mostrar confirmación con fecha formateada
        const fecha = getValue('fecha');
        const fechaFormatted = fecha ? (() => {
          const [yyyy, mm, dd] = fecha.split('-');
          return `${dd}/${mm}/${yyyy}`;
        })() : '';

        // Bloquear cambio de estación después de guardar
        setIsStationLocked(true);

        alert(`✅ Observación guardada\n\nFecha: ${fechaFormatted}\nArchivo: ${response.data.filename}${response.data.backup_path ? '\nBackup creado ✓' : ''}\n\n⚠️ La estación está ahora bloqueada.`);
      }
    } catch (error) {
      console.error('Error al guardar:', error);
      alert('❌ Error al guardar la observación');
    }
  };

  // Helper: verifica si hay datos de temperatura en alguna hora
  const hasTemperatureData = () => {
    for (const hora of hours) {
      const data = observations[hora] || {};
      // Verificar si hay Ts o Th (temperaturas principales)
      if (data.ts && data.ts.trim() !== '') return true;
      if (data.th && data.th.trim() !== '') return true;
    }
    return false;
  };

  // Función para navegar a un día específico (guarda antes de navegar)
  const navigateToDay = async (direction) => {
    const currentDate = getValue('fecha');
    const currentStation = getValue('station_id');
    const correcAlt = getValue('correc_alt');

    if (!currentStation || !currentDate) {
      console.warn('⚠️ Debe tener estación y fecha antes de navegar');
      return;
    }

    // CONFIRMACIÓN: Preguntar antes de navegar
    const directionText = direction === 1 ? 'siguiente' : 'anterior';
    const confirmed = window.confirm(
      `¿Desea ir al día ${directionText}?\n\nEl día actual será guardado automáticamente.`
    );
    if (!confirmed) {
      return;
    }

    // VALIDACIÓN 1: Si vamos hacia ATRÁS, verificar que no sea la fecha más antigua
    if (direction === -1) {
      try {
        const rangeResponse = await axios.get(`/synoptic/date-range/${currentStation}`);
        const oldestDate = rangeResponse.data.oldest_date;

        if (oldestDate && currentDate <= oldestDate) {
          console.log(`🚫 No hay datos antes del ${oldestDate} para estación ${currentStation}`);
          return; // No navegar
        }
      } catch (error) {
        console.error('Error al verificar rango de fechas:', error);
      }
    }

    // VALIDACIÓN 2: Si vamos hacia ADELANTE y NO hay temperatura, no crear nuevo día
    if (direction === 1 && !hasTemperatureData()) {
      console.log('⚠️ Debe ingresar datos de temperatura antes de avanzar al siguiente día');
      return; // No navegar
    }

    // 1. GUARDAR el día actual (solo si hay datos de temperatura)
    if (hasTemperatureData()) {
      try {
        const observationsWithResults = {};
        for (const hora of hours) {
          observationsWithResults[hora] = observations[hora] || {};
        }

        await axios.post('/synoptic/save-json', {
          station_code: currentStation,
          fecha: currentDate,
          observations: observationsWithResults,
          observer_name: getValue('nombre_observador') || null
        });
        console.log(`💾 Guardado día: ${currentDate}`);
      } catch (error) {
        console.error('Error al guardar día actual:', error);
      }
    }

    // 2. Calcular fecha destino
    const date = new Date(currentDate);
    date.setDate(date.getDate() + direction);
    const targetDate = date.toISOString().split('T')[0];

    // 3. Intentar CARGAR el día destino desde backend
    try {
      const [yyyy, mm, dd] = targetDate.split('-');
      const fechaForBackend = `${dd}${mm}${yyyy}`;

      const response = await axios.get(`/synoptic/observation/${currentStation}/${fechaForBackend}`);

      if (response.data && response.data.horarias) {
        setIsLoading(true);

        const newObservations = {};
        hours.forEach(hora => {
          newObservations[hora] = {
            station_id: currentStation,
            fecha: targetDate,
            correc_alt: correcAlt
          };
        });

        response.data.horarias.forEach(item => {
          const hora = item.hora;
          if (hours.includes(hora)) {
            const d = item.datos || {};
            const s = item.synop_manual || item.synop || {}; // Compatibilidad con formato anterior

            newObservations[hora] = {
              ...newObservations[hora],
              // Campos básicos por hora
              nombre_observador: item.nombre_observador || '',
              meteo_2_1: item.yygg_iw || '',
              // Datos manuales
              ts: d.ts || '', th: d.th || '',
              pres_est: d.pres_est || '', p3: d.p3 || '', p24: d.p24 || '',
              let_barom: d.let_barom || '', ll: d.ll || '', ll_24h: d.ll_24h || '',
              // T_max/T_min (solo horas pares)
              t_max: d.t_max || '', t_min: d.t_min || '',
              t_max_24h: d.t_max_24h || '', t_min_24h: d.t_min_24h || '',
              // Grupos SYNOP manuales - Fila 4
              meteo_4_irixhvv: s.irixhvv || '', meteo_4_1: s.n_dd_ff || '',
              meteo_4_6: s['7ww_w1w2'] || '',
              // Fila 6
              meteo_6_0: s['8nh_cl_cm_ch'] || '',
              meteo_6_2: s['0cs_dl_dm_dh'] || '',
              meteo_6_3: s['1sn_tx_manual'] || '',
              meteo_6_4: s['2sn_tn_manual'] || '',
              meteo_6_5: s['3e_jjj'] || '',
              meteo_6_6: s['5eee_je'] || '',
              // Fila 8
              meteo_8_0: s['5n_fn'] || '',
              meteo_8_1: s['56dl_dm_dh'] || '',
              meteo_8_3: s['6rrr_tr'] || '',
              meteo_8_4: s['7r24'] || '',
              meteo_8_5: s['8ns_1'] || '',
              meteo_8_6: s['8ns_2'] || '',
              // Fila 10
              meteo_10_0: s['8ns_3'] || '',
              meteo_10_1: s['8ns_4'] || '',
              meteo_10_2: s['9sp_10_2'] || '',
              meteo_10_3: s['9sp_10_3'] || '',
              meteo_10_4: s['9sp_10_4'] || '',
              meteo_10_5: s['9sp_10_5'] || '',
              meteo_10_6: s['9sp_10_6'] || '',
              // Fila 12
              meteo_12_0: s['9sp_12_0'] || '',
              meteo_12_1: s['9sp_12_1'] || '',
              meteo_12_2: s['9sp_12_2'] || '',
              meteo_12_3: s['9sp_12_3'] || '',
              meteo_12_4: s['9sp_12_4'] || '',
              meteo_12_5: s['9sp_12_5'] || '',
              meteo_12_6: s['9sp_12_6'] || '',
              // Fila 14
              meteo_14_0: s['9sp_14_0'] || '',
              meteo_14_1: s['9sp_14_1'] || '',
              meteo_14_2: s['9sp_14_2'] || '',
              meteo_14_3: s['9sp_14_3'] || '',
              meteo_14_4: s['9sp_14_4'] || '',
              meteo_14_5: s['9sp_14_5'] || '',
              meteo_14_6: s['9sp_14_6'] || '',
              // Fila 16
              meteo_16_0: s['9sp_16_0'] || '',
              meteo_16_1: s['9sp_16_1'] || '',
              meteo_16_2: s['9sp_16_2'] || '',
              meteo_16_3: s['9sp_16_3'] || '',
              meteo_16_4: s['9sp_16_4'] || '',
              // Extras
              extra_8ns_1: s.extra_8ns_1 || '',
              extra_8ns_2: s.extra_8ns_2 || ''
            };
          }
        });

        setObservations(newObservations);
        setTimeout(() => setIsLoading(false), 100);
        console.log(`📂 Cargado día existente: ${targetDate}`);
      }
    } catch (error) {
      if (error.response?.status === 404) {
        // Solo crear nuevo día si vamos hacia adelante (ya validamos que hay temperatura)
        if (direction === 1) {
          const newObservations = {};
          hours.forEach(hora => {
            newObservations[hora] = {
              station_id: currentStation,
              fecha: targetDate,
              correc_alt: correcAlt
            };
          });
          setObservations(newObservations);
          console.log(`🆕 Nuevo día creado: ${targetDate}`);
        } else {
          console.log(`🚫 No hay observación para ${targetDate}`);
          return; // No navegar hacia atrás si no hay datos
        }
      } else {
        console.error('Error al cargar día:', error);
        return;
      }
    }

    setActiveHour('06Z');
    setResults({});
  };

  // Wrappers para navegación
  const handleNextDay = () => navigateToDay(1);
  const handlePreviousDay = () => navigateToDay(-1);

  // Helper: Formatear fecha a dd/mm/aaaa para mostrar
  const formatDateDisplay = (dateStr) => {
    if (!dateStr) return '';
    // Si ya está en formato YYYY-MM-DD
    if (dateStr.includes('-')) {
      const [yyyy, mm, dd] = dateStr.split('-');
      return `${dd}/${mm}/${yyyy}`;
    }
    // Si está en formato DDMMYYYY
    if (dateStr.length === 8) {
      const dd = dateStr.substring(0, 2);
      const mm = dateStr.substring(2, 4);
      const yyyy = dateStr.substring(4, 8);
      return `${dd}/${mm}/${yyyy}`;
    }
    return dateStr;
  };

  // Helper: Guardado silencioso (para auto-save sin confirmación)
  const doQuietSave = async () => {
    const stationId = getValue('station_id');
    const fecha = getValue('fecha');

    if (!stationId || !fecha) return false;

    try {
      const observationsWithResults = {};
      for (const hora of hours) {
        observationsWithResults[hora] = observations[hora] || {};
      }

      await axios.post('/synoptic/save-json', {
        station_code: stationId,
        fecha: fecha,
        observations: observationsWithResults,
        observer_name: getValue('nombre_observador') || null
      });
      console.log(`💾 Auto-guardado: ${formatDateDisplay(fecha)}`);
      return true;
    } catch (error) {
      console.error('Error en auto-guardado:', error);
      return false;
    }
  };

  // Cambiar hora con auto-guardado
  const handleHourChange = async (newHour) => {
    if (newHour === activeHour) return;

    // Auto-guardar antes de cambiar de hora (solo si hay datos de temperatura)
    if (hasTemperatureData()) {
      await doQuietSave();
    }

    setActiveHour(newHour);
  };

  // Mapeo de nombres de estación a códigos
  const stationNameToCode = {
    'MDJB': '78484',     // El Higüero
    'MDCY': 'MDCY',      // Catey (código directo)
    'Central': '78486',  // Estación Central (si existe)
    // Agregar más mapeos según sea necesario
  };

  // Cargar datos desde archivo JSON
  const handleLoadJson = (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const jsonData = JSON.parse(e.target.result);

        // Parsear formato Resumen_Mensual_Synop
        const newObservations = {};
        hours.forEach(hora => {
          newObservations[hora] = {};
        });

        // Cargar datos de meta
        if (jsonData.meta) {
          const estacionNombre = jsonData.meta.estacion || '';
          const fecha = jsonData.meta.fecha || '';

          // Mapear nombre de estación a código
          const stationCode = stationNameToCode[estacionNombre] || estacionNombre;
          const correcAlt = stations[stationCode]?.ch || '';

          // Convertir fecha de DDMMYYYY a YYYY-MM-DD
          let fechaFormatted = '';
          if (fecha.length === 8) {
            const dd = fecha.substring(0, 2);
            const mm = fecha.substring(2, 4);
            const yyyy = fecha.substring(4, 8);
            fechaFormatted = `${yyyy}-${mm}-${dd}`;
          }
          // Aplicar a todas las horas
          hours.forEach(hora => {
            newObservations[hora].station_id = stationCode;
            newObservations[hora].fecha = fechaFormatted;
            newObservations[hora].correc_alt = correcAlt.toString();
          });
        }

        // Helper para convertir valores
        const safeValue = (val) => {
          if (val === null || val === undefined || val === '' || (typeof val === 'number' && isNaN(val))) return '';
          return val.toString();
        };

        // Cargar datos horarios
        if (jsonData.horarias) {
          jsonData.horarias.forEach(item => {
            const hora = item.hora;
            if (hours.includes(hora)) {
              const d = item.datos || {};
              const s = item.synop_manual || item.synop || {}; // Compatibilidad con formato anterior

              newObservations[hora] = {
                ...newObservations[hora],

                // Observador (campo correcto)
                nombre_observador: item.nombre_observador || '',

                // YYGGIw
                meteo_2_1: item.yygg_iw || '',

                // Temperaturas básicas
                ts: safeValue(d.ts),
                th: safeValue(d.th),

                // T_max/T_min (solo en horas pares)
                t_max: safeValue(d.t_max),
                t_min: safeValue(d.t_min),
                t_max_24h: safeValue(d.t_max_24h),
                t_min_24h: safeValue(d.t_min_24h),

                // Presión (solo manual)
                pres_est: safeValue(d.pres_est),
                p3: safeValue(d.p3),
                p24: safeValue(d.p24),
                let_barom: d.let_barom || '',

                // Precipitación
                ll: safeValue(d.ll),

                // ===== Grupos SYNOP - Mapeo CORRECTO =====

                // Fila 4: IriXHVV, N dd ff, 7wwW1W2
                meteo_4_irixhvv: s.irixhvv || '',
                meteo_4_1: s.n_dd_ff || '',
                meteo_4_6: s['7ww_w1w2'] || '',

                // Fila 6: 8Nh, (333 auto), 0CS, 1snTx, 2snTn, 3Ejjj, 5EEE
                meteo_6_0: s['8nh_cl_cm_ch'] || '',
                meteo_6_2: s['0cs_dl_dm_dh'] || '',
                meteo_6_3: s['1sn_tx_manual'] || '',  // 1snTxTxTx manual
                meteo_6_4: s['2sn_tn_manual'] || '',  // 2snTnTnTn manual
                meteo_6_5: s['3e_jjj'] || '',
                meteo_6_6: s['5eee_je'] || '',

                // Fila 8: 5nFn, 56DL, (58/59 auto), 6RRR, 7R24, 8Ns, 8Ns
                meteo_8_0: s['5n_fn'] || '',
                meteo_8_1: s['56dl_dm_dh'] || '',
                meteo_8_3: s['6rrr_tr'] || '',
                meteo_8_4: s['7r24'] || '',
                meteo_8_5: s['8ns_1'] || '',
                meteo_8_6: s['8ns_2'] || '',

                // Fila 10: 8Ns, 8Ns, 9sp...
                meteo_10_0: s['8ns_3'] || '',
                meteo_10_1: s['8ns_4'] || '',
                meteo_10_2: s['9sp_10_2'] || '',
                meteo_10_3: s['9sp_10_3'] || '',
                meteo_10_4: s['9sp_10_4'] || '',
                meteo_10_5: s['9sp_10_5'] || '',
                meteo_10_6: s['9sp_10_6'] || '',

                // Fila 12: Grupos 9sp
                meteo_12_0: s['9sp_12_0'] || '',
                meteo_12_1: s['9sp_12_1'] || '',
                meteo_12_2: s['9sp_12_2'] || '',
                meteo_12_3: s['9sp_12_3'] || '',
                meteo_12_4: s['9sp_12_4'] || '',
                meteo_12_5: s['9sp_12_5'] || '',
                meteo_12_6: s['9sp_12_6'] || '',

                // Fila 14: Grupos 9sp
                meteo_14_0: s['9sp_14_0'] || '',
                meteo_14_1: s['9sp_14_1'] || '',
                meteo_14_2: s['9sp_14_2'] || '',
                meteo_14_3: s['9sp_14_3'] || '',
                meteo_14_4: s['9sp_14_4'] || '',
                meteo_14_5: s['9sp_14_5'] || '',
                meteo_14_6: s['9sp_14_6'] || '',

                // Fila 16: Grupos 9sp (5 cols, 555 y 29UUU son auto)
                meteo_16_0: s['9sp_16_0'] || '',
                meteo_16_1: s['9sp_16_1'] || '',
                meteo_16_2: s['9sp_16_2'] || '',
                meteo_16_3: s['9sp_16_3'] || '',
                meteo_16_4: s['9sp_16_4'] || '',

                // 2 Extras 8NsChshs (panel lateral)
                extra_8ns_1: s.extra_8ns_1 || '',
                extra_8ns_2: s.extra_8ns_2 || ''
              };
            }
          });
        }

        // pp_24h solo de 12Z en resumen
        if (jsonData.resumen_dia?.pp_24h) {
          newObservations['12Z'].ll_24h = jsonData.resumen_dia.pp_24h.toString();
        }

        // Marcar carga en progreso para evitar cálculos automáticos
        setIsLoading(true);
        setObservations(newObservations);

        // Después de un tick, permitir cálculos y recalcular
        setTimeout(() => {
          setIsLoading(false);
        }, 100);

        // Confirmación de carga con fecha formateada
        const stationCode = stationNameToCode[jsonData.meta?.estacion] || jsonData.meta?.estacion;
        const fecha = jsonData.meta?.fecha || '';
        const fechaFormatted = fecha.length === 8
          ? `${fecha.substring(0, 2)}/${fecha.substring(2, 4)}/${fecha.substring(4, 8)}`
          : fecha;

        // Bloquear estación después de cargar (la observación pertenece a esa estación)
        setIsStationLocked(true);

        alert(`✅ Observación cargada\n\nEstación: ${stationCode}\nFecha: ${fechaFormatted}\n\n🔒 Estación bloqueada.`);

        // Resetear el input
        event.target.value = '';
      } catch (error) {
        console.error('Error al parsear JSON:', error);
        alert('❌ Error al cargar el archivo JSON.\nVerifique el formato.');
        event.target.value = '';
      }
    };
    reader.readAsText(file);
  };

  // Helper para obtener valores de forma segura (siempre retorna string)
  const getValue = (key) => {
    const value = observations[activeHour]?.[key];
    if (value === undefined || value === null) return '';
    return String(value);
  };

  // =============================================================================
  // TEMAS DINÁMICOS POR HORA (ESCALA DE AZULES - ALTURA DEL SOL)
  // =============================================================================

  const hourThemes = {
    "06Z": { // 02:00 AM - Noche profunda (Azul muy oscuro/Gris)
      bgGradient: "from-slate-950 to-blue-950",
      accentColor: "#1e293b", // slate-800
      textColor: "text-slate-200"
    },
    "09Z": { // 05:00 AM - Amanecer (Azul oscuro)
      bgGradient: "from-blue-950 to-blue-900",
      accentColor: "#172554", // blue-950
      textColor: "text-blue-100"
    },
    "12Z": { // 08:00 AM - Mañana (Azul medio)
      bgGradient: "from-blue-800 to-blue-600",
      accentColor: "#1d4ed8", // blue-700
      textColor: "text-white"
    },
    "15Z": { // 11:00 AM - Mediodía (Azul brillante)
      bgGradient: "from-blue-600 to-blue-500",
      accentColor: "#2563eb", // blue-600
      textColor: "text-white"
    },
    "18Z": { // 02:00 PM - Pico del Sol (Azul más fuerte/intenso)
      bgGradient: "from-blue-600 to-blue-400",
      accentColor: "#3b82f6", // blue-500
      textColor: "text-white"
    },
    "21Z": { // 05:00 PM - Tarde (Volviendo a azul medio)
      bgGradient: "from-blue-700 to-blue-600",
      accentColor: "#1d4ed8", // blue-700
      textColor: "text-white"
    },
    "00Z": { // 08:00 PM - Anochecer (Azul oscuro)
      bgGradient: "from-blue-900 to-blue-800",
      accentColor: "#1e3a8a", // blue-900
      textColor: "text-blue-100"
    },
    "03Z": { // 11:00 PM - Noche (Azul muy oscuro)
      bgGradient: "from-slate-900 to-blue-950",
      accentColor: "#0f172a", // slate-900
      textColor: "text-slate-200"
    }
  };

  const currentTheme = hourThemes[activeHour];

  // Estilos dinámicos
  const primaryHeader = `text-white font-bold text-sm px-3 py-2 rounded-lg text-center transition-colors duration-500`;
  const tableHeader = "bg-slate-600 text-white font-semibold text-xs px-2 py-2 text-center";
  const inputClass = "bg-white border border-slate-300 text-slate-800 text-sm px-2 py-2 rounded w-full focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none text-center";
  const readonlyClass = "bg-white border border-slate-300 text-blue-600 font-bold text-sm px-2 py-2 rounded w-full text-center";
  const constantClass = "bg-slate-200 border border-slate-400 text-slate-700 font-bold text-sm px-2 py-2 rounded w-full text-center";
  const errorClass = "text-red-500 text-sm mt-2 text-center";

  const meteoHeaders = {
    1: ["MiMi MjMj", "YYGG Iw", "IIiii", "Fecha"],
    3: ["Ir iX H VV", "N dd ff", "1sn T T T", "2sn Td Td Td", "4 P P P P", "5 a P P P", "7 ww W1 W2"],
    5: ["8Nh CL CM CH", "333", "0CS DL DM DH", "1sn Tx Tx Tx", "2sn Tn Tn Tn", "3E j j j", "5 EEEjE"],
    7: ["5n Fn Fn Fn", "56DL DM DH", "58/59 P24P24P24", "6 RRR tr", "7R24R24R24R24", "8NsChs hs", "8NsChs hs"],
    9: ["8NsChs hs", "8NsChs hs", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp"],
    11: ["9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp"],
    13: ["9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp"],
    15: ["9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "555", "29 UUU"]
  };

  const meteoPlaceholders = {
    2: ["AAXX", "", "78", ""],
    4: ["", "", "10", "20", "4", "5", "7"],
    6: ["8", "333", "0", "10", "20", "3///", ""],
    8: ["", "56", "5", "6", "7", "8", "8"],
    10: ["8", "8", "9", "9", "9", "9", "9"],
    12: ["9", "9", "9", "9", "9", "9", "9"],
    14: ["9", "9", "9", "9", "9", "9", "9"],
    16: ["9", "9", "9", "9", "9", "555", "29"]
  };

  return (
    <div className={`min-h-screen p-6 transition-colors duration-1000 bg-gradient-to-br ${currentTheme.bgGradient}`}>
      <div className="max-w-7xl mx-auto">
        <button
          onClick={() => navigate('/dashboard')}
          className={`mb-6 px-4 py-2 rounded-lg font-medium text-sm backdrop-blur-md bg-white/10 border border-white/20 shadow-lg transition-all hover:bg-white/20 hover:scale-105 flex items-center gap-2 ${currentTheme.textColor}`}
        >
          <span>&larr;</span> Volver al Dashboard
        </button>

        <h1 className={`text-2xl font-bold mb-6 transition-colors duration-500 ${currentTheme.textColor}`}>
          Observación Sinóptica {activeHour}
        </h1>

        <div className="flex gap-4 items-start">
          {/* Contenido Principal */}
          <div className="flex-1">
            {/* Tabla Meteorológica */}
            <div className="bg-white rounded-xl shadow-lg p-5 mb-6 transition-all duration-500">
              <div className="grid grid-cols-7 gap-2 mb-3">
                <div className={primaryHeader} style={{ backgroundColor: currentTheme.accentColor }}>Observador</div>
                <div className="col-span-6">
                  <input className={inputClass} placeholder="Nombre del Observador..." value={getValue('nombre_observador')} onChange={(e) => handleChange('nombre_observador', e.target.value)} />
                </div>
              </div>

              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16].map(row => {
                const isHeader = row % 2 === 1;
                const headers = meteoHeaders[row] || [];
                const placeholders = meteoPlaceholders[row] || [];

                if (row === 1) {
                  return (
                    <div key={row} className="grid grid-cols-7 gap-2 mb-1">
                      {headers.slice(0, 3).map((h, i) => (<div key={i} className={tableHeader}>{h}</div>))}
                      <div className={`col-span-4 ${tableHeader}`}>{headers[3]}</div>
                    </div>
                  );
                }
                if (row === 2) {
                  return (
                    <div key={row} className="grid grid-cols-7 gap-2 mb-3">
                      {/* AAXX - Constante */}
                      <input className={constantClass} value={AAXX} readOnly title="Constante AAXX" />
                      {/* YYGG Iw */}
                      <input className={inputClass} placeholder="" value={getValue('meteo_2_1')} onChange={(e) => handleChange('meteo_2_1', e.target.value)} />
                      {/* IIiii - Selector de estación (bloqueado después de guardar) */}
                      <select
                        className={`${inputClass} ${isStationLocked ? 'bg-gray-300 cursor-not-allowed opacity-75' : ''}`}
                        value={getValue('station_id')}
                        onChange={(e) => handleStationChange(e.target.value)}
                        disabled={isStationLocked}
                        title={isStationLocked
                          ? '🔒 Estación bloqueada (ya se guardó una observación)'
                          : (stations[getValue('station_id')]?.name || 'Seleccionar estación')}
                      >
                        <option value="">Seleccionar...</option>
                        {Object.entries(stations).map(([id, info]) => (
                          <option key={id} value={id}>{id}</option>
                        ))}
                      </select>
                      {/* Fecha */}
                      <div className="col-span-4">
                        <input type="date" className={inputClass} value={getValue('fecha')} onChange={(e) => handleChange('fecha', e.target.value)} />
                      </div>
                    </div>
                  );
                }
                // Row 4: Campos especiales con códigos SYNOP auto-generados
                if (row === 4) {
                  // Handler para parsear Ir e Ix del campo combinado
                  const handleIrIxChange = (value) => {
                    handleChange('meteo_4_irixhvv', value);
                    // Extraer Ir (primer dígito) e Ix (segundo dígito) si existen
                    if (value.length >= 1) {
                      handleChange('ir', value[0]);
                    }
                    if (value.length >= 2) {
                      handleChange('ix', value[1]);
                    }
                  };

                  return (
                    <div key={row} className="grid grid-cols-7 gap-2 mb-3">
                      {/* Ir iX H VV - Campo único que extrae Ir e Ix automáticamente */}
                      <input
                        className={inputClass}
                        placeholder="Ir iX H VV"
                        value={getValue('meteo_4_irixhvv')}
                        onChange={(e) => handleIrIxChange(e.target.value)}
                        onKeyDown={handleKeyDown}
                        title="Ir:precipitación, iX:tiempo, H:nubes, VV:visibilidad"
                      />
                      {/* N dd ff */}
                      <input className={inputClass} placeholder="" value={getValue('meteo_4_1')} onChange={(e) => handleChange('meteo_4_1', e.target.value)} onKeyDown={handleKeyDown} title="N:nubosidad, dd:dirección, ff:velocidad viento" />
                      {/* 1sn T T T - Auto-generado */}
                      <input className={readonlyClass} value={results.grupo_1sn_ttt || ''} readOnly title="1snTTT: temperatura seca" />
                      {/* 2sn Td Td Td - Auto-generado */}
                      <input className={readonlyClass} value={results.grupo_2sn_td || ''} readOnly title="2snTdTdTd: punto de rocío" />
                      {/* 4 P P P P - Auto-generado */}
                      <input className={readonlyClass} value={results.grupo_4pppp || ''} readOnly title="4PPPP: presión NMM" />
                      {/* 5 a P P P - Auto-generado (tendencia de presión) */}
                      <input className={readonlyClass} value={results.grupo_5appp || ''} readOnly title="5aPPP: tendencia presión 3h" />
                      {/* 7 ww W1 W2 - Condicionado por Ix */}
                      <input
                        className={results.include_weather ? inputClass : `${inputClass} opacity-50`}
                        placeholder="7"
                        value={getValue('meteo_4_6')}
                        onChange={(e) => handleChange('meteo_4_6', e.target.value)}
                        onKeyDown={handleKeyDown}
                        disabled={!results.include_weather}
                        title={results.include_weather ? "7wwW1W2: tiempo presente y pasado" : "Omitido (iX≠1,4)"}
                      />
                    </div>
                  );
                }
                // Row 6: 333 constante en posición 1, meteo_6_3/6_4 bloqueados en horas impares
                if (row === 6) {
                  return (
                    <div key={row} className="grid grid-cols-7 gap-2 mb-3">
                      <input className={inputClass} placeholder="8" value={getValue('meteo_6_0')} onChange={(e) => handleChange('meteo_6_0', e.target.value)} onKeyDown={handleKeyDown} title="8NhCLCMCH: nubes" />
                      <input className={constantClass} value={CONST_333} readOnly title="Sección 333" />
                      <input className={inputClass} placeholder="0" value={getValue('meteo_6_2')} onChange={(e) => handleChange('meteo_6_2', e.target.value)} onKeyDown={handleKeyDown} title="0CSDLDMDH: nubes dirección" />
                      {/* 1snTxTxTx - Solo habilitado en horas pares */}
                      <input
                        className={isEvenHour ? inputClass : `${inputClass} opacity-50 bg-gray-200`}
                        placeholder="10"
                        value={getValue('meteo_6_3')}
                        onChange={(e) => handleChange('meteo_6_3', e.target.value)}
                        onKeyDown={handleKeyDown}
                        disabled={!isEvenHour}
                        title={isEvenHour ? "1snTxTxTx: temperatura máxima" : "Solo en horas pares (00Z, 06Z, 12Z, 18Z)"}
                      />
                      {/* 2snTnTnTn - Solo habilitado en horas pares */}
                      <input
                        className={isEvenHour ? inputClass : `${inputClass} opacity-50 bg-gray-200`}
                        placeholder="20"
                        value={getValue('meteo_6_4')}
                        onChange={(e) => handleChange('meteo_6_4', e.target.value)}
                        onKeyDown={handleKeyDown}
                        disabled={!isEvenHour}
                        title={isEvenHour ? "2snTnTnTn: temperatura mínima" : "Solo en horas pares (00Z, 06Z, 12Z, 18Z)"}
                      />
                      <input className={inputClass} placeholder="3///" value={getValue('meteo_6_5')} onChange={(e) => handleChange('meteo_6_5', e.target.value)} onKeyDown={handleKeyDown} title="3Ejjj: estado del suelo" />
                      <input className={inputClass} placeholder="" value={getValue('meteo_6_6')} onChange={(e) => handleChange('meteo_6_6', e.target.value)} onKeyDown={handleKeyDown} title="5EEEjE: evaporación" />
                    </div>
                  );
                }
                // Row 8: 58/59 P24 auto-generado en posición 2, 6RRR condicionado por Ir
                if (row === 8) {
                  return (
                    <div key={row} className="grid grid-cols-7 gap-2 mb-3">
                      <input className={inputClass} placeholder="" value={getValue('meteo_8_0')} onChange={(e) => handleChange('meteo_8_0', e.target.value)} onKeyDown={handleKeyDown} title="5nFnFnFn: insolación" />
                      <input className={inputClass} placeholder="56" value={getValue('meteo_8_1')} onChange={(e) => handleChange('meteo_8_1', e.target.value)} onKeyDown={handleKeyDown} title="56DLDMDH: nubes dirección" />
                      {/* 58/59 P24P24P24 - Auto-generado */}
                      <input className={readonlyClass} value={results.grupo_58_59_p24 || ''} readOnly title="58/59: cambio presión 24h" />
                      {/* 6 RRR tr - Condicionado por Ir */}
                      <input
                        className={results.include_precipitation ? inputClass : `${inputClass} opacity-50`}
                        placeholder="6"
                        value={getValue('meteo_8_3')}
                        onChange={(e) => handleChange('meteo_8_3', e.target.value)}
                        onKeyDown={handleKeyDown}
                        disabled={!results.include_precipitation}
                        title={results.include_precipitation ? "6RRRtr: precipitación" : "Omitido (Ir=3,4)"}
                      />
                      <input className={inputClass} placeholder="7" value={getValue('meteo_8_4')} onChange={(e) => handleChange('meteo_8_4', e.target.value)} onKeyDown={handleKeyDown} title="7R24R24R24R24: precipitación 24h" />
                      <input className={inputClass} placeholder="8" value={getValue('meteo_8_5')} onChange={(e) => handleChange('meteo_8_5', e.target.value)} onKeyDown={handleKeyDown} title="8NsChshs: nube adicional" />
                      <input className={inputClass} placeholder="8" value={getValue('meteo_8_6')} onChange={(e) => handleChange('meteo_8_6', e.target.value)} onKeyDown={handleKeyDown} title="8NsChshs: nube adicional" />
                    </div>
                  );
                }
                // Row 16: 555 constante y 29UUU auto-generado en últimas 2 posiciones
                if (row === 16) {
                  return (
                    <div key={row} className="grid grid-cols-7 gap-2 mb-3">
                      <input className={inputClass} placeholder="9" value={getValue('meteo_16_0')} onChange={(e) => handleChange('meteo_16_0', e.target.value)} />
                      <input className={inputClass} placeholder="9" value={getValue('meteo_16_1')} onChange={(e) => handleChange('meteo_16_1', e.target.value)} />
                      <input className={inputClass} placeholder="9" value={getValue('meteo_16_2')} onChange={(e) => handleChange('meteo_16_2', e.target.value)} />
                      <input className={inputClass} placeholder="9" value={getValue('meteo_16_3')} onChange={(e) => handleChange('meteo_16_3', e.target.value)} />
                      <input className={inputClass} placeholder="9" value={getValue('meteo_16_4')} onChange={(e) => handleChange('meteo_16_4', e.target.value)} />
                      {/* 555 - Sección 5 Constante */}
                      <input className={constantClass} value={CONST_555} readOnly title="Sección 555 - Constante" />
                      {/* 29UUU - Humedad relativa auto-generado */}
                      <input className={readonlyClass} value={results.grupo_29uuu || ''} readOnly title="Grupo 29UUU (humedad relativa)" />
                    </div>
                  );
                }
                if (isHeader && headers.length > 0) {
                  return (<div key={row} className="grid grid-cols-7 gap-2 mb-1">{headers.map((h, i) => (<div key={i} className={tableHeader}>{h}</div>))}</div>);
                }
                if (!isHeader && placeholders.length > 0) {
                  return (<div key={row} className="grid grid-cols-7 gap-2 mb-3">{placeholders.map((p, i) => (<input key={i} className={inputClass} placeholder={p} value={getValue(`meteo_${row}_${i}`)} onChange={(e) => handleChange(`meteo_${row}_${i}`, e.target.value)} />))}</div>);
                }
                return null;
              })}
            </div>

            {/* Tabla de Cálculos de Estación */}
            <div className="bg-white rounded-xl shadow-lg p-5 transition-all duration-500">
              <div className="grid grid-cols-7 gap-2 mb-3">
                <div className={`col-span-2 ${primaryHeader}`} style={{ backgroundColor: currentTheme.accentColor }}>Cálculos de Estación</div>
                <div className={primaryHeader} style={{ backgroundColor: currentTheme.accentColor }}>Presión de la Estación</div>
                <div className={primaryHeader} style={{ backgroundColor: currentTheme.accentColor }}>P 3 Horas</div>
                <div className={primaryHeader} style={{ backgroundColor: currentTheme.accentColor }}>P 24 Horas</div>
                <div className={primaryHeader} style={{ backgroundColor: currentTheme.accentColor }}>Máx. / Mín.</div>
                <div className={primaryHeader} style={{ backgroundColor: currentTheme.accentColor }}>Máx. / Mín. (24 H)</div>
              </div>

              <div className="grid grid-cols-7 gap-2 mb-1">
                <div className={tableHeader}>Ts.</div>
                <input className={inputClass} placeholder="°C" value={getValue('ts')} onChange={(e) => handleChange('ts', e.target.value)} />
                <div className={tableHeader}>Let. Barom.</div>
                <div className={tableHeader}>P 3</div>
                <div className={tableHeader}>P 24</div>
                <div className={tableHeader}>T Máx.</div>
                <div className={tableHeader}>T Máx.</div>
              </div>

              <div className="grid grid-cols-7 gap-2 mb-1">
                <div className={tableHeader}>Pr.</div>
                <input className={readonlyClass} value={results.punto_rocio || ''} readOnly title="Punto de rocío calculado" placeholder="°C" />
                <input className={inputClass} placeholder="Lectura..." value={getValue('let_barom')} onChange={(e) => handleChange('let_barom', e.target.value)} onKeyDown={handleKeyDown} title="Lectura barométrica sin corregir" />
                <input
                  className={inputClass}
                  placeholder="hPa"
                  value={getValue('p3')}
                  onChange={(e) => handleChange('p3', e.target.value)}
                  onBlur={() => handlePressureBlur('p3')}
                  onKeyDown={(e) => handlePressureKeyDown(e, 'p3')}
                  title="Presión hace 3 horas"
                />
                <input
                  className={inputClass}
                  placeholder="hPa"
                  value={getValue('p24')}
                  onChange={(e) => handleChange('p24', e.target.value)}
                  onBlur={() => handlePressureBlur('p24')}
                  onKeyDown={(e) => handlePressureKeyDown(e, 'p24')}
                  title="Presión hace 24 horas"
                />
                <input className={isEvenHour ? inputClass : `${inputClass} opacity-50 bg-gray-200`} placeholder="°C" value={getValue('t_max')} onChange={(e) => handleChange('t_max', e.target.value)} onKeyDown={handleKeyDown} disabled={!isEvenHour} title={isEvenHour ? "Temperatura máxima" : "Solo en horas pares"} />
                <input className={isEvenHour ? inputClass : `${inputClass} opacity-50 bg-gray-200`} placeholder="°C" value={getValue('t_max_24h')} onChange={(e) => handleChange('t_max_24h', e.target.value)} onKeyDown={handleKeyDown} disabled={!isEvenHour} title={isEvenHour ? "Temperatura máxima 24h" : "Solo en horas pares"} />
              </div>

              <div className="grid grid-cols-7 gap-2 mb-1">
                <div className={tableHeader}>Th.</div>
                <input className={inputClass} placeholder="°C" value={getValue('th')} onChange={(e) => handleChange('th', e.target.value)} onKeyDown={handleKeyDown} title="Temperatura húmeda" />
                <div className={tableHeader}>Correc. Temp.</div>
                <div className={tableHeader}>Let.</div>
                <div className={tableHeader}>Let.</div>
                <div className={tableHeader}>T Mín.</div>
                <div className={tableHeader}>T Mín.</div>
              </div>

              <div className="grid grid-cols-7 gap-2 mb-1">
                <div className={tableHeader}>Tv.</div>
                <input className={readonlyClass} value={results.tension_vapor || ''} readOnly title="Tensión de vapor calculada" placeholder="hPa" />
                <input className={inputClass} placeholder="0.0" value={getValue('correc_temp')} onChange={(e) => handleChange('correc_temp', e.target.value)} onKeyDown={handleKeyDown} title="Corrección por temperatura" />
                <input className={readonlyClass} value={results.p3_let || ''} readOnly title="Lectura P3 = Pres.Est." placeholder="hPa" />
                <input className={readonlyClass} value={results.p24_let || ''} readOnly title="Lectura P24 = Pres.Est." placeholder="hPa" />
                <input className={isEvenHour ? inputClass : `${inputClass} opacity-50 bg-gray-200`} placeholder="°C" value={getValue('t_min')} onChange={(e) => handleChange('t_min', e.target.value)} onKeyDown={handleKeyDown} disabled={!isEvenHour} title={isEvenHour ? "Temperatura mínima" : "Solo en horas pares"} />
                <input className={isEvenHour ? inputClass : `${inputClass} opacity-50 bg-gray-200`} placeholder="°C" value={getValue('t_min_24h')} onChange={(e) => handleChange('t_min_24h', e.target.value)} onKeyDown={handleKeyDown} disabled={!isEvenHour} title={isEvenHour ? "Temperatura mínima 24h" : "Solo en horas pares"} />
              </div>

              <div className="grid grid-cols-7 gap-2 mb-1">
                <div className={tableHeader}>Dif.</div>
                <input className={readonlyClass} value={results.diferencia || ''} readOnly title="Diferencia Ts - Th" placeholder="°C" />
                <div className={tableHeader}>Pres. Est.</div>
                <div className={tableHeader}>Dif.</div>
                <div className={tableHeader}>Dif.</div>
                <div className={tableHeader}>LL</div>
                <div className={tableHeader}>LL</div>
              </div>

              <div className="grid grid-cols-7 gap-2 mb-1">
                <div className={tableHeader}>Hr.</div>
                <input className={readonlyClass} value={results.humedad_relativa ? `${results.humedad_relativa}%` : ''} readOnly title="Humedad relativa calculada" placeholder="%" />
                <input
                  className={inputClass}
                  placeholder="hPa"
                  value={getValue('pres_est')}
                  onChange={(e) => handleChange('pres_est', e.target.value)}
                  onBlur={() => handlePressureBlur('pres_est')}
                  onKeyDown={(e) => handlePressureKeyDown(e, 'pres_est')}
                  title="Presión de la estación"
                />
                <input className={readonlyClass} value={results.p3_dif || ''} readOnly title="Diferencia Pres.Est - P3" placeholder="hPa" />
                <input className={readonlyClass} value={results.p24_dif || ''} readOnly title="Diferencia Pres.Est - P24" placeholder="hPa" />
                <input className={inputClass} placeholder="mm" value={getValue('ll')} onChange={(e) => handleChange('ll', e.target.value)} onKeyDown={handleKeyDown} title="Precipitación (mm)" />
                <input className={inputClass} placeholder="mm" value={getValue('ll_24h')} onChange={(e) => handleChange('ll_24h', e.target.value)} onKeyDown={handleKeyDown} title="Precipitación 24h (mm)" />
              </div>

              <div className="grid grid-cols-7 gap-2 mb-1">
                <div className="col-span-2"></div>
                <div className={tableHeader}>Correc. Alt.</div>
                <div className="col-span-4"></div>
              </div>
              <div className="grid grid-cols-7 gap-2 mb-1">
                <div className="col-span-2"></div>
                <input className={readonlyClass} value={getValue('correc_alt') || ''} readOnly title="Corrección por altitud" placeholder="hPa" />
                <div className="col-span-4"></div>
              </div>

              <div className="grid grid-cols-7 gap-2 mb-1">
                <div className="col-span-2"></div>
                <div className={tableHeader}>Pres. NMM</div>
                <div className="col-span-4"></div>
              </div>
              <div className="grid grid-cols-7 gap-2">
                <div className="col-span-2"></div>
                <input className={readonlyClass} value={results.pres_nmm || ''} readOnly title="Presión al nivel medio del mar" placeholder="hPa" />
                <div className="col-span-4"></div>
              </div>

              {/* Mensaje de error */}
              {errorMessage && <p className={errorClass}>{errorMessage}</p>}
            </div>
          </div>

          {/* Panel de Navegación */}
          <div className="w-36 bg-white rounded-xl shadow-lg p-4 transition-all duration-500">
            <h2 className="text-sm font-bold mb-4 text-center text-gray-700">Observación</h2>

            <div className="space-y-2">
              {hours.map(hora => (
                <button
                  key={hora}
                  onClick={() => handleHourChange(hora)}
                  className={`w-full py-2.5 px-3 rounded-lg font-medium text-sm transition-all duration-300 ${activeHour === hora
                    ? 'text-white shadow-md scale-105'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  style={activeHour === hora ? { backgroundColor: currentTheme.accentColor } : {}}
                >
                  {hora}
                </button>
              ))}

              {/* Botones de navegación entre días */}
              <div className="flex gap-1 mt-3">
                <button
                  onClick={handlePreviousDay}
                  className="flex-1 py-2 px-2 rounded-lg font-medium text-xs bg-blue-100 text-blue-700 hover:bg-blue-200 transition-all duration-300 flex items-center justify-center gap-1"
                  title="Guardar y cargar día anterior"
                >
                  <span>←</span>
                  <span>Ant.</span>
                </button>
                <button
                  onClick={handleNextDay}
                  className="flex-1 py-2 px-2 rounded-lg font-medium text-xs bg-green-100 text-green-700 hover:bg-green-200 transition-all duration-300 flex items-center justify-center gap-1"
                  title="Guardar y avanzar al siguiente día"
                >
                  <span>Sig.</span>
                  <span>→</span>
                </button>
              </div>
            </div>

            {/* Botones CLI */}
            <div className="mt-4 pt-3 border-t border-gray-200">
              <h2 className="text-sm font-bold mb-4 text-center text-gray-700">CLI</h2>
              <div className="space-y-2">
                <button
                  onClick={() => navigate('/maintenance')}
                  className="w-full py-2 px-3 rounded-lg font-medium text-xs bg-amber-100 text-amber-700 hover:bg-amber-200 transition-colors"
                >
                  3074
                </button>
                <button
                  onClick={() => navigate('/maintenance')}
                  className="w-full py-2 px-3 rounded-lg font-medium text-xs bg-amber-100 text-amber-700 hover:bg-amber-200 transition-colors"
                >
                  4074
                </button>
                <button
                  onClick={() => navigate('/maintenance')}
                  className="w-full py-2 px-3 rounded-lg font-medium text-xs bg-amber-100 text-amber-700 hover:bg-amber-200 transition-colors"
                >
                  5074
                </button>
              </div>
            </div>

            {/* Campos extra 8NsChshs */}
            <div className="mt-4 pt-3 border-t border-gray-200">
              <div className={`${tableHeader} rounded-lg mb-2`}>8NsChshs Extra</div>
              <div className="space-y-2">
                <input
                  className={inputClass}
                  placeholder="8"
                  value={getValue('extra_8ns_1')}
                  onChange={(e) => handleChange('extra_8ns_1', e.target.value)}
                  onKeyDown={handleKeyDown}
                  title="Ns=nubosidad, C=tipo, hshs=altura"
                />
                <input
                  className={inputClass}
                  placeholder="8"
                  value={getValue('extra_8ns_2')}
                  onChange={(e) => handleChange('extra_8ns_2', e.target.value)}
                  onKeyDown={handleKeyDown}
                  title="Ns=nubosidad, C=tipo, hshs=altura"
                />
              </div>
            </div>

            {/* Botones Cargar/Guardar (debajo de 8NsChshs, independientes) */}
            <div className="mt-4 pt-3 border-t border-gray-200 space-y-2">
              {/* Cargar JSON - Solo Admin */}
              {isAdmin() && (
                <label className="w-full py-2 px-3 rounded-lg font-bold text-xs bg-blue-100 text-blue-700 hover:bg-blue-200 cursor-pointer transition-colors flex items-center justify-center gap-2">
                  📂 Cargar JSON
                  <input
                    type="file"
                    accept=".json"
                    className="hidden"
                    onChange={handleLoadJson}
                  />
                </label>
              )}
              {/* Guardar */}
              <button
                onClick={handleSave}
                className="w-full py-2 px-3 rounded-lg text-white font-bold text-sm transition-all shadow-md hover:opacity-90"
                style={{ backgroundColor: currentTheme.accentColor }}
              >
                💾 Guardar
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SynopticPage;
