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

    // Logout: limpia localStorage
    logout: () => {
        localStorage.removeItem('token');
        localStorage.removeItem('user_email');
        localStorage.removeItem('user_roles');
    },

    // --- ADMIN METHODS usando Tauri IPC y Rust ---
    getUsers: async () => {
        return await invoke('get_users');
    },

    updateUser: async (userId, data) => {
        return await invoke('update_user', {
            userId,
            roleName: data.role_name,
            isActive: data.is_active,
        });
    },

    changePassword: async (userId, password) => {
        return await invoke('change_password', {
            userId,
            passwordVal: password,
        });
    },

    deleteUser: async (userId) => {
        return await invoke('delete_user', { userId });
    },
};