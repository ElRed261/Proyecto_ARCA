import React from 'react';
import { ArrowRight } from 'lucide-react';

const ModuleCard = ({ title, description, icon: Icon, color, onClick, status = 'active' }) => {
    const isDisabled = status === 'disabled';

    return (
        <div
            onClick={!isDisabled ? onClick : undefined}
            className={`
        relative overflow-hidden rounded-2xl p-6 transition-all duration-300 border
        ${isDisabled
                    ? 'bg-gray-50 border-gray-200 cursor-not-allowed opacity-60 grayscale'
                    : 'bg-white border-gray-100 hover:shadow-xl cursor-pointer hover:-translate-y-1 group'
                }
      `}
        >
            {/* Fondo decorativo con gradiente suave */}
            <div className={`absolute top-0 right-0 -mt-4 -mr-4 w-24 h-24 rounded-full opacity-10 ${color}`}></div>

            <div className="flex items-start justify-between mb-4">
                <div className={`p-3 rounded-lg ${isDisabled ? 'bg-gray-200' : `${color} bg-opacity-10 text-gray-700`}`}>
                    <Icon size={32} className={isDisabled ? 'text-gray-400' : ''} />
                </div>
                {status === 'beta' && (
                    <span className="bg-yellow-100 text-yellow-800 text-xs font-bold px-2 py-1 rounded-full">
                        EN DESARROLLO
                    </span>
                )}
            </div>

            <h3 className="text-xl font-bold text-gray-800 mb-2 group-hover:text-blue-600 transition-colors">
                {title}
            </h3>
            <p className="text-gray-500 text-sm mb-6 leading-relaxed">
                {description}
            </p>

            {!isDisabled && (
                <div className="flex items-center text-sm font-semibold text-blue-600 group-hover:gap-2 transition-all">
                    Acceder al Módulo <ArrowRight size={16} className="ml-1" />
                </div>
            )}
        </div>
    );
};

export default ModuleCard;