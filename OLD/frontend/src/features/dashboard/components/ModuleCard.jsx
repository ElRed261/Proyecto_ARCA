import React, { useState } from 'react';
import { ArrowRight } from 'lucide-react';

/*
 * ModuleCard — mosaico del Dashboard.
 * · accent: hex del módulo (Synoptic azul, correcciones naranja, resumen
 *   violeta, config teal, admin pizarra). Al hover, la tarjeta BRILLA con
 *   el color de su propio módulo (glow) y el borde se tiñe — coherencia
 *   visual color↔destino (skill ui-ux-pro-max: states & variants).
 */
// eslint-disable-next-line no-unused-vars
const ModuleCard = ({ title, description, icon: Icon, color = 'bg-blue-500 text-blue-600', accent = '#3b82f6', onClick, status = 'active' }) => {
    const isDisabled = status === 'disabled';
    const [hovered, setHovered] = useState(false);

    const glowStyle = isDisabled
        ? undefined
        : hovered
          ? {
                borderColor: `${accent}66`,
                boxShadow: `0 12px 40px -8px ${accent}59, 0 0 0 1px ${accent}33, 0 4px 16px ${accent}26`,
            }
          : undefined;

    return (
        <button
            onClick={onClick}
            disabled={isDisabled}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            aria-label={`Abrir módulo: ${title}`}
            style={glowStyle}
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
                <div className="absolute -top-6 -right-6 w-32 h-32 rounded-full filter blur-xl opacity-40 transition-all duration-500 group-hover:scale-125 group-hover:opacity-70" style={{ background: `radial-gradient(circle, ${accent}66 0%, ${accent}00 70%)` }}></div>
            )}

            <div className="flex items-start justify-between mb-4">
                <div className={`p-3 rounded-xl transition-all duration-500 ${isDisabled ? 'bg-slate-200' : `${color} bg-opacity-10 text-slate-700 group-hover:text-white group-hover:scale-110 shadow-sm`}
                                    style={{ background: accent }}`}>
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