import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { invoke } from '@tauri-apps/api/core';
import { authService } from '../api/authService';
import AdminPage from './AdminPage';

vi.mock('../components/StationAdminTable', () => ({
  StationAdminTable: () => <div data-testid="station-admin-table" />,
}));

vi.mock('react-hot-toast', () => ({
  default: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

describe('AdminPage', () => {
  const mockUsers = [
    { id: 1, email: 'admin@arca.com', roles: ['admin'], is_active: true },
    { id: 2, email: 'user@arca.com', roles: ['user'], is_active: false },
  ];

  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();

    invoke.mockResolvedValue({});

    vi.spyOn(authService, 'getUsers').mockResolvedValue(mockUsers);
    vi.spyOn(authService, 'createUser').mockResolvedValue({});
    vi.spyOn(authService, 'updateUser').mockResolvedValue({});
    vi.spyOn(authService, 'changePassword').mockResolvedValue({});
    vi.spyOn(authService, 'deleteUser').mockResolvedValue({});

    vi.spyOn(window, 'confirm').mockReturnValue(true);
  });

  const renderPage = () =>
    render(<AdminPage onBack={vi.fn()} addLog={vi.fn()} />);

  it('renders the user table with users', async () => {
    renderPage();

    expect(await screen.findByText('admin@arca.com')).toBeInTheDocument();
    expect(screen.getByText('user@arca.com')).toBeInTheDocument();
  });

  it('shows the "Crear Usuario" button', async () => {
    renderPage();

    expect(await screen.findByRole('button', { name: /crear usuario/i })).toBeInTheDocument();
  });

  it('opens the create modal when "Crear Usuario" is clicked', async () => {
    const user = userEvent.setup();
    renderPage();

    const createButton = await screen.findByRole('button', { name: /crear usuario/i });
    await user.click(createButton);

    expect(screen.getByRole('heading', { name: /crear nuevo usuario/i })).toBeInTheDocument();
    expect(screen.getByText(/correo electrónico/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText('usuario@arca.do')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Contraseña temporal')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Usuario')).toBeInTheDocument();
  });

  it('calls authService.createUser when the create form is submitted', async () => {
    const user = userEvent.setup();
    renderPage();

    const createButton = await screen.findByRole('button', { name: /crear usuario/i });
    await user.click(createButton);

    await user.type(screen.getByPlaceholderText('usuario@arca.do'), 'new@arca.com');
    await user.type(screen.getByPlaceholderText('Contraseña temporal'), 'secret123');

    const submitButton = screen.getByText('Crear Usuario', { selector: 'button[type="submit"]' });
    await user.click(submitButton);

    await waitFor(() => {
      expect(authService.createUser).toHaveBeenCalledWith('new@arca.com', 'secret123', 'user');
    });
  });

  it('opens the edit modal when the edit button is clicked', async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByText('admin@arca.com');
    const editButtons = screen.getAllByTitle(/editar/i);
    expect(editButtons.length).toBeGreaterThan(0);

    await user.click(editButtons[0]);

    expect(screen.getByRole('heading', { name: /editar usuario/i })).toBeInTheDocument();
    expect(screen.getByText(/rol del sistema/i)).toBeInTheDocument();
    expect(screen.getByDisplayValue('Administrador')).toBeInTheDocument();
    expect(screen.getByRole('checkbox')).toBeInTheDocument();
  });

  it('calls authService.deleteUser when the delete button is clicked', async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByText('admin@arca.com');
    const deleteButtons = screen.getAllByTitle(/desactivar/i);
    expect(deleteButtons.length).toBeGreaterThan(0);

    await user.click(deleteButtons[0]);

    await waitFor(() => {
      expect(authService.deleteUser).toHaveBeenCalledWith(1);
    });
  });

  it('renders the station locking section', async () => {
    renderPage();

    expect(
      await screen.findByRole('heading', { name: /bloqueo de estación por instalación/i })
    ).toBeInTheDocument();
    expect(screen.getByText('Estación Meteorológica')).toBeInTheDocument();
    expect(screen.getByRole('combobox')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /aplicar bloqueo/i })).toBeInTheDocument();
  });

  it('shows a loading state while users are loading', () => {
    authService.getUsers.mockReturnValue(new Promise(() => {}));
    renderPage();

    expect(screen.getByText(/cargando usuarios/i)).toBeInTheDocument();
  });
});
