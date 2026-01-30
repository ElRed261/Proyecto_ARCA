/**
 * Panel de navegación lateral para el formulario sinóptico
 * - Selector de horas
 * - Navegación entre días
 * - Botones CLI
 * - Campos extra 8NsChshs
 * - Botones Cargar/Guardar
 */
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { isAdmin } from '../../../shared/utils/auth';
import { styles } from '../config/synopticConfig';

const SynopticSidebar = ({
    hours,
    activeHour,
    currentTheme,
    onHourChange,
    onPreviousDay,
    onNextDay,
    onSave,
    onLoadJson,
    getValue,
    handleChange,
    handleKeyDown
}) => {
    const navigate = useNavigate();
    const { tableHeader, inputClass } = styles;

    return (
        <div className="w-36 bg-white rounded-xl shadow-lg p-4 transition-all duration-500">
            <h2 className="text-sm font-bold mb-4 text-center text-gray-700">Observación</h2>

            {/* Selector de Horas */}
            <div className="space-y-2">
                {hours.map(hora => (
                    <button
                        key={hora}
                        onClick={() => onHourChange(hora)}
                        className={`w-full py-2.5 px-3 rounded-lg font-medium text-sm transition-all duration-300 ${activeHour === hora
                                ? 'text-white shadow-md scale-105'
                                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                            }`}
                        style={activeHour === hora ? { backgroundColor: currentTheme.accentColor } : {}}
                    >
                        {hora}
                    </button>
                ))}

                {/* Navegación entre días */}
                <div className="flex gap-1 mt-3">
                    <button
                        onClick={onPreviousDay}
                        className="flex-1 py-2 px-2 rounded-lg font-medium text-xs bg-blue-100 text-blue-700 hover:bg-blue-200 transition-all duration-300 flex items-center justify-center gap-1"
                        title="Guardar y cargar día anterior"
                    >
                        <span>←</span>
                        <span>Ant.</span>
                    </button>
                    <button
                        onClick={onNextDay}
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
                    {['3074', '4074', '5074'].map(code => (
                        <button
                            key={code}
                            onClick={() => navigate('/maintenance')}
                            className="w-full py-2 px-3 rounded-lg font-medium text-xs bg-amber-100 text-amber-700 hover:bg-amber-200 transition-colors"
                        >
                            {code}
                        </button>
                    ))}
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

            {/* Botones Cargar/Guardar */}
            <div className="mt-4 pt-3 border-t border-gray-200 space-y-2">
                {isAdmin() && (
                    <label className="w-full py-2 px-3 rounded-lg font-bold text-xs bg-blue-100 text-blue-700 hover:bg-blue-200 cursor-pointer transition-colors flex items-center justify-center gap-2">
                        📂 Cargar JSON
                        <input
                            type="file"
                            accept=".json"
                            className="hidden"
                            onChange={onLoadJson}
                        />
                    </label>
                )}
                <button
                    onClick={onSave}
                    className="w-full py-2 px-3 rounded-lg text-white font-bold text-sm transition-all shadow-md hover:opacity-90"
                    style={{ backgroundColor: currentTheme.accentColor }}
                >
                    💾 Guardar
                </button>
            </div>
        </div>
    );
};

export default SynopticSidebar;
