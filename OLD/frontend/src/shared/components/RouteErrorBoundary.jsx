import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AlertTriangle, RotateCw, Home } from 'lucide-react';

/**
 * RouteErrorBoundary — frontera de error POR RUTA.
 *
 * Antes: un único ErrorBoundary global envolvía toda la App; un render error
 * en cualquier página dejaba toda la navegación muerta ("Recargar" como única
 * salida). Componente de skill ui-ux-pro-max: graceful degradation — el error
 * se confina a la sección y el resto del app sigue vivo.
 *
 * El key (ruta actual) provoca reset automático al navegar a otra sección.
 */
function RouteErrorBoundary({ children }) {
    const location = useLocation();
    const navigate = useNavigate();

    return (
        <RouteErrorBoundaryClass key={location.pathname} navigate={navigate}>
            {children}
        </RouteErrorBoundaryClass>
    );
}

class RouteErrorBoundaryClass extends React.Component {
    constructor(props) {
        super(props);
        this.state = { error: null };
    }

    static getDerivedStateFromError(error) {
        return { error };
    }

    componentDidCatch(error) {
        console.error('[RouteErrorBoundary]', this.props.location?.pathname, error);
    }

    render() {
        if (this.state.error) {
            return (
                <div className="min-h-screen bg-slate-900 flex items-center justify-center p-6">
                    <div className="bg-slate-800/80 border border-slate-700 rounded-2xl p-8 max-w-lg text-center">
                        <div className="w-20 h-20 rounded-full bg-red-500/10 border-2 border-red-500/40 flex items-center justify-center mx-auto mb-5">
                            <AlertTriangle className="w-10 h-10 text-red-500" />
                        </div>
                        <h1 className="text-xl font-bold text-white mb-2">Esta sección falló</h1>
                        <p className="text-slate-400 text-sm mb-3">
                            El error se confinó a este módulo: el resto del sistema sigue
                            funcionando. No se perdió ningún dato local.
                        </p>
                        <code className="block bg-slate-900 text-red-400 text-xs px-4 py-2.5 rounded-lg mb-5 overflow-auto max-h-24 text-left">
                            {String(this.state.error?.message || this.state.error)}
                        </code>
                        <div className="flex items-center justify-center gap-3">
                            <button
                                type="button"
                                onClick={() => this.setState({ error: null })}
                                className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-blue-600 text-white text-sm font-bold hover:bg-blue-500 cursor-pointer min-h-[44px]"
                            >
                                <RotateCw className="w-4 h-4" />
                                Reintentar
                            </button>
                            <button
                                type="button"
                                onClick={() => this.props.navigate('/dashboard')}
                                className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-slate-700 text-slate-200 text-sm font-bold hover:bg-slate-600 cursor-pointer min-h-[44px]"
                            >
                                <Home className="w-4 h-4" />
                                Ir al Dashboard
                            </button>
                        </div>
                    </div>
                </div>
            );
        }
        return this.props.children;
    }
}

export default RouteErrorBoundary;
