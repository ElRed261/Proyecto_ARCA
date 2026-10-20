import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

/**
 * BackButton — botón de volver CONSISTENTE: de la app.
 *
 * Reglas (decisión del autor + skill ui-ux-pro-max):
 * - SIEMPRE en la esquina superior izquierda de la página.
 * - Icono de flecha SOLO (sin texto): la flecha es universal.
 * - Toma el color principal del módulo (`accent`): Synoptic azul,
 *   correcciones naranja, resumen violeta, configuración teal, etc.
 * - aria-label/tag accesible, target táctil ≥44px.
 *
 * Props:
 *  - to: ruta destino (usa navigate). Requerido si no hay onClick.
 *  - onBack: alternativa con lógica propia de la página.
 *  - label: texto del aria-label/title (default 'Volver').
 *  - accent: hex del color principal del módulo.
 */
const BackButton = ({ to, onBack, label = 'Volver', accent = '#64748b' }) => {
    const navigate = useNavigate();
    const handleClick = () => {
        if (onBack) onBack();
        else if (to) navigate(to);
    };

    return (
        <button
            type="button"
            onClick={handleClick}
            aria-label={label}
            title={label}
            style={{ color: accent, borderColor: `${accent}55` }}
            className="min-h-[44px] min-w-[44px] w-11 h-11 rounded-full bg-white border shadow-sm transition-colors
                       hover:border-slate-300 cursor-pointer flex items-center justify-center
                       focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        >
            <ArrowLeft className="w-5 h-5" />
        </button>
    );
};

export default BackButton;
