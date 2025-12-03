export const isAdmin = () => {
    try {
        const rolesStr = localStorage.getItem('user_roles');
        if (!rolesStr) return false;
        const roles = JSON.parse(rolesStr);
        // Check if roles is an array of objects with name property or just strings
        // Based on previous code, it seems to be objects from backend
        return roles.some(r => (r.name === 'admin' || r === 'admin'));
    } catch (e) {
        console.error("Error checking admin role", e);
        return false;
    }
};
