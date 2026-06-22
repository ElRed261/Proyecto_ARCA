const ROLE_ID_MAP = {
    1: 'admin',
    2: 'encargado',
    3: 'observador',
    4: 'control_calidad',
};

export const normalizeRole = (role) => {
    if (!role) return '';
    if (typeof role === 'string') return role;
    if (typeof role === 'object') {
        if (role.name) return role.name;
        if (role.id !== undefined && ROLE_ID_MAP[role.id]) return ROLE_ID_MAP[role.id];
    }
    return '';
};

export const normalizeRoles = (rolesData) => {
    if (!rolesData) return [];
    try {
        const rawRoles = typeof rolesData === 'string' ? JSON.parse(rolesData) : rolesData;
        const arr = Array.isArray(rawRoles) ? rawRoles : [rawRoles];
        return arr.map(normalizeRole).filter(Boolean);
    } catch (e) {
        console.error("Error normalizando roles:", e);
        return [];
    }
};

export const hasRole = (userRoles, requiredRoles) => {
    if (!userRoles || !requiredRoles || !requiredRoles.length) return false;
    const roles = Array.isArray(userRoles) ? userRoles : [userRoles];
    const normalized = roles.map(normalizeRole).filter(Boolean).map(r => r.toLowerCase());
    const required = requiredRoles.map(r => r.toLowerCase());
    return normalized.some(role => required.includes(role));
};

export const isAdmin = () => {
    try {
        const rolesStr = localStorage.getItem('user_roles');
        if (!rolesStr) return false;
        const roles = JSON.parse(rolesStr);
        return hasRole(roles, ['admin', 'administrador']);
    } catch (e) {
        console.error("Error checking admin role", e);
        return false;
    }
};
