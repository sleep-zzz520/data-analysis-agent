import axios from 'axios'
const http = axios.create({ baseURL: '', timeout: 120000 })

// 请求自动携带 token
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  (res) => res.data,
  (err) => {
    // 登录失效：清 token 跳登录页（登录页本身除外）
    if (err.response?.status === 401 && !location.pathname.startsWith('/login')) {
      localStorage.removeItem('token')
      localStorage.removeItem('username')
      location.href = '/login'
    }
    let e
    if (!err.response) {
      e = { code:'NETWORK', severity:'block', message:'无法连接到后端服务。', suggestion:'请确认后端已启动（uvicorn ... 8000），且 vite 代理目标正确。' }
    } else {
      const s = err.response.status
      const detail = err.response.data?.detail || err.message
      if (s === 422) e = { code:'VALIDATION', severity:'warn', message:'填写内容校验未通过。', suggestion:String(detail) }
      else if (s === 404) e = { code:'NOT_FOUND', severity:'block', message:'接口不存在（404）。', suggestion:'请确认后端已实现该路由，或前后端路径前缀一致。' }
      else if (s >= 500) e = { code:'SERVER', severity:'block', message:`后端异常（${s}）。`, suggestion:String(detail).slice(0,200) }
      else e = { code:`HTTP_${s}`, severity:'warn', message:`请求失败（${s}）。`, suggestion:String(detail).slice(0,200) }
    }
    return Promise.reject(e)
  }
)
export default http
