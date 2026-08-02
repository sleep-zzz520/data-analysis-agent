import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('../api/config.js', () => ({
  listLlm: vi.fn(),
  listDb: vi.fn()
}))

import * as cfgApi from '../api/config.js'
import { useConfigStore } from './config.js'

const SID_KEY = 'da_session_id'

describe('config store', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  it('loadAll 填充列表并选中默认配置', async () => {
    cfgApi.listLlm.mockResolvedValue([
      { id: 1, name: 'a', is_default: false },
      { id: 2, name: 'b', is_default: true }
    ])
    cfgApi.listDb.mockResolvedValue([{ id: 9, name: '订单库', is_default: true }])
    const store = useConfigStore()
    await store.loadAll()
    expect(store.llmList).toHaveLength(2)
    expect(store.currentLlmId).toBe(2)
    expect(store.currentDbId).toBe(9)
    expect(store.ready).toBe(true)
  })

  it('无默认配置时选中第一个', async () => {
    cfgApi.listLlm.mockResolvedValue([{ id: 5, name: 'a' }])
    cfgApi.listDb.mockResolvedValue([{ id: 6, name: 'b' }])
    const store = useConfigStore()
    await store.loadAll()
    expect(store.currentLlmId).toBe(5)
    expect(store.currentDbId).toBe(6)
  })

  it('currentLlm/currentDb getter', async () => {
    cfgApi.listLlm.mockResolvedValue([{ id: 1, name: 'qwen' }])
    cfgApi.listDb.mockResolvedValue([{ id: 2, name: 'db' }])
    const store = useConfigStore()
    await store.loadAll()
    expect(store.currentLlm.name).toBe('qwen')
    expect(store.currentDb.name).toBe('db')
  })

  it('newSession / setSession 更新并持久化 sessionId', () => {
    const store = useConfigStore()
    store.newSession()
    expect(localStorage.getItem(SID_KEY)).toBe(store.sessionId)
    store.setSession('fixed-id')
    expect(store.sessionId).toBe('fixed-id')
    expect(localStorage.getItem(SID_KEY)).toBe('fixed-id')
  })
})
