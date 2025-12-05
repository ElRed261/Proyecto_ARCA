import React from 'react';
import { useNavigate } from 'react-router-dom';

const MaintenancePage = () => {
    const navigate = useNavigate();

    return (
        <div className="min-h-screen bg-gradient-to-br from-amber-50 to-amber-100 p-6 flex flex-col items-center justify-center">
            <div className="bg-white rounded-xl shadow-lg p-8 max-w-md text-center">
                <div className="text-6xl mb-4">🔧</div>
                <h1 className="text-2xl font-bold text-amber-700 mb-4">Página en Mantenimiento</h1>
                <p className="text-gray-600 mb-6">
                    Esta función está en desarrollo y estará disponible próximamente.
                </p>
                <p className="text-sm text-gray-500 mb-6">
                    Los módulos 3074, 4074 y 5074 se implementarán en futuras actualizaciones.
                </p>
                <button
                    onClick={() => navigate('/synoptic')}
                    className="px-6 py-3 bg-amber-600 text-white font-bold rounded-lg hover:bg-amber-700 transition-colors"
                >
                    Volver al Formulario
                </button>
            </div>
        </div>
    );
};

export default MaintenancePage;
