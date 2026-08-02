import { describe, it, expect, vi, beforeEach } from 'vitest'
import http from './http.js'

describe('http 请求拦截器', () => {
  beforeEach(() => localStorage.clear())

  it('有 token 时自动携带 Bearer 头', () => {
    localStorage.setItem('token', 'jwt-abc')
    const handler = http.interceptors.request.handlers[0].fulfilled
    const config = handler({ headers: {} })
    expect(config.headers.Authorization).toBe('Bearer jwt-abc')
  })

  it('无 token 时不携带 Authorization 头', () => {
    const handler = http.interceptors.request.handlers[0].fulfilled
    const config = handler({ headers: {} })
    expect(config.headers.Authorization).toBeUndefined()
  })
})

describe('http 响应错误规范化', () => {
  const rejected = http.interceptors.response.handlers[0].rejected
  const mkErr = (status, detail) => ({
    response: { status, data: { detail } },
    message: 'boom'
  })

  it('网络错误 → NETWORK', async () => {
    await expect(rejected({ message: 'Network Error' })).rejects.toMatchObject({
      code: 'NETWORK', severity: 'block'
    })
  })

  it('422 → VALIDATION', async () => {
    await expect(rejected(mkErr(422, '字段缺失'))).rejects.toMatchObject({
      code: 'VALIDATION', severity: 'warn'
    })
  })

  it('404 → NOT_FOUND', async () => {
    await expect(rejected(mkErr(404, 'x'))).rejects.toMatchObject({ code: 'NOT_FOUND' })
  })

  it('5xx → SERVER', async () => {
    await expect(rejected(mkErr(500, '炸了'))).rejects.toMatchObject({ code: 'SERVER', severity: 'block' })
  })

  it('其他状态码 → HTTP_xxx', async () => {
    await expect(rejected(mkErr(403, '无权限'))).rejects.toMatchObject({ code: 'HTTP_403' })
  })

  it('401 且不在登录页 → 清 token 并跳转登录页', async () => {
    localStorage.setItem('token', 'jwt')
    localStorage.setItem('username', 'alice')
    // happy-dom 中 location.href 赋值会触发导航；直接断言其效果
    await expect(rejected(mkErr(401, '过期'))).rejects.toMatchObject({ code: 'HTTP_401' })
    expect(localStorage.getItem('token')).toBeNull()
    expect(location.pathname).toBe('/login')
  })
})
