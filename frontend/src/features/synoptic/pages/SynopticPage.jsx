import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { invoke } from '@tauri-apps/api/core';
import { ArrowLeft, Save, Upload, ArrowRight, Sun, Moon, FileText, Cloud, Clock, Sunrise, Sunset } from 'lucide-react';
import { isAdmin } from '../../../shared/utils/auth';
import { hourThemes, meteoHeaders, meteoPlaceholders, styles } from '../config/synopticConfig';
import { AAXX, CONST_333, CONST_555, HOURS, EVEN_HOURS, ODD_HOURS, normalizePressure } from '../utils/synopticUtils';
import { toast } from 'react-hot-toast';

// =============================================================================
// COMPONENTE PRINCIPAL
// =============================================================================



// =============================================================================

// normalizePressure importado de utils/synopticUtils

// =============================================================================
// COMPONENTE PRINCIPAL
// =============================================================================

const SynopticPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const hours = HOURS;
  const evenHours = EVEN_HOURS;

  // =========================================================================
  // SESSION STORAGE DRAFT — Persistir estado al navegar a sub-módulos
  // =========================================================================
  const DRAFT_KEY = 'synoptic_draft';

  const saveDraft = () => {
    try {
      const draft = { observations: observationsRef.current, activeHour: activeHourRef.current, resultsPerHour: resultsPerHourRef.current };
      sessionStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
    } catch (e) { console.warn('Error guardando draft:', e); }
  };

  const loadDraft = () => {
    try {
      const raw = sessionStorage.getItem(DRAFT_KEY);
      if (raw) return JSON.parse(raw);
    } catch (e) { console.warn('Error cargando draft:', e); }
    return null;
  };

  const clearDraft = () => sessionStorage.removeItem(DRAFT_KEY);

  // Estado inicial: tomar del draft o crear vacío
  const savedDraft = loadDraft();

  const [observations, setObservations] = useState(
    savedDraft?.observations || hours.reduce((acc, hour) => ({ ...acc, [hour]: {} }), {})
  );

  // Hora activa por defecto: tomar de la navegación, del draft o valor por defecto
  const [activeHour, setActiveHour] = useState(location.state?.activeHour || savedDraft?.activeHour || '06Z');
  const [results, setResults] = useState({});
  const [resultsPerHour, setResultsPerHour] = useState(savedDraft?.resultsPerHour || {});
  const [errorMessage, setErrorMessage] = useState('');
  const [stations, setStations] = useState({});
  // eslint-disable-next-line no-unused-vars
  const [isCalculating, setIsCalculating] = useState(false);
  const [isLoading, setIsLoading] = useState(!!savedDraft); // Evitar recálculo inicial si restauramos draft
  const [isStationLocked, setIsStationLocked] = useState(false);

  // Refs para acceso sincrónico en saveDraft
  const observationsRef = React.useRef(observations);
  const activeHourRef = React.useRef(activeHour);
  const resultsPerHourRef = React.useRef(resultsPerHour);
  React.useEffect(() => { observationsRef.current = observations; }, [observations]);
  React.useEffect(() => { activeHourRef.current = activeHour; }, [activeHour]);
  React.useEffect(() => { resultsPerHourRef.current = resultsPerHour; }, [resultsPerHour]);

  // Si restauramos draft, quitar flag isLoading después de montar
  React.useEffect(() => {
    if (savedDraft) {
      const timer = setTimeout(() => setIsLoading(false), 500);
      return () => clearTimeout(timer);
    }
  }, []);

  // Determinar si la hora activa es par (tiene T_max/T_min)
  const isEvenHour = evenHours.includes(activeHour);

  // Cargar lista de estaciones al montar
  useEffect(() => {
    const fetchStations = async () => {
      try {
        const data = await invoke('get_stations');
        setStations(data);
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
      const calcResults = await invoke('calculate_observations', {
        data: {
          ts: data.ts || '',
          th: data.th || '',
          pres_est: data.pres_est || '',
          p3: data.p3 || '',
          p24: data.p24 || '',
          correc_alt: data.correc_alt || '',
          station_id: data.station_id || '',
          ir: data.ir || '',
          ix: data.ix || ''
        }
      });

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
      // Guardar resultados por hora específica
      setResultsPerHour(prev => ({
        ...prev,
        [activeHour]: calcResults
      }));
    } catch (error) {
      console.error('Error en cálculos:', error);
      // Fallback: resultados vacíos
      setResults({});
    } finally {
      setIsCalculating(false);
    }
  }, [activeHour]);

  // Extraer sólo los datos relevantes para los cálculos matemáticos en caliente
  const currentCalcInput = observations[activeHour] ? {
    ts: observations[activeHour].ts || '',
    th: observations[activeHour].th || '',
    pres_est: observations[activeHour].pres_est || '',
    p3: observations[activeHour].p3 || '',
    p24: observations[activeHour].p24 || '',
    correc_alt: observations[activeHour].correc_alt || '',
    station_id: observations[activeHour].station_id || '',
    ir: observations[activeHour].ir || '',
    ix: observations[activeHour].ix || ''
  } : null;

  // Efecto para recalcular resultados cuando cambia la hora o los datos de cálculo
  useEffect(() => {
    // No calcular mientras se está cargando un archivo
    if (isLoading || !currentCalcInput) return;

    // Debounce para evitar muchas llamadas
    const timeoutId = setTimeout(() => {
      performCalculations(currentCalcInput);
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [activeHour, JSON.stringify(currentCalcInput), performCalculations, isLoading]);

  const handleChange = (key, value) => {
    // Regla de exclusión mutua: 0CS DL DM DH vs 56 DL DM DH
    // Si se usa meteo_6_2 (0CS), limpiar meteo_8_1 (56)
    // Si se usa meteo_8_1 (56), limpiar meteo_6_2 (0CS)
    setObservations(prev => {
      const newObservations = {
        ...prev,
        [activeHour]: {
          ...prev[activeHour],
          [key]: value
        }
      };

      // Aplicar regla de exclusión mutua
      if (key === 'meteo_6_2' && value && value.trim() !== '') {
        // Si se está llenando 0CS DL DM DH, limpiar 56 DL DM DH
        newObservations[activeHour].meteo_8_1 = '';
      } else if (key === 'meteo_8_1' && value && value.trim() !== '') {
        // Si se está llenando 56 DL DM DH, limpiar 0CS DL DM DH
        newObservations[activeHour].meteo_6_2 = '';
      }

      return newObservations;
    });
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
        toast.error('Debe seleccionar una estación antes de guardar');
        return;
      }
      if (!fecha) {
        toast.error('Debe seleccionar una fecha antes de guardar');
        return;
      }

      // Removida restricción de hora - se puede guardar desde cualquier hora

      // Preparar datos de todas las horas - cada hora con sus propios cálculos
      const observationsWithResults = {};
      for (const hora of hours) {
        const horaData = observations[hora] || {};
        // Obtener resultados de esta hora específica (no de la hora activa)
        const horaResults = resultsPerHour[hora] || {};
        observationsWithResults[hora] = {
          ...horaData,
          // Incluir SOLO resultados calculados de esta hora específica
          pres_nmm: horaResults.pres_nmm || '',
          punto_rocio: horaResults.punto_rocio || '',
          tension_vapor: horaResults.tension_vapor || '',
          humedad_relativa: horaResults.humedad_relativa || '',
          diferencia: horaResults.diferencia || ''
        };
      }

      const response = await invoke('save_observation_json', {
        stationCode: stationId,
        fecha: fecha,
        observations: observationsWithResults,
        observerName: getValue('observador') || null
      });

      if (response.success) {
        // Mostrar confirmación con fecha formateada
        const fecha = getValue('fecha');
        const fechaFormatted = fecha ? (() => {
          const [yyyy, mm, dd] = fecha.split('-');
          return `${dd}/${mm}/${yyyy}`;
        })() : '';

        // Bloquear cambio de estación después de guardar y limpiar draft
        setIsStationLocked(true);
        clearDraft();

        toast.success(`Observación guardada. Fecha: ${fechaFormatted}`);
      }
    } catch (error) {
      console.error('Error al guardar:', error);
      toast.error('Error al guardar la observación');
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
        const rangeData = await invoke('get_station_date_range', { stationCode: currentStation });
        const oldestDate = rangeData.oldest_date;

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

        await invoke('save_observation_json', {
          stationCode: currentStation,
          fecha: currentDate,
          observations: observationsWithResults,
          observerName: getValue('nombre_observador') || null
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

      const responseData = await invoke('get_observation', { 
        stationCode: currentStation, 
        fecha: fechaForBackend 
      });

      if (responseData && Object.keys(responseData).some(key => hours.includes(key))) {
        setIsLoading(true);

        const newObservations = {};
        hours.forEach(hora => {
          newObservations[hora] = {
            station_id: currentStation,
            fecha: targetDate,
            correc_alt: correcAlt
          };
        });

        hours.forEach(hora => {
          const item = responseData[hora];
          if (item && Object.keys(item).length > 0) {
            newObservations[hora] = {
              ...newObservations[hora],
              // La data proveniente de Rust es plana y ya tiene los keys en minúscula y transformados
              // Conservamos pre-existentes y pisamos con los devueltos
              ...item
            };
          }
        });

        setObservations(newObservations);
        setActiveHour('06Z'); // Reset a 06Z como default al cambiar de día
        setTimeout(() => setIsLoading(false), 100);
        console.log(`📂 Cargado día existente: ${targetDate}`);
      }
    } catch (error) {
      if (typeof error === 'string' && error.includes('no encontrada')) {
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

      await invoke('save_observation_json', {
        stationCode: stationId,
        fecha: fecha,
        observations: observationsWithResults,
        observerName: getValue('nombre_observador') || null
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
        if (jsonData.horas) {
          Object.entries(jsonData.horas).forEach(([hora, item]) => {
            if (hours.includes(hora) && Object.keys(item).length > 0) {
              const d = item.datos || {};
              const s = item.synop_manual || item.synop || {}; // Compatibilidad con formato anterior

newObservations[hora] = {
  ...newObservations[hora],

  // Observador
  nombre_observador: item.nombre_observador || '',

  // Temperaturas básicas
  ts: safeValue(d.ts),
  th: safeValue(d.th),

  // T_max/T_min
  t_max: safeValue(d.Tmax),
  t_min: safeValue(d.Tmin),
  t_max_24h: safeValue(d.Tmax_24h),
  t_min_24h: safeValue(d.Tmin_24h),

  // Presión
  pres_est: safeValue(d.pres_est),
  p3: safeValue(d.p3),
  p24: safeValue(d.p24),
  let_barom: d.let_barom || '',

  // Precipitación
  ll: safeValue(d.LL),
  ll_24h: safeValue(d.LL_24h),

  // ===== Grupos SYNOP =====
  // Fila 2 - YYGGIw
  meteo_2_1: s['YYGGiw'] || item.yygg_iw || '',

  // Fila 4
                meteo_4_irixhvv: s['IrIXHVV'] || '',
                meteo_4_1: s['Nddff'] || '',
                meteo_4_6: s['7wwW1W2'] || '',

                // Fila 6
                meteo_6_0: s['8NhCLCMCH'] || '',
                meteo_6_2: s['0CSDL DM DH'] || '',
                meteo_6_3: s['1snTxTxTx'] || '',
                meteo_6_4: s['2snTnTnTn'] || '',
                meteo_6_5: s['3Ejjj'] || '',
                meteo_6_6: s['5EEEjE'] || '',

                // Fila 8
                meteo_8_0: s['5nFnFnFn'] || '',
                meteo_8_1: s['56DLDMDH'] || '',
                meteo_8_3: s['6RRRtr'] || '',
                meteo_8_4: s['7R24R24R24R24'] || '',
                meteo_8_5: s['8NsChshs_1'] || '',
                meteo_8_6: s['8NsChshs_2'] || '',

                // Fila 10
                meteo_10_0: s['8NsChshs_5'] || '',
                meteo_10_1: s['8NsChshs_6'] || '',
                meteo_10_2: s['9spspsp_1'] || '',
                meteo_10_3: s['9spspsp_2'] || '',
                meteo_10_4: s['9spspsp_3'] || '',
                meteo_10_5: s['9spspsp_4'] || '',
                meteo_10_6: s['9spspsp_5'] || '',

                // Fila 12
                meteo_12_0: s['9spspsp_6'] || '',
                meteo_12_1: s['9spspsp_7'] || '',
                meteo_12_2: s['9spspsp_8'] || '',
                meteo_12_3: s['9spspsp_9'] || '',
                meteo_12_4: s['9spspsp_10'] || '',
                meteo_12_5: s['9spspsp_11'] || '',
                meteo_12_6: s['9spspsp_12'] || '',

                // Fila 14
                meteo_14_0: s['9spspsp_13'] || '',
                meteo_14_1: s['9spspsp_14'] || '',
                meteo_14_2: s['9spspsp_15'] || '',
                meteo_14_3: s['9spspsp_16'] || '',
                meteo_14_4: s['9spspsp_17'] || '',
                meteo_14_5: s['9spspsp_18'] || '',
                meteo_14_6: s['9spspsp_19'] || '',

                // Fila 16
                meteo_16_0: s['9spspsp_20'] || '',
                meteo_16_1: s['9spspsp_21'] || '',
                meteo_16_2: s['9spspsp_22'] || '',
                meteo_16_3: s['9spspsp_23'] || '',
                meteo_16_4: s['9spspsp_24'] || '',
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

        toast.success(`Observación cargada. Estación: ${stationCode}`);

        // Resetear el input
        event.target.value = '';
      } catch (error) {
        console.error('Error al parsear JSON:', error);
        toast.error('Error al cargar el archivo JSON. Verifique el formato.');
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

  const currentTheme = hourThemes[activeHour];

  // Estilos dinámicos desestructurados de config
  const { tableHeader, inputClass, readonlyClass, constantClass, errorClass } = styles;
  const primaryHeader = `text-white font-bold text-sm px-3 py-2 rounded-lg text-center transition-colors duration-500`;

  return (
    <div className={`min-h-screen p-6 transition-colors duration-1000 bg-gradient-to-br ${currentTheme.bgGradient}`}>
      <div className="max-w-7xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <button
            onClick={() => navigate('/dashboard')}
            className={`w-10 h-10 rounded-full backdrop-blur-md bg-white/10 border border-white/20 shadow-lg transition-all hover:bg-white/20 hover:scale-110 flex items-center justify-center ${currentTheme.textColor}`}
            title="Volver al Dashboard"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
        </div>

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
                        {Object.keys(stations).map((id) => (
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
        // Verificar si el campo opuesto (56 DL DM DH) tiene valor
        const has56DLDM = (getValue('meteo_8_1') || '').trim() !== '';
        
        return (
          <div key={row} className="grid grid-cols-7 gap-2 mb-3">
            <input className={inputClass} placeholder="8" value={getValue('meteo_6_0')} onChange={(e) => handleChange('meteo_6_0', e.target.value)} onKeyDown={handleKeyDown} title="8NhCLCMCH: nubes" />
            <input className={constantClass} value={CONST_333} readOnly title="Sección 333" />
            {/* 0CS DL DM DH - Deshabilitado si 56 DL DM DH tiene valor */}
            <input 
              className={has56DLDM ? `${inputClass} opacity-50 bg-gray-200` : inputClass} 
              placeholder="0" 
              value={getValue('meteo_6_2')} 
              onChange={(e) => handleChange('meteo_6_2', e.target.value)} 
              onKeyDown={handleKeyDown} 
              disabled={has56DLDM}
              title={has56DLDM ? "Deshabilitado: use 56 DL DM DH en su lugar" : "0CSDLDMDH: nubes dirección"} 
            />
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
        // Verificar si el campo opuesto (0CS DL DM DH) tiene valor
        const has0CSDLDM = (getValue('meteo_6_2') || '').trim() !== '';
        
        return (
          <div key={row} className="grid grid-cols-7 gap-2 mb-3">
            <input className={inputClass} placeholder="" value={getValue('meteo_8_0')} onChange={(e) => handleChange('meteo_8_0', e.target.value)} onKeyDown={handleKeyDown} title="5nFnFnFn: insolación" />
            {/* 56 DL DM DH - Deshabilitado si 0CS DL DM DH tiene valor */}
            <input 
              className={has0CSDLDM ? `${inputClass} opacity-50 bg-gray-200` : inputClass} 
              placeholder="56" 
              value={getValue('meteo_8_1')} 
              onChange={(e) => handleChange('meteo_8_1', e.target.value)} 
              onKeyDown={handleKeyDown} 
              disabled={has0CSDLDM}
              title={has0CSDLDM ? "Deshabilitado: use 0CS DL DM DH en su lugar" : "56DLDMDH: nubes dirección"} 
            />
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

          {/* Panel de Navegación en Tarjetas Independientes */}
          <div className="w-64 flex flex-col gap-4 sticky top-6 transition-all duration-500">
            
            {/* Tarjeta 1: Horas de Observación */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200/80 p-4 transition-all duration-300 hover:shadow-md">
              <h2 className="text-xs font-bold mb-3 text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5" /> Horas de Observación
              </h2>
              <div className="grid grid-cols-2 gap-2">
                {hours.map(hora => {
                  let icon;
                  if (hora === '06Z') {
                    icon = <Sunrise className={`w-3.5 h-3.5 ${activeHour === hora ? 'text-white' : 'text-orange-400'}`} />;
                  } else if (['09Z', '12Z', '15Z'].includes(hora)) {
                    icon = <Sun className={`w-3.5 h-3.5 ${activeHour === hora ? 'text-white' : 'text-amber-500 animate-pulse'}`} />;
                  } else if (hora === '18Z') {
                    icon = <Sunset className={`w-3.5 h-3.5 ${activeHour === hora ? 'text-white' : 'text-rose-400'}`} />;
                  } else {
                    icon = <Moon className={`w-3.5 h-3.5 ${activeHour === hora ? 'text-white' : 'text-indigo-400'}`} />;
                  }

                  return (
                    <button
                      key={hora}
                      onClick={() => handleHourChange(hora)}
                      className={`py-2 px-2.5 rounded-lg font-bold text-xs transition-all duration-300 cursor-pointer flex items-center justify-center gap-1.5 border border-transparent shadow-sm ${activeHour === hora
                        ? 'text-white shadow-md scale-105'
                        : 'bg-slate-50 text-slate-600 hover:bg-slate-100 hover:text-slate-900 hover:scale-105 hover:border-slate-300 hover:shadow'
                        }`}
                      style={activeHour === hora ? { backgroundColor: currentTheme.accentColor } : {}}
                    >
                      {icon}
                      <span>{hora}</span>
                    </button>
                  );
                })}
              </div>

              {/* Botones de navegación entre días */}
              <div className="flex gap-2 mt-3 pt-3 border-t border-slate-100">
                <button
                  onClick={handlePreviousDay}
                  className="flex-1 py-2 px-3 rounded-lg bg-sky-50 text-sky-700 hover:bg-sky-100 hover:scale-105 hover:border-sky-200 hover:shadow-sm active:scale-95 transition-all duration-300 flex items-center justify-center cursor-pointer border border-sky-100/50 shadow-sm"
                  title="Guardar y cargar día anterior"
                >
                  <ArrowLeft className="w-4 h-4" />
                </button>
                <button
                  onClick={handleNextDay}
                  className="flex-1 py-2 px-3 rounded-lg bg-green-50 text-green-700 hover:bg-green-100 hover:scale-105 hover:border-green-200 hover:shadow-sm active:scale-95 transition-all duration-300 flex items-center justify-center cursor-pointer border border-green-100/50 shadow-sm"
                  title="Guardar y avanzar al siguiente día"
                >
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Tarjeta 2: Módulos CLI (Solo Números con Iconos) */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200/80 p-4 transition-all duration-300 hover:shadow-md">
              <h2 className="text-xs font-bold mb-3 text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5" /> Módulos CLI
              </h2>
              <div className="grid grid-cols-3 gap-2">
                {['3074', '4074', '5074'].map(code => (
                  <button
                    key={code}
                    onClick={() => { saveDraft(); navigate(`/cli${code}`, { state: { stationId: getValue('station_id'), date: getValue('fecha') } }); }}
                    className="flex flex-col items-center justify-center py-2 px-1 rounded-xl text-xs font-bold border border-slate-100 bg-slate-50/50 text-slate-700 hover:bg-amber-50 hover:border-amber-200 hover:text-amber-800 transition-all duration-200 cursor-pointer shadow-sm"
                    title={`Ver reporte CLI ${code}`}
                  >
                    <FileText className="w-4 h-4 mb-1 text-slate-400 group-hover:text-amber-600" />
                    <span>{code}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Tarjeta 3: Campos Extra 8NsChshs */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200/80 p-4 transition-all duration-300 hover:shadow-md">
              <h2 className="text-xs font-bold mb-3 text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                <Cloud className="w-3.5 h-3.5" /> Nubosidad Extra
              </h2>
              <div className="space-y-3">
                <div>
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Grupo Extra 1 (8Ns)</label>
                  <input
                    className={`${inputClass} !w-full`}
                    placeholder="8..."
                    value={getValue('extra_8ns_1')}
                    onChange={(e) => handleChange('extra_8ns_1', e.target.value)}
                    onKeyDown={handleKeyDown}
                    title="Ns=nubosidad, C=tipo, hshs=altura"
                  />
                </div>
                <div>
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Grupo Extra 2 (8Ns)</label>
                  <input
                    className={`${inputClass} !w-full`}
                    placeholder="8..."
                    value={getValue('extra_8ns_2')}
                    onChange={(e) => handleChange('extra_8ns_2', e.target.value)}
                    onKeyDown={handleKeyDown}
                    title="Ns=nubosidad, C=tipo, hshs=altura"
                  />
                </div>
              </div>
            </div>

            {/* Tarjeta 4: Acciones Cargar/Guardar */}
            <div className="bg-white rounded-2xl shadow-sm border border-slate-200/80 p-4 transition-all duration-300 hover:shadow-md flex flex-col gap-2">
              <button
                onClick={handleSave}
                className="w-full py-2.5 px-4 rounded-xl text-white font-bold text-sm transition-all shadow-md hover:shadow-lg hover:opacity-95 flex items-center justify-center gap-2 cursor-pointer hover:scale-102"
                style={{ backgroundColor: currentTheme.accentColor }}
              >
                <Save className="w-4 h-4" /> Guardar Observación
              </button>
              
              {isAdmin() && (
                <label className="w-full py-2 px-4 rounded-xl font-bold text-xs bg-slate-50 border border-slate-200 text-slate-700 hover:bg-slate-100 cursor-pointer transition-colors flex items-center justify-center gap-2 hover:scale-102 shadow-sm">
                  <Upload className="w-3.5 h-3.5" /> Cargar JSON
                  <input
                    type="file"
                    accept=".json"
                    className="hidden"
                    onChange={handleLoadJson}
                  />
                </label>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SynopticPage;
