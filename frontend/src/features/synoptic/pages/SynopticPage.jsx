import React, { useState, useEffect } from 'react';
import axios from '../../../shared/api/axiosConfig';

const SynopticPage = () => {
  const hours = ["06Z", "09Z", "12Z", "15Z", "18Z", "21Z", "00Z", "03Z"];

  // Estado inicial: objeto con claves para cada hora
  const [observations, setObservations] = useState(
    hours.reduce((acc, hour) => ({ ...acc, [hour]: {} }), {})
  );

  // Hora activa por defecto: 06Z
  const [activeHour, setActiveHour] = useState('06Z');
  const [results, setResults] = useState({});

  // Efecto para recalcular resultados cuando cambia la hora o los datos de la hora actual
  useEffect(() => {
    const currentData = observations[activeHour] || {};
    calculateResults(currentData);
  }, [activeHour, observations]);

  const handleChange = (key, value) => {
    setObservations(prev => ({
      ...prev,
      [activeHour]: {
        ...prev[activeHour],
        [key]: value
      }
    }));
  };

  const calculateResults = (data) => {
    const ts = parseFloat(data.ts) || 0;
    const th = parseFloat(data.th) || 0;
    const diferencia = ts - th;

    let tensionVapor = 0;
    let humedadRelativa = 0;
    let puntoRocio = 0;

    if (th !== 0) {
      tensionVapor = 6.11 * Math.pow(10, (7.5 * th) / (237.3 + th));
    }

    if (ts !== 0) {
      const tensionSaturacion = 6.11 * Math.pow(10, (7.5 * ts) / (237.3 + ts));
      if (tensionSaturacion !== 0) {
        humedadRelativa = (tensionVapor / tensionSaturacion) * 100;
      }
    }

    if (humedadRelativa !== 0) {
      puntoRocio = th - ((100 - humedadRelativa) / 5);
    }

    setResults({
      diferencia: diferencia.toFixed(1),
      tension_vapor: tensionVapor.toFixed(1),
      humedad_relativa: Math.min(100, humedadRelativa).toFixed(0),
      punto_rocio: puntoRocio.toFixed(1)
    });
  };

  const handleSave = async () => {
    try {
      // Guardamos solo los datos de la hora activa
      const currentData = observations[activeHour];
      await axios.post('/synoptic/observations', { ...currentData, hora: activeHour });
      alert(`Observación de las ${activeHour} guardada exitosamente`);
    } catch (error) {
      console.error('Error al guardar:', error);
      alert('Error al guardar la observación');
    }
  };

  // Helper para obtener el valor del campo actual de forma segura
  const getValue = (key) => {
    return observations[activeHour]?.[key] || '';
  };

  // Colores del tema (azul para coincidir con el diseño)
  const primaryHeader = "text-white font-bold text-sm px-3 py-2 rounded-lg text-center";
  const tableHeader = "bg-slate-600 text-white font-semibold text-xs px-2 py-2 text-center";
  const inputClass = "bg-white border border-slate-300 text-slate-800 text-sm px-2 py-2 rounded w-full focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none text-center";
  const readonlyClass = "bg-slate-100 border border-slate-300 text-blue-700 font-semibold text-sm px-2 py-2 rounded w-full text-center";

  const primaryColor = "#2563eb"; // blue-600

  const meteoHeaders = {
    1: ["MiMi MjMj", "YYGG Iw", "IIiii", "Fecha"],
    3: ["Ir iX H VV", "N dd ff", "1sn T T T", "2sn Td Td Td", "4 P P P P", "5 a P P P", "7 ww W1 W2"],
    5: ["8Nh CL CM CH", "333", "0CS DL DM DH", "1sn Tx Tx Tx", "2sn Tn Tn Tn", "3E j j j", "5 EEEjE"],
    7: ["5n Fn Fn Fn", "56DL DM DH", "58/59 P24P24P24", "6 RRR tr", "7R24R24R24R24", "8NsChs hs", "8NsChs hs"],
    9: ["8NsChs hs", "8NsChs hs", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp"],
    11: ["9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp"],
    13: ["9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp"],
    15: ["9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp", "9sp sp sp sp"]
  };

  const meteoPlaceholders = {
    2: ["AAXX", "", "78", ""],
    4: ["", "", "10", "20", "4", "5", "7"],
    6: ["8", "333", "0", "10", "20", "3///", ""],
    8: ["", "56", "5", "6", "7", "8", "8"],
    10: ["8", "8", "9", "9", "9", "9", "9"],
    12: ["9", "9", "9", "9", "9", "9", "9"],
    14: ["9", "9", "9", "9", "9", "9", "9"],
    16: ["9", "9", "9", "9", "9", "9", "9"]
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <h1 className="text-2xl font-bold mb-6 text-gray-800">Formulario de Datos Meteorológicos</h1>

      <div className="flex gap-4 items-start">
        {/* Contenido Principal */}
        <div className="flex-1">
          {/* Tabla Meteorológica */}
          <div className="bg-white rounded-xl shadow-lg p-5 mb-6">
            <div className="grid grid-cols-7 gap-2 mb-3">
              <div className={primaryHeader} style={{ backgroundColor: primaryColor }}>Observador</div>
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
                    {placeholders.slice(0, 3).map((p, i) => (<input key={i} className={inputClass} placeholder={p} value={getValue(`meteo_${row}_${i}`)} onChange={(e) => handleChange(`meteo_${row}_${i}`, e.target.value)} />))}
                    <div className="col-span-4">
                      <input
                        type="date"
                        className={inputClass}
                        value={getValue('fecha')}
                        onChange={(e) => handleChange('fecha', e.target.value)}
                      />
                    </div>
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
          <div className="bg-white rounded-xl shadow-lg p-5">
            <div className="grid grid-cols-7 gap-2 mb-3">
              <div className={`col-span-2 ${primaryHeader}`} style={{ backgroundColor: primaryColor }}>Cálculos de Estación</div>
              <div className={primaryHeader} style={{ backgroundColor: primaryColor }}>Presión de la Estación</div>
              <div className={primaryHeader} style={{ backgroundColor: primaryColor }}>P 3 Horas</div>
              <div className={primaryHeader} style={{ backgroundColor: primaryColor }}>P 24 Horas</div>
              <div className={primaryHeader} style={{ backgroundColor: primaryColor }}>Máx. / Mín.</div>
              <div className={primaryHeader} style={{ backgroundColor: primaryColor }}>Máx. / Mín. (24 H)</div>
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
              <input className={readonlyClass} value={results.punto_rocio || ''} readOnly />
              <input className={inputClass} placeholder="Lectura..." value={getValue('let_barom')} onChange={(e) => handleChange('let_barom', e.target.value)} />
              <input className={inputClass} placeholder="0.0" value={getValue('p3')} onChange={(e) => handleChange('p3', e.target.value)} />
              <input className={inputClass} placeholder="Lectura..." value={getValue('p24')} onChange={(e) => handleChange('p24', e.target.value)} />
              <input className={inputClass} placeholder="°C" value={getValue('t_max')} onChange={(e) => handleChange('t_max', e.target.value)} />
              <input className={inputClass} placeholder="°C" value={getValue('t_max_24h')} onChange={(e) => handleChange('t_max_24h', e.target.value)} />
            </div>

            <div className="grid grid-cols-7 gap-2 mb-1">
              <div className={tableHeader}>Th.</div>
              <input className={inputClass} placeholder="°C" value={getValue('th')} onChange={(e) => handleChange('th', e.target.value)} />
              <div className={tableHeader}>Correc. Temp.</div>
              <div className={tableHeader}>Let.</div>
              <div className={tableHeader}>Let.</div>
              <div className={tableHeader}>T Mín.</div>
              <div className={tableHeader}>T Mín.</div>
            </div>

            <div className="grid grid-cols-7 gap-2 mb-1">
              <div className={tableHeader}>Tv.</div>
              <input className={readonlyClass} value={results.tension_vapor || ''} readOnly />
              <input className={inputClass} placeholder="0.0" value={getValue('correc_temp')} onChange={(e) => handleChange('correc_temp', e.target.value)} />
              <input className={inputClass} placeholder="0.0" value={getValue('p3_let')} onChange={(e) => handleChange('p3_let', e.target.value)} />
              <input className={inputClass} placeholder="0.0" value={getValue('p24_let')} onChange={(e) => handleChange('p24_let', e.target.value)} />
              <input className={inputClass} placeholder="°C" value={getValue('t_min')} onChange={(e) => handleChange('t_min', e.target.value)} />
              <input className={inputClass} placeholder="°C" value={getValue('t_min_24h')} onChange={(e) => handleChange('t_min_24h', e.target.value)} />
            </div>

            <div className="grid grid-cols-7 gap-2 mb-1">
              <div className={tableHeader}>Dif.</div>
              <input className={readonlyClass} value={results.diferencia || ''} readOnly />
              <div className={tableHeader}>Pres. Est.</div>
              <div className={tableHeader}>Dif.</div>
              <div className={tableHeader}>Dif.</div>
              <div className={tableHeader}>LL</div>
              <div className={tableHeader}>LL</div>
            </div>

            <div className="grid grid-cols-7 gap-2 mb-1">
              <div className={tableHeader}>Hr.</div>
              <input className={readonlyClass} value={results.humedad_relativa ? `${results.humedad_relativa}%` : ''} readOnly />
              <input className={inputClass} placeholder="1.6" value={getValue('pres_est')} onChange={(e) => handleChange('pres_est', e.target.value)} />
              <input className={inputClass} placeholder="0.0" value={getValue('p3_dif')} onChange={(e) => handleChange('p3_dif', e.target.value)} />
              <input className={inputClass} placeholder="0.0" value={getValue('p24_dif')} onChange={(e) => handleChange('p24_dif', e.target.value)} />
              <input className={inputClass} placeholder="mm" value={getValue('ll')} onChange={(e) => handleChange('ll', e.target.value)} />
              <input className={inputClass} placeholder="mm" value={getValue('ll_24h')} onChange={(e) => handleChange('ll_24h', e.target.value)} />
            </div>

            <div className="grid grid-cols-7 gap-2 mb-1">
              <div className="col-span-2"></div>
              <div className={tableHeader}>Correc. Alt.</div>
              <div className="col-span-4"></div>
            </div>
            <div className="grid grid-cols-7 gap-2 mb-1">
              <div className="col-span-2"></div>
              <input className={inputClass} placeholder="Corrección..." value={getValue('correc_alt')} onChange={(e) => handleChange('correc_alt', e.target.value)} />
              <div className="col-span-4"></div>
            </div>

            <div className="grid grid-cols-7 gap-2 mb-1">
              <div className="col-span-2"></div>
              <div className={tableHeader}>Pres. NMM</div>
              <div className="col-span-4"></div>
            </div>
            <div className="grid grid-cols-7 gap-2">
              <div className="col-span-2"></div>
              <input className={inputClass} placeholder="1.6" value={getValue('pres_nmm')} onChange={(e) => handleChange('pres_nmm', e.target.value)} />
              <div className="col-span-4"></div>
            </div>
          </div>
        </div>

        {/* Panel de Navegación - Alineado con los datos */}
        <div className="w-36 bg-white rounded-xl shadow-lg p-4">
          <h2 className="text-sm font-bold mb-4 text-center text-gray-700">Observación</h2>

          <div className="space-y-2">
            {hours.map(hora => (
              <button
                key={hora}
                onClick={() => setActiveHour(hora)}
                className={`w-full py-2.5 px-3 rounded-lg font-medium text-sm transition-all ${activeHour === hora
                    ? 'text-white shadow-md'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                style={activeHour === hora ? { backgroundColor: primaryColor } : {}}
              >
                {hora}
              </button>
            ))}
          </div>

          <button
            onClick={handleSave}
            className="w-full py-2.5 px-3 rounded-lg text-white font-bold mt-3 transition-colors shadow-md text-sm"
            style={{ backgroundColor: primaryColor }}
          >
            Guardar
          </button>
        </div>
      </div>
    </div>
  );
};

export default SynopticPage;
