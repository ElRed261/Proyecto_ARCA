import React from 'react';
import { ArrowRight } from 'lucide-react';

// eslint-disable-next-line no-unused-vars
const ModuleCard = ({ title, description, icon: Icon, color, onClick, status = 'active' }) => {
    const isDisabled = status === 'disabled';

    return (
        <button
            onClick={onClick}
            disabled={isDisabled}
            className={`
                text-left w-full relative overflow-hidden rounded-2xl p-6 border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-blue-500 transition-all duration-500
                ${isDisabled
                    ? 'bg-slate-50/50 border-slate-200 cursor-not-allowed opacity-60 grayscale'
                    : 'bg-white border-slate-100 hover:border-slate-200/80 hover:shadow-[0_20px_50px_-12px_rgba(0,0,0,0.06)] cursor-pointer hover:-translate-y-1.5 group'
                }
            `}
        >
            {/* Fondo decorativo con gradiente difuminado blur */}
            {!isDisabled && (
                <div className={`absolute -top-6 -right-6 w-32 h-32 rounded-full filter blur-xl opacity-20 bg-current transition-all duration-500 group-hover:scale-125 group-hover:opacity-30 ${color.split(' ')[0]}`}></div>
            )}

            <div className="flex items-start justify-between mb-4">
                <div className={`p-3 rounded-xl transition-all duration-500 ${isDisabled ? 'bg-slate-200' : `${color} bg-opacity-10 text-slate-700 group-hover:text-white group-hover:bg-opacity-100 group-hover:scale-110 shadow-sm`}`}>
                    <Icon size={28} className={isDisabled ? 'text-slate-400' : 'transition-transform duration-500'} />
                </div>
                {status === 'beta' && (
                    <span className="bg-yellow-100 text-yellow-800 text-xs font-bold px-2.5 py-1 rounded-full shadow-inner">
                        EN DESARROLLO
                    </span>
                )}
            </div>

            <h3 className="text-xl font-bold text-slate-800 mb-2 group-hover:text-slate-900 transition-colors">
                {title}
            </h3>
            <p className="text-slate-500 text-sm mb-6 leading-relaxed">
                {description}
            </p>

            {!isDisabled && (
                <div className={`flex items-center text-sm font-bold transition-all duration-300 ${color.split(' ')[1] || 'text-blue-600'} group-hover:translate-x-1`}>
                    Acceder al Módulo <ArrowRight size={16} className="ml-1 transition-transform duration-300 group-hover:translate-x-1" />
                </div>
            )}
        </button>
    );
};

export default ModuleCard;