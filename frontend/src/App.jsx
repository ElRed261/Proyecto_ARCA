import { useState, useEffect } from 'react';
import { Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import AuthPage from './features/auth/pages/AuthPage';
import DashboardPage from './features/dashboard/pages/DashboardPage';
import AdminPage from './features/auth/pages/AdminPage';
import SynopticPage from './features/synoptic/pages/SynopticPage';
import SummaryPage from './features/summary/pages/SummaryPage';
import AuditPage from './features/audit/pages/AuditPage';

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

        {/* Synoptic Module */}
        <Route path="/synoptic" element={
          <ProtectedRoute>
            <div className="min-h-screen bg-gray-50 pb-20">
              <div className="max-w-7xl mx-auto pt-6 px-4 sm:px-6 lg:px-8">
                <button onClick={() => navigate('/dashboard')} className="mb-4 text-indigo-600 hover:text-indigo-800">
                  &larr; Volver al Dashboard
                </button>
                <SynopticPage />
              </div>
            </div>
          </ProtectedRoute>
        } />

        {/* Summary Module */}
        <Route path="/summary" element={
          <ProtectedRoute>
            <div className="min-h-screen bg-gray-50 pb-20">
              <div className="max-w-7xl mx-auto pt-6 px-4 sm:px-6 lg:px-8">
                <button onClick={() => navigate('/dashboard')} className="mb-4 text-indigo-600 hover:text-indigo-800">
                  &larr; Volver al Dashboard
                </button>
                <SummaryPage />
              </div>
            </div>
          </ProtectedRoute>
        } />

        {/* Audit Module */}
        <Route path="/audit" element={
          <ProtectedRoute>
            <div className="min-h-screen bg-gray-50 pb-20">
              <div className="max-w-7xl mx-auto pt-6 px-4 sm:px-6 lg:px-8">
                <button onClick={() => navigate('/dashboard')} className="mb-4 text-indigo-600 hover:text-indigo-800">
                  &larr; Volver al Dashboard
                </button>
                <AuditPage />
              </div>
            </div>
          </ProtectedRoute>
        } />

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}

export default App;