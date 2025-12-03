import React, { useState, useEffect } from 'react';
import { authService } from '../api/authService';
import { Users, Edit, Key, Trash2, CheckCircle, XCircle, ShieldAlert } from 'lucide-react';

const AdminPage = ({ onBack, addLog }) => {
    const [users, setUsers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedUser, setSelectedUser] = useState(null);
    const [showEditModal, setShowEditModal] = useState(false);
    const [showPasswordModal, setShowPasswordModal] = useState(false);

    // Form states
    const [editForm, setEditForm] = useState({ role_name: '', is_active: true });
    const [passwordForm, setPasswordForm] = useState({ password: '' });

    useEffect(() => {
        fetchUsers();
    }, []);

    const fetchUsers = async () => {
        try {
            setLoading(true);
            const data = await authService.getUsers();
            setUsers(data);
            addLog('Lista de usuarios actualizada.', 'success');
        } catch (error) {
            console.error(error);
            addLog('Error al cargar usuarios.', 'error');
        } finally {
            setLoading(false);
        }
    };

    const handleEditClick = (user) => {
        setSelectedUser(user);
        // Asumimos que el usuario tiene un rol principal o tomamos el primero
        const currentRole = user.roles && user.roles.length > 0 ? user.roles[0].name : 'user';
        setEditForm({ role_name: currentRole, is_active: user.is_active });
        setShowEditModal(true);
    };

    const handlePasswordClick = (user) => {
        setSelectedUser(user);
        setPasswordForm({ password: '' });
        setShowPasswordModal(true);
    };

    const handleDeleteClick = async (user) => {
        if (window.confirm(`¿Estás seguro de desactivar al usuario ${user.email}?`)) {
            try {
                await authService.deleteUser(user.id);
                addLog(`Usuario ${user.email} desactivado.`, 'warning');
                fetchUsers();
            } catch (error) {
                addLog('Error al desactivar usuario.', 'error');
            }
        }
    };

    const submitEdit = async (e) => {
        e.preventDefault();
        try {
            await authService.updateUser(selectedUser.id, editForm);
            addLog(`Usuario ${selectedUser.email} actualizado.`, 'success');
            setShowEditModal(false);
            fetchUsers();
        } catch (error) {
            addLog('Error al actualizar usuario.', 'error');
        }
    };

    const submitPassword = async (e) => {
        e.preventDefault();
        try {
            await authService.changePassword(selectedUser.id, passwordForm.password);
            addLog(`Contraseña de ${selectedUser.email} cambiada.`, 'success');
            setShowPasswordModal(false);
        } catch (error) {
            addLog('Error al cambiar contraseña.', 'error');
        }
    };

    return (
        <div className="min-h-screen bg-gray-50 p-8 pb-64">
            <div className="max-w-6xl mx-auto">
                {/* Header */}
                <div className="flex justify-between items-center mb-8">
                    <div>
                        <h1 className="text-3xl font-bold text-gray-800 flex items-center gap-3">
                            <ShieldAlert className="text-blue-600" size={32} />
                            Panel de Seguridad
                        </h1>
                        <p className="text-gray-500 mt-1">Gestión de Usuarios y Permisos del Sistema</p>
                    </div>
                    <button
                        onClick={onBack}
                        className="px-6 py-2 bg-gradient-to-r from-gray-800 to-gray-900 text-white rounded-lg hover:from-gray-700 hover:to-gray-800 transition shadow-lg flex items-center gap-2 font-medium"
                    >
                        <span>←</span> Volver al Dashboard
                    </button>
                </div>

                {/* Table */}
                <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                    <div className="overflow-x-auto">
                        <table className="w-full text-left">
                            <thead className="bg-gray-50 border-b border-gray-200">
                                <tr>
                                    <th className="px-6 py-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">ID</th>
                                    <th className="px-6 py-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Usuario</th>
                                    <th className="px-6 py-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Roles</th>
                                    <th className="px-6 py-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">Estado</th>
                                    <th className="px-6 py-4 text-xs font-semibold text-gray-500 uppercase tracking-wider text-right">Acciones</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-200">
                                {loading ? (
                                    <tr><td colSpan="5" className="px-6 py-8 text-center text-gray-500">Cargando usuarios...</td></tr>
                                ) : users.map((user) => (
                                    <tr key={user.id} className="hover:bg-gray-50 transition">
                                        <td className="px-6 py-4 text-sm text-gray-500">#{user.id}</td>
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-3">
                                                <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-bold text-xs">
                                                    {user.email.substring(0, 2).toUpperCase()}
                                                </div>
                                                <span className="text-sm font-medium text-gray-900">{user.email}</span>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            {user.roles && user.roles.length > 0 ? (
                                                user.roles.map(role => (
                                                    <span key={role.id} className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800 mr-1">
                                                        {role.name}
                                                    </span>
                                                ))
                                            ) : (
                                                <span className="text-xs text-gray-400">Sin rol</span>
                                            )}
                                        </td>
                                        <td className="px-6 py-4">
                                            {user.is_active ? (
                                                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                                                    <CheckCircle size={12} /> Activo
                                                </span>
                                            ) : (
                                                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                                                    <XCircle size={12} /> Inactivo
                                                </span>
                                            )}
                                        </td>
                                        <td className="px-6 py-4 text-right space-x-2">
                                            <button
                                                onClick={() => handleEditClick(user)}
                                                className="p-2 text-blue-600 hover:bg-blue-50 rounded-full transition"
                                                title="Editar"
                                            >
                                                <Edit size={18} />
                                            </button>
                                            <button
                                                onClick={() => handlePasswordClick(user)}
                                                className="p-2 text-yellow-600 hover:bg-yellow-50 rounded-full transition"
                                                title="Cambiar Contraseña"
                                            >
                                                <Key size={18} />
                                            </button>
                                            <button
                                                onClick={() => handleDeleteClick(user)}
                                                className="p-2 text-red-600 hover:bg-red-50 rounded-full transition"
                                                title="Desactivar"
                                            >
                                                <Trash2 size={18} />
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            {/* Edit Modal */}
            {showEditModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 backdrop-blur-sm">
                    <div className="bg-white rounded-xl shadow-2xl p-6 w-full max-w-md">
                        <h3 className="text-lg font-bold text-gray-900 mb-4">Editar Usuario</h3>
                        <form onSubmit={submitEdit} className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Rol del Sistema</label>
                                <select
                                    className="w-full border border-gray-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500"
                                    value={editForm.role_name}
                                    onChange={(e) => setEditForm({ ...editForm, role_name: e.target.value })}
                                >
                                    <option value="user">Usuario</option>
                                    <option value="admin">Administrador</option>
                                    <option value="manager">Gerente</option>
                                </select>
                            </div>
                            <div className="flex items-center gap-2">
                                <input
                                    type="checkbox"
                                    id="isActive"
                                    checked={editForm.is_active}
                                    onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })}
                                    className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                                />
                                <label htmlFor="isActive" className="text-sm text-gray-700">Cuenta Activa</label>
                            </div>
                            <div className="flex justify-end gap-3 mt-6">
                                <button type="button" onClick={() => setShowEditModal(false)} className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg">Cancelar</button>
                                <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">Guardar Cambios</button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Password Modal */}
            {showPasswordModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 backdrop-blur-sm">
                    <div className="bg-white rounded-xl shadow-2xl p-6 w-full max-w-md">
                        <h3 className="text-lg font-bold text-gray-900 mb-4">Cambiar Contraseña</h3>
                        <p className="text-sm text-gray-500 mb-4">Establece una nueva contraseña para {selectedUser?.email}</p>
                        <form onSubmit={submitPassword} className="space-y-4">
                            <div>
                                <input
                                    type="password"
                                    placeholder="Nueva contraseña"
                                    required
                                    className="w-full border border-gray-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500"
                                    value={passwordForm.password}
                                    onChange={(e) => setPasswordForm({ ...passwordForm, password: e.target.value })}
                                />
                            </div>
                            <div className="flex justify-end gap-3 mt-6">
                                <button type="button" onClick={() => setShowPasswordModal(false)} className="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg">Cancelar</button>
                                <button type="submit" className="px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700">Actualizar</button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
};

export default AdminPage;
