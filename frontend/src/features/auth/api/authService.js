import api from '../../../shared/api/axiosConfig';

// =====================================================
// Cuentas locales hardcodeadas (auth sin servidor)
// TODO: Reemplazar con autenticación basada en servidor
// cuando se implemente la infraestructura de auth
// =====================================================
const LOCAL_USERS = [
    { email: 'admin@arca.rd', password: 'admin123', roles: ['admin'] },
    { email: 'encargado@arca.rd', password: 'encargado123', roles: ['encargado'] },
    { email: 'observador@arca.rd', password: 'observador123', roles: ['observador'] },
];

export const authService = {
    // Login local: valida contra cuentas hardcodeadas
    login: async (email, password) => {
        const user = LOCAL_USERS.find(
            (u) => u.email === email && u.password === password
        );

        if (!user) {
            throw { response: { data: { detail: 'Credenciales incorrectas' } } };
        }

        // Generar un token local simple (no criptográfico — es placeholder)
        const token = btoa(JSON.stringify({ sub: user.email, roles: user.roles, iat: Date.now() }));

        localStorage.setItem('token', token);
        localStorage.setItem('user_email', user.email);
        localStorage.setItem('user_roles', JSON.stringify(user.roles));

        return {
            access_token: token,
            token_type: 'bearer',
            user_email: user.email,
            roles: user.roles,
        };
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

    // --- ADMIN METHODS (siguen usando el backend API) ---
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
    },
};