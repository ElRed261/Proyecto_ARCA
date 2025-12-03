import { useState, useEffect } from 'react';
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import AuthPage from './features/auth/pages/AuthPage';
import DashboardPage from './features/dashboard/pages/DashboardPage';
import AdminPage from './features/auth/pages/AdminPage';
import AccountingLayout from './features/accounting/layouts/AccountingLayout';
import ChartOfAccountsPage from './features/accounting/pages/ChartOfAccountsPage';
import JournalEntryPage from './features/accounting/pages/JournalEntryPage';
import GeneralLedgerPage from './features/accounting/pages/GeneralLedgerPage';
import AccountingDashboardPage from './features/accounting/pages/AccountingDashboardPage';
import FiscalPeriodsPage from './features/accounting/pages/FiscalPeriodsPage';
import ReportsPage from './features/accounting/pages/ReportsPage';
import CostCentersPage from './features/accounting/pages/CostCentersPage';

function App() {
  const [user, setUser] = useState(null);
  const navigate = useNavigate();
  const location = useLocation();

  const addLog = (message, type = 'info') => {
    console.log(`[System Log] ${type.toUpperCase()}: ${message}`);
  };

  useEffect(() => {
    const token = localStorage.getItem('token');
    const email = localStorage.getItem('user_email');
    const savedRoles = localStorage.getItem('user_roles');

    if (token && email) {
      const roles = savedRoles ? JSON.parse(savedRoles) : [];
      setUser({ email, roles });
      addLog('Sistema restaurado. Sesión activa detectada.', 'success');
      // Si estamos en root, ir a dashboard
      if (location.pathname === '/') {
        navigate('/dashboard');
      }
    }
  }, []);

  const handleLoginSuccess = (userData) => {
    setUser({ email: userData.user_email, roles: userData.roles || [] });
    addLog(`Autenticación correcta. Bienvenido: ${userData.user_email}`, 'success');
    navigate('/dashboard');
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user_email');
    localStorage.removeItem('user_roles');
    setUser(null);
    navigate('/');
  };

  // Wrapper para proteger rutas
  const ProtectedRoute = ({ children }) => {
    if (!user) {
      return <Navigate to="/" replace />;
    }
    return children;
  };

  return (
    <div className="relative min-h-screen bg-gray-100 font-sans text-gray-800">
      <Routes>
        {/* Login */}
        <Route path="/" element={
          !user ? (
            <AuthPage
              addLog={(msg) => console.log(`[Auth System]: ${msg}`)}
              onLoginSuccess={handleLoginSuccess}
            />
          ) : (
            <Navigate to="/dashboard" replace />
          )
        } />

        {/* Dashboard */}
        <Route path="/dashboard" element={
          <ProtectedRoute>
            <DashboardPage
              user={user}
              onLogout={handleLogout}
              onNavigate={(path) => navigate(`/${path}`)}
            />
          </ProtectedRoute>
        } />

        {/* Admin */}
        <Route path="/admin" element={
          <ProtectedRoute>
            <AdminPage
              onBack={() => navigate('/dashboard')}
              addLog={addLog}
            />
          </ProtectedRoute>
        } />

        {/* Accounting Module */}
        <Route path="/accounting" element={
          <ProtectedRoute>
            <AccountingLayout user={user} onLogout={handleLogout} />
          </ProtectedRoute>
        }>
          <Route index element={<AccountingDashboardPage />} />
          <Route path="accounts" element={<ChartOfAccountsPage />} />
          <Route path="entries" element={<JournalEntryPage addLog={addLog} />} />
          <Route path="ledger" element={<GeneralLedgerPage />} />
          <Route path="periods" element={<FiscalPeriodsPage />} />
          <Route path="cost-centers" element={<CostCentersPage />} />
          <Route path="reports" element={<ReportsPage />} />
        </Route>

        {/* Placeholders for other modules */}
        <Route path="/hrm" element={
          <ProtectedRoute>
            <ModulePlaceholder
              name="Recursos Humanos (HRM)"
              description="Gestión de Nómina, Contratos y Personal."
              onBack={() => navigate('/dashboard')}
            />
          </ProtectedRoute>
        } />
        <Route path="/scm" element={
          <ProtectedRoute>
            <ModulePlaceholder
              name="Cadena de Suministro (SCM)"
              description="Inventario, Bodegas, Proveedores y Compras."
              onBack={() => navigate('/dashboard')}
            />
          </ProtectedRoute>
        } />
        <Route path="/crm" element={
          <ProtectedRoute>
            <ModulePlaceholder
              name="Gestión Comercial (CRM)"
              description="Clientes, Oportunidades y Facturación."
              onBack={() => navigate('/dashboard')}
            />
          </ProtectedRoute>
        } />

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}

const ModulePlaceholder = ({ name, description, onBack }) => (
  <div className="min-h-screen flex flex-col items-center justify-center p-8 bg-gray-50 pb-64 animate-fadeIn">
    <div className="bg-white p-10 rounded-2xl shadow-xl border border-gray-100 max-w-2xl text-center">
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