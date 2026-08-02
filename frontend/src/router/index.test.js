import { describe, it, expect, beforeEach } from 'vitest'
import router from './index.js'

// 守卫逻辑测试：未登录只能访问 /login，已登录访问 /login 会跳转 /chat。
// 注意 router 是模块级单例，同路径重复导航不会触发守卫，因此测试按导航链顺序执行。
describe('router 登录守卫', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('无 token 访问 /chat → 重定向 /login', async () => {
    await router.push('/chat')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('无 token 访问 /config → 重定向 /login', async () => {
    await router.push('/config')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('有 token 访问 /chat → 放行', async () => {
    localStorage.setItem('token', 'jwt')
    await router.push('/chat')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/chat')
  })

  it('有 token 访问 /login → 重定向 /chat（从 /chat 导航触发守卫）', async () => {
    localStorage.setItem('token', 'jwt')
    await router.push('/login')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/chat')
  })
})
