import http from './http.js'
export const listLlm   = () => http.get('/api/config/llm')
export const listDb    = () => http.get('/api/config/db')
export const saveLlm   = (form) => http.post('/api/config/llm', form)
export const saveDb    = (form) => http.post('/api/config/db', form)
export const testLlm   = (form) => http.post('/api/config/llm/test', form)
export const testDb    = (form) => http.post('/api/config/db/test', form)
export const removeLlm = (id) => http.delete(`/api/config/llm/${id}`)
export const removeDb  = (id) => http.delete(`/api/config/db/${id}`)
