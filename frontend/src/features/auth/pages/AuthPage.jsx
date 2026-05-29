import React, { useState } from 'react';
import { authService } from '../api/authService';
import { Shield, LogIn, Lock, UserPlus } from 'lucide-react';
import loginBg from '../../../assets/login-bg.png';

import Logo from '../../../shared/components/Logo';

const AuthPage = ({ addLog, onLoginSuccess }) => {
    const [isLogin, setIsLogin] = useState(true); // Switch entre Login y Registro
    const [formData, setFormData] = useState({ email: '', password: '' });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError(null);
        // Log inicial
        addLog(`Enviando petición POST a ${isLogin ? '/api/auth/login' : '/api/auth/register'}...`, 'info');

        try {
            if (isLogin) {
                const data = await authService.login(formData.email, formData.password);
                addLog(`Éxito: Token recibido [${data.access_token.substring(0, 15)}...]`, 'success');
                addLog(`Usuario autenticado: ${data.user_email}`, 'success');
                onLoginSuccess(data); // Notificar al App.jsx que entramos
            } else {
                const data = await authService.register(formData.email, formData.password);
                addLog(`Registro exitoso. ID Usuario: ${data.id}`, 'success');
                setIsLogin(true); // Cambiar a login automáticamente
            }
        } catch (error) {
            console.error(error);
            const errorMsg = error.response?.data?.detail || "Error de conexión con el servidor";
            setError(errorMsg);
            addLog(`Error Crítico: ${errorMsg}`, 'error');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div
            className="min-h-screen bg-gray-900 flex items-center justify-center relative"
            style={{
                backgroundImage: `url(${loginBg})`,
                backgroundSize: 'cover',
                backgroundPosition: 'center'
            }}
        >
            {/* Overlay para oscurecer el fondo y dar legibilidad */}
            <div className="absolute inset-0 bg-black/40 backdrop-blur-sm"></div>

            <div className="bg-white/85 backdrop-blur-xl p-8 rounded-2xl shadow-[0_24px_60px_-15px_rgba(0,0,0,0.25)] w-full max-w-md border border-white/40 relative z-10">

                {/* Cabecera */}
                <div className="text-center mb-8 flex flex-col items-center">
                    <div className="mb-4 transform scale-150">
                        <Logo variant="full" />
                    </div>
                    <p className="text-slate-500 text-sm mt-2">Acceso al Sistema ERP</p>
                </div>

                {/* Mensaje de Error */}
                {error && (
                    <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg flex items-center justify-center animate-shake">
                        {error}
                    </div>
                )}

                {/* Formulario */}
                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm font-semibold text-slate-700 mb-1">Correo Electrónico</label>
                        <input
                            type="email"
                            required
                            className="w-full px-4 py-2 border border-slate-200 bg-white/70 rounded-lg focus:ring-4 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all duration-300 placeholder:text-slate-400"
                            placeholder="test@arca.com"
                            value={formData.email}
                            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-semibold text-slate-700 mb-1">Contraseña</label>
                        <input
                            type="password"
                            required
                            className="w-full px-4 py-2 border border-slate-200 bg-white/70 rounded-lg focus:ring-4 focus:ring-blue-500/20 focus:border-blue-500 outline-none transition-all duration-300 placeholder:text-slate-400"
                            placeholder="••••••"
                            value={formData.password}
                            onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                        />
                    </div>

                    <button
                        type="submit"
                        disabled={loading}
                        className={`w-full py-3 rounded-lg text-white font-bold shadow-md hover:shadow-lg transition-all duration-300 active:scale-[0.98] flex items-center justify-center gap-2 cursor-pointer
              ${loading ? 'bg-slate-400 cursor-not-allowed shadow-none' : isLogin ? 'bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700' : 'bg-gradient-to-r from-purple-600 to-violet-600 hover:from-purple-700 hover:to-violet-700'}`}
                    >
                        {loading ? (
                            <span className="animate-pulse">Procesando...</span>
                        ) : (
                            <>
                                {isLogin ? <LogIn size={18} /> : <UserPlus size={18} />}
                                {isLogin ? 'Iniciar Sesión' : 'Crear Cuenta'}
                            </>
                        )}
                    </button>
                </form>

                {/* Registro deshabilitado en modo local */}

                {/* Footer info */}
                <div className="mt-6 text-center text-xs text-slate-400 flex items-center justify-center gap-1">
                    <Lock size={12} />
                    <span>Modo Local — Autenticación Offline</span>
                </div>
            </div>
        </div>
    );
};

export default AuthPage;