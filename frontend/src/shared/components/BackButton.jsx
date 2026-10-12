import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

/**
 * BackButton — botón de volver CONSISTENTE para toda la app.
 *
 * Regla de diseño (skill ui-ux-pro-max, prioridad 1/2/9):
 * - Navegación predecible: mismo componente, misma posición, mismo look en
 *   todas las páginas (no más flecha sola vs texto solo vs ← literal).
 * - Accesible: aria-label explícito siempre (icono + texto).
 * - Target táctil ≥44px.
 *
 * Props:
 *  - to: ruta destino (usa navigate). Requerido si no hay onClick.
 *  - onBack: alternativa con lógica propia de la página (ej: ir 1 nivel atrás).
 *  - label: texto del aria-label/title (default 'Volver').
 */
const BackButton = ({ to, onBack, label = 'Volver' }) => {
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
            className="min-h-[44px] min-w-[44px] px-3 py-2 rounded-full bg-white border border-slate-200 shadow-sm transition-all
                       hover:bg-slate-50 hover:shadow-md cursor-pointer flex items-center justify-center gap-1.5
                       text-slate-600 hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 font-medium text-sm"
        >
            <ArrowLeft className="w-5 h-5" />
            <span className="hidden sm:inline">Volver</span>
        </button>
    );
};

export default BackButton;
