import { useState, useEffect } from 'react';
import AuthPage from './features/auth/pages/AuthPage';
import DashboardPage from './features/dashboard/pages/DashboardPage';

function App() {
  // --- ESTADOS GLOBALES DEL SISTEMA ---
  const [user, setUser] = useState(null);
  const [currentModule, setCurrentModule] = useState('dashboard'); // 'dashboard', 'hrm', 'scm', etc.

  // --- FUNCIÓN CENTRAL DE LOGS ---
  // Permite que cualquier parte de la app escriba en la terminal negra inferior
  const addLog = (message, type = 'info') => {
    console.log(`[System Log] ${type.toUpperCase()}: ${message}`);
  };

  // --- EFECTO DE PERSISTENCIA ---
  // Al iniciar, revisamos si hay una sesión guardada en el navegador
  useEffect(() => {
    const token = localStorage.getItem('token');
    const email = localStorage.getItem('user_email');

    if (token && email) {
      setUser({ email });
      addLog('Sistema restaurado. Sesión activa detectada.', 'success');
    }
  }, []);

  // --- MANEJADORES (HANDLERS) ---

  const handleLoginSuccess = (userData) => {
    setUser({ email: userData.user_email });
    // Este log aparecerá apenas cargue el Dashboard
    addLog(`Autenticación correcta. Bienvenido: ${userData.user_email}`, 'success');
    addLog('Inicializando módulos del núcleo empresarial...', 'info');
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user_email');
    setUser(null);
    setCurrentModule('dashboard');
    setCurrentModule('dashboard');
  };

  const handleNavigate = (moduleId) => {
    setCurrentModule(moduleId);
    addLog(`Navegando al módulo: ${moduleId.toUpperCase()}`, 'info');
  };

  return (
    <div className="relative min-h-screen bg-gray-100 font-sans text-gray-800">

      {/* 1. ESTADO: NO AUTENTICADO (Muestra Login limpio) */}
      {!user ? (
        <AuthPage
          // Pasamos una función vacía o console.log a addLog para que 
          // la pantalla de login no intente escribir en la terminal visual (que está oculta)
          addLog={(msg) => console.log(`[Auth System]: ${msg}`)}
          onLoginSuccess={handleLoginSuccess}
        />
      ) : (
        /* 2. ESTADO: AUTENTICADO (Muestra Sistema Completo) */
        <>
          {/* A. ENRUTADOR DE VISTAS */}

          {/* Vista 1: Dashboard Principal */}
          {currentModule === 'dashboard' && (
            <DashboardPage
              user={user}
              onLogout={handleLogout}
              onNavigate={handleNavigate}
            />
          )}

          {/* Vista 2: Recursos Humanos */}
          {currentModule === 'hrm' && (
            <ModulePlaceholder
              name="Recursos Humanos (HRM)"
              description="Gestión de Nómina, Contratos y Personal."
              onBack={() => setCurrentModule('dashboard')}
            />
          )}

          {/* Vista 3: Cadena de Suministro */}
          {currentModule === 'scm' && (
            <ModulePlaceholder
              name="Cadena de Suministro (SCM)"
              description="Inventario, Bodegas, Proveedores y Compras."
              onBack={() => setCurrentModule('dashboard')}
            />
          )}

          {/* Vista 4: CRM */}
          {currentModule === 'crm' && (
            <ModulePlaceholder
              name="Gestión Comercial (CRM)"
              description="Clientes, Oportunidades y Facturación."
              onBack={() => setCurrentModule('dashboard')}
            />
          )}

          {/* Vista 5: Admin */}
          {currentModule === 'admin' && (
            <ModulePlaceholder
              name="Seguridad y Auditoría"
              description="Configuración de Roles, Usuarios y Permisos."
              onBack={() => setCurrentModule('dashboard')}
            />
          )}


        </>
      )}

    </div>
  );
}

// --- COMPONENTE AUXILIAR (Placeholder Visual) ---
// Se muestra cuando entras a un módulo que existe en BD pero no tiene Frontend aún.
const ModulePlaceholder = ({ name, description, onBack }) => (
  <div className="min-h-screen flex flex-col items-center justify-center p-8 bg-gray-50 pb-64 animate-fadeIn">
    <div className="bg-white p-10 rounded-2xl shadow-xl border border-gray-100 max-w-2xl text-center">
      {/* Icono de construcción */}
      <div className="mb-6 inline-flex p-4 rounded-full bg-blue-50 text-blue-600">
        <svg className="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" /></svg>
      </div>

      <h1 className="text-3xl font-bold text-gray-800 mb-2">{name}</h1>
      <h2 className="text-xl text-blue-600 mb-6 font-medium">{description}</h2>

      <p className="text-gray-500 mb-8 leading-relaxed">
        Este módulo está conectado a nivel de base de datos y backend,
        pero su interfaz gráfica está actualmente en desarrollo por el equipo de ingeniería.
      </p>

      <button
        onClick={onBack}
        className="px-8 py-3 bg-gray-900 text-white rounded-lg hover:bg-gray-800 transition shadow-lg font-semibold flex items-center justify-center mx-auto gap-2"
      >
        <span>←</span> Volver al Panel Principal
      </button>
    </div>
  </div>
);

export default App;