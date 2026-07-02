import { describe, it, expect, beforeEach } from 'vitest';
import { normalizeRole, normalizeRoles, hasRole, isAdmin } from './auth';

describe('auth utilities', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  describe('normalizeRole', () => {
    it('returns lowercase string roles as-is', () => {
      expect(normalizeRole('admin')).toBe('admin');
      expect(normalizeRole('user')).toBe('user');
      expect(normalizeRole('control_calidad')).toBe('control_calidad');
    });

    it('preserves original casing for string roles', () => {
      expect(normalizeRole('ADMIN')).toBe('ADMIN');
      expect(normalizeRole('Admin')).toBe('Admin');
      expect(normalizeRole('CONTROL_CALIDAD')).toBe('CONTROL_CALIDAD');
    });

    it('resolves numeric role ids to role names', () => {
      expect(normalizeRole({ id: 1 })).toBe('admin');
      expect(normalizeRole({ id: 2 })).toBe('encargado');
      expect(normalizeRole({ id: 3 })).toBe('observador');
      expect(normalizeRole({ id: 4 })).toBe('control_calidad');
    });

    it('returns the role name property when present', () => {
      expect(normalizeRole({ name: 'admin' })).toBe('admin');
      expect(normalizeRole({ name: 'CONTROL_CALIDAD' })).toBe('CONTROL_CALIDAD');
    });

    it('returns empty string for falsy values', () => {
      expect(normalizeRole(null)).toBe('');
      expect(normalizeRole(undefined)).toBe('');
      expect(normalizeRole('')).toBe('');
    });

    it('returns empty string for unknown values', () => {
      expect(normalizeRole(123)).toBe('');
      expect(normalizeRole({})).toBe('');
      expect(normalizeRole({ id: 99 })).toBe('');
    });
  });

  describe('normalizeRoles', () => {
    it('parses a JSON string array of roles', () => {
      expect(normalizeRoles('["admin"]')).toEqual(['admin']);
      expect(normalizeRoles('["admin", "user"]')).toEqual(['admin', 'user']);
    });

    it('returns an empty array for a plain string role (not valid JSON)', () => {
      // The current implementation only accepts JSON arrays; plain strings fail to parse.
      expect(normalizeRoles('admin')).toEqual([]);
      expect(normalizeRoles('user')).toEqual([]);
    });

    it('wraps a valid JSON string role in an array', () => {
      expect(normalizeRoles('"admin"')).toEqual(['admin']);
      expect(normalizeRoles('"user"')).toEqual(['user']);
    });

    it('normalizes an array of roles', () => {
      expect(normalizeRoles(['admin', 'user'])).toEqual(['admin', 'user']);
      expect(normalizeRoles([{ id: 1 }, { id: 4 }])).toEqual(['admin', 'control_calidad']);
    });

    it('filters out empty or invalid roles', () => {
      expect(normalizeRoles(['admin', '', null, undefined])).toEqual(['admin']);
      expect(normalizeRoles([{}, { id: 99 }])).toEqual([]);
    });

    it('returns an empty array for null, undefined or empty input', () => {
      expect(normalizeRoles(null)).toEqual([]);
      expect(normalizeRoles(undefined)).toEqual([]);
      expect(normalizeRoles('')).toEqual([]);
    });

    it('returns an empty array for invalid JSON strings', () => {
      expect(normalizeRoles('{invalid')).toEqual([]);
    });
  });

  describe('hasRole', () => {
    it('returns true when the user has the required role', () => {
      expect(hasRole(['admin'], ['admin'])).toBe(true);
      expect(hasRole(['admin', 'control_calidad'], ['control_calidad'])).toBe(true);
    });

    it('returns false when the user does not have the required role', () => {
      expect(hasRole(['admin'], ['user'])).toBe(false);
      expect(hasRole(['user'], ['admin'])).toBe(false);
    });

    it('returns false for empty user roles or missing requirements', () => {
      expect(hasRole([], ['admin'])).toBe(false);
      expect(hasRole(['admin'], [])).toBe(false);
      expect(hasRole(null, ['admin'])).toBe(false);
      expect(hasRole(['admin'], null)).toBe(false);
    });

    it('compares roles case-insensitively', () => {
      expect(hasRole(['ADMIN'], ['admin'])).toBe(true);
      expect(hasRole(['Admin'], ['admin'])).toBe(true);
      expect(hasRole(['admin', 'CONTROL_CALIDAD'], ['control_calidad'])).toBe(true);
    });

    it('requires the required roles argument to be an array', () => {
      // The current implementation calls requiredRoles.map, so a string throws.
      expect(() => hasRole(['admin'], 'admin')).toThrow();
    });
  });

  describe('isAdmin', () => {
    it('returns true when localStorage contains an admin role', () => {
      localStorage.setItem('user_roles', JSON.stringify(['admin']));
      expect(isAdmin()).toBe(true);
    });

    it('returns true for the administrador alias', () => {
      localStorage.setItem('user_roles', JSON.stringify(['administrador']));
      expect(isAdmin()).toBe(true);
    });

    it('returns false for non-admin roles', () => {
      localStorage.setItem('user_roles', JSON.stringify(['user']));
      expect(isAdmin()).toBe(false);
    });

    it('returns false when no roles are stored', () => {
      expect(isAdmin()).toBe(false);
    });

    it('returns false for an empty roles array', () => {
      localStorage.setItem('user_roles', JSON.stringify([]));
      expect(isAdmin()).toBe(false);
    });

    it('returns false when stored roles are not valid JSON', () => {
      localStorage.setItem('user_roles', 'not-json');
      expect(isAdmin()).toBe(false);
    });
  });
});
