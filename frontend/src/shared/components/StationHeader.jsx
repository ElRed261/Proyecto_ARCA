import React from 'react';

const themeClasses = {
  sky: {
    border: 'border-t-sky-500',
    ring: 'focus:ring-sky-500'
  },
  emerald: {
    border: 'border-t-emerald-500',
    ring: 'focus:ring-emerald-500'
  },
  rose: {
    border: 'border-t-rose-500',
    ring: 'focus:ring-rose-500'
  }
};

const StationHeader = ({
  selectedStation,
  setSelectedStation,
  date,
  setDate,
  stations = {},
  colorTheme = 'sky'
}) => {
  const stInfo = selectedStation && stations[selectedStation] ? stations[selectedStation] : null;
  const theme = themeClasses[colorTheme] || themeClasses.sky;

  return (
    <div className={`mx-6 mb-4 p-4 bg-white border border-slate-200 border-t-4 ${theme.border} shadow-sm rounded-lg z-10 max-w-full overflow-x-auto`}>
      <div className="flex flex-wrap items-center gap-x-8 gap-y-4">
        <div className="flex items-center gap-2">
          <label className="text-sm font-bold text-slate-700 uppercase">Estación:</label>
          <select 
            value={selectedStation} 
            onChange={(e) => setSelectedStation(e.target.value)}
            className={`bg-slate-50 border border-slate-300 text-slate-800 text-sm rounded-md px-3 py-1.5 focus:ring-2 ${theme.ring} focus:outline-none`}
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
            className={`bg-slate-50 border border-slate-300 text-slate-800 text-sm rounded-md px-3 py-1.5 focus:ring-2 ${theme.ring} focus:outline-none`}
          />
        </div>
      </div>
    </div>
  );
};

export default StationHeader;
