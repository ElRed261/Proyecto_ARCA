import api from '../../../shared/api/axiosConfig';

export const authService = {
    // Función para iniciar sesión
    login: async (email, password) => {
        // Enviamos los datos al endpoint que creamos en Python
        const response = await api.post('/auth/login', { email, password });

        // Si hay éxito, guardamos el token en el navegador
        if (response.data.access_token) {
            localStorage.setItem('token', response.data.access_token);
            localStorage.setItem('user_email', response.data.user_email);
            localStorage.setItem('user_roles', JSON.stringify(response.data.roles));
        }
        return response.data;
    },

    // Función para registrar usuario
    register: async (email, password) => {
        const response = await api.post('/auth/register', {
            email,
            password
        });
        return response.data;
    },

    // Función para salir
    logout: () => {
        localStorage.removeItem('token');
        localStorage.removeItem('user_email');
        localStorage.removeItem('user_roles');
    },

    // --- ADMIN METHODS ---
    getUsers: async () => {
        const response = await api.get('/admin/users');
        return response.data;
    },

    updateUser: async (userId, data) => {
        const response = await api.put(`/admin/users/${userId}`, data);
        return response.data;
    },

    changePassword: async (userId, password) => {
        const response = await api.put(`/admin/users/${userId}/password`, { password });
        return response.data;
    },

    deleteUser: async (userId) => {
        const response = await api.delete(`/admin/users/${userId}`);
        return response.data;
    }
};