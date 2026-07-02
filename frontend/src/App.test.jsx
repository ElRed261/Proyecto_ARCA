import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import { authService } from './features/auth/api/authService';
import App from './App';

vi.mock('./features/auth/api/authService', () => ({
  authService: {
    validateToken: vi.fn(),
    logout: vi.fn(),
  },
}));

vi.mock('./features/auth/pages/AuthPage', () => ({
  default: ({ onLoginSuccess }) => (
    <div data-testid="auth-page">
      <h1>Login</h1>
      <button
        data-testid="auth-login-button"
        onClick={() =>
          onLoginSuccess({
            user_email: 'user@arca.com',
            roles: ['admin'],
          })
        }
      >
        Log in
      </button>
    </div>
  ),
}));

vi.mock('./features/dashboard/pages/DashboardPage', () => ({
  default: ({ onLogout }) => (
    <div data-testid="dashboard-page">
      <h1>Dashboard</h1>
      <button data-testid="dashboard-logout" onClick={onLogout}>
        Logout
      </button>
    </div>
  ),
}));

describe('App routing', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  const renderApp = (initialEntries = ['/']) =>
    render(
      <MemoryRouter initialEntries={initialEntries}>
        <App />
      </MemoryRouter>
    );

  it('renders the login page when no token is stored', async () => {
    authService.validateToken.mockResolvedValue(false);
    renderApp();

    expect(await screen.findByTestId('auth-page')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /login/i })).toBeInTheDocument();
  });

  it('redirects to the dashboard when a valid token is stored', async () => {
    localStorage.setItem('token', 'valid-token');
    localStorage.setItem('user_email', 'user@arca.com');
    localStorage.setItem('user_roles', JSON.stringify(['admin']));
    authService.validateToken.mockResolvedValue(true);

    renderApp(['/dashboard']);

    expect(await screen.findByTestId('dashboard-page')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /dashboard/i })).toBeInTheDocument();
  });

  it('clears localStorage and shows login for an invalid token', async () => {
    localStorage.setItem('token', 'invalid-token');
    localStorage.setItem('user_email', 'user@arca.com');
    localStorage.setItem('user_roles', JSON.stringify(['admin']));
    authService.validateToken.mockResolvedValue(false);

    renderApp();

    await waitFor(() => {
      expect(localStorage.getItem('token')).toBeNull();
      expect(localStorage.getItem('user_email')).toBeNull();
      expect(localStorage.getItem('user_roles')).toBeNull();
    });

    expect(await screen.findByTestId('auth-page')).toBeInTheDocument();
  });

  it('clears user state and shows login on logout', async () => {
    localStorage.setItem('token', 'valid-token');
    localStorage.setItem('user_email', 'user@arca.com');
    localStorage.setItem('user_roles', JSON.stringify(['admin']));
    authService.validateToken.mockResolvedValue(true);
    authService.logout.mockImplementation(async () => {
      localStorage.removeItem('token');
      localStorage.removeItem('user_email');
      localStorage.removeItem('user_roles');
    });

    renderApp(['/dashboard']);

    const user = userEvent.setup();
    const logoutButton = await screen.findByTestId('dashboard-logout');
    await user.click(logoutButton);

    await waitFor(() => {
      expect(authService.logout).toHaveBeenCalled();
      expect(screen.getByTestId('auth-page')).toBeInTheDocument();
    });
  });
});
