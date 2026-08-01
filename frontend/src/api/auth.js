import http from './http.js'
export const register = (username, password) => http.post('/api/auth/register', { username, password })
export const login = (username, password) => http.post('/api/auth/login', { username, password })
export const me = () => http.get('/api/auth/me')
export const listUsers = () => http.get('/api/auth/users')
export const setUserRole = (userId, role) => http.put(`/api/auth/users/${userId}`, { role })
export const changePassword = (oldPassword, newPassword) => http.post('/api/auth/change-password', { old_password: oldPassword, new_password: newPassword })
export const deleteAccount = () => http.delete('/api/auth/account')
