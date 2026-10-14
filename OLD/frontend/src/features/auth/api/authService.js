import { invoke } from '@tauri-apps/api/core';

export const authService = {
    // Login usando comando Tauri seguro en Rust
    login: async (email, password) => {
        try {
            const data = await invoke('login_user', { email, password });

            localStorage.setItem('token', data.access_token);
            localStorage.setItem('user_email', data.user_email);
            localStorage.setItem('user_roles', JSON.stringify(data.roles));

            return data;
        } catch (error) {
            throw { response: { data: { detail: error } } };
        }
    },

    // Registro deshabilitado en modo local
    register: async () => {
        throw { response: { data: { detail: 'Registro deshabilitado en modo local' } } };
    },

    // Logout: limpia backend + localStorage
    logout: async () => {
        const token = localStorage.getItem('token') || '';
        try {
            if (token) await invoke('logout', { token });
        } catch {
            // Si el backend ya no tiene la sesión, no importa
        }
        localStorage.removeItem('token');
        localStorage.removeItem('user_email');
        localStorage.removeItem('user_roles');
    },

    // Validar token contra el backend (SessionStore en memoria)
    validateToken: async () => {
        const token = localStorage.getItem('token') || '';
        if (!token) return false;
        try {
            return await invoke('validate_token', { token });
        } catch {
            return false;
        }
    },

    // --- ADMIN METHODS usando Tauri IPC y Rust ---
    getUsers: async () => {
        const token = localStorage.getItem('token') || '';
        return await invoke('get_users', { token });
    },

    updateUser: async (userId, data) => {
        const token = localStorage.getItem('token') || '';
        return await invoke('update_user', {
            token,
            userId,
            roleName: data.role_name,
            isActive: data.is_active,
        });
    },

    changePassword: async (userId, password) => {
        const token = localStorage.getItem('token') || '';
        return await invoke('change_password', {
            token,
            userId,
            passwordVal: password,
        });
    },

    createUser: async (email, password, role) => {
        const token = localStorage.getItem('token') || '';
        return await invoke('create_user', { token, email, password, role });
    },

    deleteUser: async (userId) => {
        const token = localStorage.getItem('token') || '';
        return await invoke('delete_user', { token, userId });
    },
};