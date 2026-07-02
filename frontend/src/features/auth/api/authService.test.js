import { describe, it, expect, vi, beforeEach } from 'vitest';
import { invoke } from '@tauri-apps/api/core';
import { authService } from './authService';

describe('authService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  describe('login', () => {
    it('stores token, email and roles in localStorage on success', async () => {
      const response = {
        access_token: 'valid-token-123',
        user_email: 'user@arca.com',
        roles: ['admin'],
      };
      invoke.mockResolvedValue(response);

      const result = await authService.login('user@arca.com', 'password');

      expect(invoke).toHaveBeenCalledWith('login_user', {
        email: 'user@arca.com',
        password: 'password',
      });
      expect(result).toEqual(response);
      expect(localStorage.getItem('token')).toBe('valid-token-123');
      expect(localStorage.getItem('user_email')).toBe('user@arca.com');
      expect(localStorage.getItem('user_roles')).toBe(JSON.stringify(['admin']));
    });

    it('throws an error shaped like an axios response on failure', async () => {
      invoke.mockRejectedValue('Invalid credentials');

      await expect(authService.login('user@arca.com', 'wrong')).rejects.toEqual({
        response: { data: { detail: 'Invalid credentials' } },
      });
    });
  });

  describe('logout', () => {
    it('calls logout command and clears localStorage', async () => {
      localStorage.setItem('token', 'token-123');
      localStorage.setItem('user_email', 'user@arca.com');
      localStorage.setItem('user_roles', JSON.stringify(['admin']));
      invoke.mockResolvedValue({});

      await authService.logout();

      expect(invoke).toHaveBeenCalledWith('logout', { token: 'token-123' });
      expect(localStorage.getItem('token')).toBeNull();
      expect(localStorage.getItem('user_email')).toBeNull();
      expect(localStorage.getItem('user_roles')).toBeNull();
    });

    it('still clears localStorage when the backend call fails', async () => {
      localStorage.setItem('token', 'token-123');
      localStorage.setItem('user_email', 'user@arca.com');
      localStorage.setItem('user_roles', JSON.stringify(['admin']));
      invoke.mockRejectedValue(new Error('session expired'));

      await authService.logout();

      expect(localStorage.getItem('token')).toBeNull();
      expect(localStorage.getItem('user_email')).toBeNull();
      expect(localStorage.getItem('user_roles')).toBeNull();
    });
  });

  describe('validateToken', () => {
    it('returns true when a valid token is stored', async () => {
      localStorage.setItem('token', 'valid-token');
      invoke.mockResolvedValue(true);

      const result = await authService.validateToken();

      expect(invoke).toHaveBeenCalledWith('validate_token', { token: 'valid-token' });
      expect(result).toBe(true);
    });

    it('returns false when no token is stored', async () => {
      const result = await authService.validateToken();

      expect(invoke).not.toHaveBeenCalled();
      expect(result).toBe(false);
    });

    it('returns false when invoke throws', async () => {
      localStorage.setItem('token', 'invalid-token');
      invoke.mockRejectedValue(new Error('token invalid'));

      const result = await authService.validateToken();

      expect(result).toBe(false);
    });
  });

  describe('admin methods', () => {
    beforeEach(() => {
      localStorage.setItem('token', 'admin-token');
    });

    it('getUsers calls get_users with the stored token', async () => {
      const users = [{ id: 1, email: 'a@a.com' }];
      invoke.mockResolvedValue(users);

      const result = await authService.getUsers();

      expect(invoke).toHaveBeenCalledWith('get_users', { token: 'admin-token' });
      expect(result).toEqual(users);
    });

    it('createUser calls create_user with email, password and role', async () => {
      invoke.mockResolvedValue({ id: 2 });

      await authService.createUser('new@arca.com', 'secret', 'user');

      expect(invoke).toHaveBeenCalledWith('create_user', {
        token: 'admin-token',
        email: 'new@arca.com',
        password: 'secret',
        role: 'user',
      });
    });

    it('updateUser calls update_user with role and active status', async () => {
      invoke.mockResolvedValue({});

      await authService.updateUser(5, { role_name: 'admin', is_active: false });

      expect(invoke).toHaveBeenCalledWith('update_user', {
        token: 'admin-token',
        userId: 5,
        roleName: 'admin',
        isActive: false,
      });
    });

    it('changePassword calls change_password with the new password', async () => {
      invoke.mockResolvedValue({});

      await authService.changePassword(3, 'new-password');

      expect(invoke).toHaveBeenCalledWith('change_password', {
        token: 'admin-token',
        userId: 3,
        passwordVal: 'new-password',
      });
    });

    it('deleteUser calls delete_user with the user id', async () => {
      invoke.mockResolvedValue({});

      await authService.deleteUser(7);

      expect(invoke).toHaveBeenCalledWith('delete_user', {
        token: 'admin-token',
        userId: 7,
      });
    });
  });
});
