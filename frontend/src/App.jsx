import { useState, useEffect, lazy, Suspense } from 'react';
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { ArrowLeft } from 'lucide-react';
const AuthPage = lazy(() => import('./features/auth/pages/AuthPage'));
const DashboardPage = lazy(() => import('./features/dashboard/pages/DashboardPage'));
const AdminPage = lazy(() => import('./features/auth/pages/AdminPage'));
const SynopticPage = lazy(() => import('./features/synoptic/pages/SynopticPage'));
const SummaryPage = lazy(() => import('./features/summary/pages/SummaryPage'));
const AuditPage = lazy(() => import('./features/audit/pages/AuditPage'));
const AuditObservationPage = lazy(() => import('./features/audit/pages/AuditObservationPage'));
const AuditReportPage = lazy(() => import('./features/audit/pages/AuditReportPage'));
const MaintenancePage = lazy(() => import('./features/maintenance/pages/MaintenancePage'));
const Cli3074Page = lazy(() => import('./features/synoptic/cli3074/pages/Cli3074Page'));
const Cli4074Page = lazy(() => import('./features/synoptic/cli4074/pages/Cli4074Page'));
const Cli5074Page = lazy(() => import('./features/synoptic/cli5074/pages/Cli5074Page'));
import { normalizeRoles, hasRole } from './shared/utils/auth';
import { authService } from './features/auth/api/authService';

const ProtectedRoute = ({ user, children }) => {
  if (!user) {
    return <Navigate to="/" replace />;
  }
  return children;
};

const RoleRoute = ({ user, roles, children }) => {
  if (!user) {
    return <Navigate to="/" replace />;
  }
  if (!hasRole(user.roles, roles)) {
    return <Navigate to="/dashboard" replace />;
  }
  return children;
};

function App() {
  const [user, setUser] = useState(null);
  const navigate = useNavigate();
  const location = useLocation();

  const addLog = (message, type = 'info') => {
    console.log(`[System Log] ${type.toUpperCase()}: ${message}`);
  };

  useEffect(() => {
    const restoreSession = async () => {
      const token = localStorage.getItem('token');
      const email = localStorage.getItem('user_email');
      const savedRoles = localStorage.getItem('user_roles');

      if (token && email) {
        // Validar token contra el backend (SessionStore en memoria)
        const isValid = await authService.validateToken();
        if (isValid) {
          const roles = normalizeRoles(savedRoles);
          // eslint-disable-next-line react-hooks/set-state-in-effect
          setUser({ email, roles });
          addLog('Sistema restaurado. Sesión activa detectada.', 'success');
          if (location.pathname === '/') {
            navigate('/dashboard');
          }
        } else {
          // Sesión fantasma: el token ya no es válido en el backend
          localStorage.removeItem('token');
          localStorage.removeItem('user_email');
          localStorage.removeItem('user_roles');
          addLog('Sesión expirada o inválida. Por favor, inicie sesión nuevamente.', 'warning');
        }
      }
    };
    restoreSession();
  }, []);

  const handleLoginSuccess = (userData) => {
    const roles = normalizeRoles(userData.roles);
    setUser({ email: userData.user_email, roles });
    addLog(`Autenticación correcta. Bienvenido: ${userData.user_email}`, 'success');
    navigate('/dashboard');
  };

  const handleLogout = async () => {
    await authService.logout();
    setUser(null);
    navigate('/');
  };

  return (
    <div className="relative min-h-screen bg-gray-100 font-sans text-gray-800">
      <Toaster position="top-right" />
      <Suspense fallback={<div className="flex items-center justify-center min-h-screen"><span className="text-gray-500">Cargando...</span></div>}>
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
          <ProtectedRoute user={user}>
            <DashboardPage
              user={user}
              onLogout={handleLogout}
              onNavigate={(path) => navigate(`/${path}`)}
            />
          </ProtectedRoute>
        } />

        {/* Admin */}
        <Route path="/admin" element={
          <RoleRoute user={user} roles={['admin']}>
            <AdminPage
              onBack={() => navigate('/dashboard')}
              addLog={addLog}
            />
          </RoleRoute>
        } />

        {/* Synoptic Module */}
        <Route path="/synoptic" element={
          <ProtectedRoute user={user}>
            <SynopticPage />
          </ProtectedRoute>
        } />

        {/* Summary Module */}
        <Route path="/summary" element={
          <ProtectedRoute user={user}>
            <div className="min-h-screen bg-gray-50 pb-20">
              <div className="max-w-7xl mx-auto pt-6 px-4 sm:px-6 lg:px-8">

                <SummaryPage />
              </div>
            </div>
          </ProtectedRoute>
        } />

        {/* Audit Module */}
        <Route path="/audit" element={
          <RoleRoute user={user} roles={['admin', 'control_calidad']}>
            <div className="min-h-screen bg-gray-50 pb-20">
              <div className="max-w-7xl mx-auto pt-6 px-4 sm:px-6 lg:px-8">
                <AuditPage />
              </div>
            </div>
          </RoleRoute>
        } />

        <Route path="/audit/observation/:station/:date" element={
          <RoleRoute user={user} roles={['admin', 'control_calidad']}>
            <div className="min-h-screen bg-gray-50 pb-20">
              <div className="max-w-7xl mx-auto pt-6 px-4 sm:px-6 lg:px-8">
                <AuditObservationPage />
              </div>
            </div>
          </RoleRoute>
        } />

        <Route path="/audit/report" element={
          <RoleRoute user={user} roles={['admin', 'control_calidad']}>
            <div className="min-h-screen bg-gray-50 pb-20">
              <div className="max-w-7xl mx-auto pt-6 px-4 sm:px-6 lg:px-8">
                <AuditReportPage />
              </div>
            </div>
          </RoleRoute>
        } />

        {/* Maintenance Module (4074, 5074) */}
        <Route path="/maintenance" element={
          <ProtectedRoute user={user}>
            <MaintenancePage />
          </ProtectedRoute>
        } />

        {/* CLI 3074 Module */}
        <Route path="/cli3074" element={
          <ProtectedRoute user={user}>
            <Cli3074Page />
          </ProtectedRoute>
        } />

        {/* CLI 4074 Module - Nubosidad y Temperatura */}
        <Route path="/cli4074" element={
          <ProtectedRoute user={user}>
            <Cli4074Page />
          </ProtectedRoute>
        } />

        {/* CLI 5074 Module - Fenomenos Significativos */}
        <Route path="/cli5074" element={
          <ProtectedRoute user={user}>
            <Cli5074Page />
          </ProtectedRoute>
        } />

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </Suspense>
    </div>
  );
}

export default App;