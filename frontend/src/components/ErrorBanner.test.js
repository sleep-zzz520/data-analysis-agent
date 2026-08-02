import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ErrorBanner from './ErrorBanner.vue'

describe('ErrorBanner', () => {
  it('error 为空时不渲染', () => {
    const w = mount(ErrorBanner, { props: { error: '' } })
    expect(w.find('.error-banner').exists()).toBe(false)
  })

  it('渲染错误文本', () => {
    const w = mount(ErrorBanner, { props: { error: '余额不足' } })
    expect(w.text()).toContain('余额不足')
  })

  it('点击关闭按钮触发 dismiss 事件', async () => {
    const w = mount(ErrorBanner, { props: { error: '出错了' } })
    await w.find('.close-btn').trigger('click')
    expect(w.emitted('dismiss')).toHaveLength(1)
  })

  it('传入 onRetry 时显示重试按钮并触发回调', async () => {
    const onRetry = vi.fn()
    const w = mount(ErrorBanner, { props: { error: '出错了', onRetry } })
    const btn = w.find('.retry-btn')
    expect(btn.exists()).toBe(true)
    await btn.trigger('click')
    expect(onRetry).toHaveBeenCalledOnce()
  })

  it('未传 onRetry 时不显示重试按钮', () => {
    const w = mount(ErrorBanner, { props: { error: '出错了' } })
    expect(w.find('.retry-btn').exists()).toBe(false)
  })
})
