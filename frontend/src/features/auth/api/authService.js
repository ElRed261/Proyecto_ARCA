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
        }
        return response.data;
    },

    // Función para registrar admin (solo para pruebas iniciales)
    register: async (email, password) => {
        const response = await api.post('/auth/register-admin', {
            email,
            password,
            role_name: 'admin' // Valor por defecto
        });
        return response.data;
    },

    // Función para salir
    logout: () => {
        localStorage.removeItem('token');
        localStorage.removeItem('user_email');
    }
};