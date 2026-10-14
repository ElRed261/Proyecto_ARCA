import React, { useState } from 'react';
import { User, LogOut, ChevronDown } from 'lucide-react';

const UserMenu = ({ user, onLogout }) => {
    const [isOpen, setIsOpen] = useState(false);
    const [showDetails, setShowDetails] = useState(false);

    // Si no hay usuario, no mostrar nada
    if (!user) return null;

    return (
        <div
            className="relative z-50"
            onMouseEnter={() => setShowDetails(true)}
            onMouseLeave={() => setShowDetails(false)}
        >
            {/* Avatar / Icono */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center gap-2 p-2 rounded-full hover:bg-gray-100 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
                <div className="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center text-white shadow-md">
                    <User size={20} />
                </div>
                {/* Indicador visual de menú */}
                <ChevronDown size={14} className={`text-gray-500 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
            </button>

            {/* Tooltip / Datos Simples (Hover) */}
            {showDetails && !isOpen && (
                <div className="absolute top-14 right-0 bg-gray-800 text-white text-sm py-2 px-4 rounded-lg shadow-xl whitespace-nowrap animate-fadeIn">
                    <p className="font-bold">{user.email}</p>
                    <p className="text-xs text-gray-300 capitalize">
                        {user.roles && user.roles.length > 0 ? user.roles.join(', ') : 'Usuario'}
                    </p>
                </div>
            )}

            {/* Menú Desplegable (Click) */}
            {isOpen && (
                <div className="absolute top-14 right-0 w-64 bg-white rounded-xl shadow-2xl border border-gray-100 overflow-hidden animate-fadeIn">
                    {/* Header del menú */}
                    <div className="p-4 bg-gray-50 border-b border-gray-100">
                        <p className="text-sm font-bold text-gray-800 truncate">{user.email}</p>
                        <p className="text-xs text-gray-500 mt-1">
                            Rol: <span className="capitalize font-medium text-blue-600">{user.roles ? user.roles[0] : 'N/A'}</span>
                        </p>
                    </div>

                    {/* Opciones */}
                    <div className="p-2">
                        <button
                            onClick={() => {
                                setIsOpen(false);
                                onLogout();
                            }}
                            className="w-full flex items-center gap-3 px-4 py-3 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                        >
                            <LogOut size={18} />
                            <span>Cerrar Sesión</span>
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default UserMenu;
