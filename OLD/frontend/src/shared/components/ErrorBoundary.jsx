import React from 'react';
import { ShieldAlert, RefreshCw, Home } from 'lucide-react';

class ErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        console.error("ErrorBoundary caught an error:", error, errorInfo);
    }

    handleReload = () => {
        window.location.reload();
    };

    handleReset = () => {
        this.setState({ hasError: false, error: null });
        window.location.hash = '#/dashboard';
    };

    render() {
        if (this.state.hasError) {
            return (
                <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col items-center justify-center p-6 select-none">
                    <div className="max-w-md w-full bg-slate-800/80 backdrop-blur-md border border-slate-700 p-8 rounded-2xl shadow-2xl text-center space-y-6">
                        <div className="w-16 h-16 bg-red-950/50 border border-red-500 rounded-full flex items-center justify-center text-red-500 mx-auto animate-pulse">
                            <ShieldAlert size={36} />
                        </div>

                        <div className="space-y-2">
                            <h2 className="text-xl font-bold text-white">Oops, algo salió mal</h2>
                            <p className="text-sm text-slate-400">
                                Ocurrió un error inesperado en la interfaz. No te preocupes, tus datos locales no se han perdido.
                            </p>
                        </div>

                        {this.state.error && (
                            <div className="bg-slate-950/60 border border-slate-800 p-3 rounded-lg text-xs font-mono text-red-400 overflow-x-auto text-left max-h-32">
                                {this.state.error.toString()}
                            </div>
                        )}

                        <div className="flex gap-4">
                            <button
                                onClick={this.handleReload}
                                className="flex-1 flex items-center justify-center gap-2 py-3 px-4 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-xl transition shadow-lg shadow-blue-950 active:scale-95 text-sm"
                            >
                                <RefreshCw size={16} />
                                Recargar
                            </button>
                            <button
                                onClick={this.handleReset}
                                className="flex-1 flex items-center justify-center gap-2 py-3 px-4 bg-slate-700 hover:bg-slate-600 text-slate-200 font-semibold rounded-xl transition border border-slate-600 active:scale-95 text-sm"
                            >
                                <Home size={16} />
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

export default ErrorBoundary;
