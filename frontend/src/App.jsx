import { useState, useEffect } from 'react';
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { ArrowLeft } from 'lucide-react';
import AuthPage from './features/auth/pages/AuthPage';
import DashboardPage from './features/dashboard/pages/DashboardPage';
import AdminPage from './features/auth/pages/AdminPage';
import SynopticPage from './features/synoptic/pages/SynopticPage';
import SummaryPage from './features/summary/pages/SummaryPage';
import AuditPage from './features/audit/pages/AuditPage';
import AuditObservationPage from './features/audit/pages/AuditObservationPage';
import AuditReportPage from './features/audit/pages/AuditReportPage';
import MaintenancePage from './features/maintenance/pages/MaintenancePage';
import Cli3074Page from './features/synoptic/cli3074/pages/Cli3074Page';
import Cli4074Page from './features/synoptic/cli4074/pages/Cli4074Page';
import Cli5074Page from './features/synoptic/cli5074/pages/Cli5074Page';
import { normalizeRoles, hasRole } from './shared/utils/auth';

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
    const token = localStorage.getItem('token');
    const email = localStorage.getItem('user_email');
    const savedRoles = localStorage.getItem('user_roles');

    if (token && email) {
      const roles = normalizeRoles(savedRoles);
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setUser({ email, roles });
      addLog('Sistema restaurado. Sesión activa detectada.', 'success');
      if (location.pathname === '/') {
        navigate('/dashboard');
      }
    }
  }, []);

  const handleLoginSuccess = (userData) => {
    const roles = normalizeRoles(userData.roles);
    setUser({ email: userData.user_email, roles });
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

  return (
    <div className="relative min-h-screen bg-gray-100 font-sans text-gray-800">
      <Toaster position="top-right" />
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
    </div>
  );
}

export default App;