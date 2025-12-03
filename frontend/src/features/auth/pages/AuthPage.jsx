import React, { useState } from 'react';
import { authService } from '../api/authService';
import { Shield, UserPlus, LogIn, Server } from 'lucide-react';
import loginBg from '../../../assets/login-bg.png';

const AuthPage = ({ addLog, onLoginSuccess }) => {
    const [isLogin, setIsLogin] = useState(true); // Switch entre Login y Registro
    const [formData, setFormData] = useState({ email: '', password: '' });
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        const action = isLogin ? 'Iniciando Sesión' : 'Registrando Usuario';

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
            addLog(`Error Crítico: ${errorMsg}`, 'error');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div
            className="min-h-screen bg-gray-900 flex items-center justify-center pb-48 relative"
            style={{
                backgroundImage: `url(${loginBg})`,
                backgroundSize: 'cover',
                backgroundPosition: 'center'
            }}
        >
            {/* Overlay para oscurecer el fondo y dar legibilidad */}
            <div className="absolute inset-0 bg-black/40 backdrop-blur-sm"></div>

            <div className="bg-white/95 backdrop-blur-md p-8 rounded-xl shadow-2xl w-full max-w-md border border-white/20 relative z-10">

                {/* Cabecera */}
                <div className="text-center mb-8">
                    <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-100 text-blue-600 rounded-full mb-4">
                        <Shield size={32} />
                    </div>
                    <h1 className="text-2xl font-bold text-gray-800">Proyecto ARCA</h1>
                    <p className="text-gray-500 text-sm">Acceso al Sistema ERP</p>
                </div>

                {/* Tabs */}
                <div className="flex mb-6 bg-gray-100 p-1 rounded-lg">
                    <button
                        onClick={() => setIsLogin(true)}
                        className={`flex-1 py-2 text-sm font-medium rounded-md transition-all ${isLogin ? 'bg-white shadow text-blue-600' : 'text-gray-500 hover:text-gray-700'}`}
                    >
                        Iniciar Sesión
                    </button>
                    <button
                        onClick={() => setIsLogin(false)}
                        className={`flex-1 py-2 text-sm font-medium rounded-md transition-all ${!isLogin ? 'bg-white shadow text-blue-600' : 'text-gray-500 hover:text-gray-700'}`}
                    >
                        Registrarse
                    </button>
                </div>

                {/* Formulario */}
                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Correo Electrónico</label>
                        <input
                            type="email"
                            required
                            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition"
                            placeholder="admin@arca.com"
                            value={formData.email}
                            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Contraseña</label>
                        <input
                            type="password"
                            required
                            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition"
                            placeholder="••••••"
                            value={formData.password}
                            onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                        />
                    </div>

                    <button
                        type="submit"
                        disabled={loading}
                        className={`w-full py-3 rounded-lg text-white font-bold shadow-lg transition transform active:scale-95 flex items-center justify-center gap-2
              ${loading ? 'bg-gray-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700'}`}
                    >
                        {loading ? (
                            <span className="animate-pulse">Procesando...</span>
                        ) : (
                            <>
                                {isLogin ? <LogIn size={18} /> : <UserPlus size={18} />}
                                {isLogin ? 'Entrar al Sistema' : 'Crear Cuenta'}
                            </>
                        )}
                    </button>
                </form>

                {/* Footer info */}
                <div className="mt-6 text-center text-xs text-gray-400 flex items-center justify-center gap-1">
                    <Server size={12} />
                    <span>Conectado a Backend v1.0.0</span>
                </div>
            </div>
        </div>
    );
};

export default AuthPage;