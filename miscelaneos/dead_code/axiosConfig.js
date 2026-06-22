import axios from 'axios';

// Creamos una instancia configurada para no repetir la URL siempre
const api = axios.create({
    baseURL: 'http://127.0.0.1:8000/api', // La dirección de tu FastAPI
    headers: {
        'Content-Type': 'application/json',
    },
});

// Interceptor: Antes de cada petición, si tenemos token, lo pegamos
api.interceptors.request.use(
    (config) => {
        const token = localStorage.getItem('token');
        if (token) {
            config.headers['Authorization'] = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

export default api;