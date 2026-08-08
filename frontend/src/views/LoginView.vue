<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-brand">
        <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
        数据分析 Agent
      </div>
      <h2 class="login-title">{{ isRegister ? '注册账号' : '登录' }}</h2>
      <p v-if="isRegister" class="login-tip">
        新注册账号为<b>普通用户</b>；系统<b>首个注册</b>的账号自动成为<b>管理员</b>（可管理全局配置与用户）。
      </p>
      <p v-if="!isRegister && showTestCredentials" class="login-tip test-credentials">
        测试管理员：<b>admin</b> / <b>admin1234</b>
      </p>
      <form @submit.prevent="submit">
        <div class="field">
          <label>用户名</label>
          <input v-model="username" placeholder="至少 2 位" required />
        </div>
        <div class="field">
          <label>密码</label>
          <input v-model="password" type="password" placeholder="至少 4 位" required />
        </div>
        <p v-if="error" class="login-error">{{ error }}</p>
        <button type="submit" class="login-btn" :disabled="loading">
          {{ loading ? '请稍候...' : (isRegister ? '注册并登录' : '登录') }}
        </button>
      </form>
      <p class="login-switch">
        {{ isRegister ? '已有账号？' : '还没有账号？' }}
        <a href="#" @click.prevent="isRegister = !isRegister">{{ isRegister ? '去登录' : '去注册' }}</a>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import * as authApi from '../api/auth.js'

const router = useRouter()
const isRegister = ref(false)
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)
const showTestCredentials = import.meta.env.DEV

async function submit() {
  if (username.value.trim().length < 2 || password.value.length < 4) {
    error.value = '用户名至少 2 位，密码至少 4 位'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const res = isRegister.value
      ? await authApi.register(username.value.trim(), password.value)
      : await authApi.login(username.value.trim(), password.value)
    localStorage.setItem('token', res.token)
    localStorage.setItem('username', res.username)
    localStorage.setItem('role', res.role || 'user')
    router.push('/chat')
  } catch (err) {
    error.value = err.suggestion || err.message || '操作失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex; align-items: center; justify-content: center;
  background: var(--bg-secondary);
}
.login-card {
  width: 360px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: 32px;
  box-shadow: var(--shadow-lg);
}
.login-brand {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  font-size: 16px; font-weight: 700; color: var(--brand-start);
  margin-bottom: 20px;
}
.login-title { font-size: 18px; font-weight: 700; margin-bottom: 16px; }
.login-tip {
  font-size: 12px; color: var(--text-tertiary);
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
  padding: 8px 10px; margin-bottom: 14px; line-height: 1.6;
}
.login-tip b { color: var(--text-secondary); }
.field { margin-bottom: 14px; }
.field label { display: block; font-size: 13px; font-weight: 500; color: var(--text-secondary); margin-bottom: 6px; }
.field input {
  width: 100%; padding: 9px 12px;
  border: 1px solid var(--border-color); border-radius: var(--radius-sm);
  font-size: 14px; color: var(--text-primary);
}
.field input:focus { outline: none; border-color: var(--brand-start); }
.login-error { color: #EF4444; font-size: 13px; margin-bottom: 10px; }
.login-btn {
  width: 100%; padding: 10px;
  background: var(--brand-gradient); color: #fff; border: none;
  border-radius: var(--radius-sm); font-size: 14px; font-weight: 600;
  cursor: pointer; transition: var(--transition);
}
.login-btn:hover:not(:disabled) { opacity: 0.92; }
.login-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.login-switch { margin-top: 14px; font-size: 13px; color: var(--text-tertiary); text-align: center; }
.login-switch a { color: var(--brand-start); text-decoration: none; font-weight: 500; }
</style>
