<template>
  <div class="config-page">
    <div class="page-header">
      <h2 class="h2">配置中心</h2>
      <p class="tip">所有参数由你填写并加密保存；下次进入自动回填。建议数据库使用<b>只读账号</b>。</p>
    </div>

    <section class="block">
      <div class="section-title">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a10 10 0 0 1 10 10c0 5.52-4.48 10-10 10S2 17.52 2 12 6.48 2 12 2z"/><path d="M8 12l2 2 4-4"/></svg>
        LLM 模型配置
      </div>
      <div class="row">
        <ConfigList class="col-list" title="LLM 模型配置" :items="store.llmList" :current-id="store.currentLlmId"
          :subtitle="(it) => `${it.model_name} · ${it.base_url}`" :readonly="!isAdmin"
          @create="llmEditing = null" @select="(it) => llmEditing = it"
          @set-default="setLlmDefault" @remove="removeLlm" @rename="renameLlm" />
        <LlmConfigForm v-if="isAdmin" class="col-form" :initial-data="llmEditing" @submit="onLlmSubmit" />
      </div>
    </section>

    <section class="block">
      <div class="section-title">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>
        数据库配置
      </div>
      <div class="row">
        <ConfigList class="col-list" title="数据库配置" :items="store.dbList" :current-id="store.currentDbId"
          :subtitle="(it) => `${it.host}:${it.port}${it.default_schema ? ' · ' + it.default_schema : ' · 全部业务库'}`" :readonly="!isAdmin"
          @create="dbEditing = null" @select="(it) => dbEditing = it"
          @set-default="setDbDefault" @remove="removeDb" @rename="renameDb" />
        <DbConfigForm v-if="isAdmin" class="col-form" :initial-data="dbEditing" @submit="onDbSubmit" />
      </div>
    </section>

    <!-- 用户管理（仅管理员） -->
    <section class="block" v-if="isAdmin">
      <div class="section-title">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
        用户管理
      </div>
      <div class="user-list">
        <div v-for="u in users" :key="u.id" class="user-row">
          <div class="user-info">
            <span class="user-name">{{ u.username }}</span>
            <span class="badge" :class="u.role">{{ u.role === 'admin' ? '管理员' : '普通用户' }}</span>
            <span v-if="u.username === myName" class="user-self">（我）</span>
          </div>
          <div class="user-ops">
            <button v-if="u.role === 'user'" class="mini-btn" @click="setRole(u, 'admin')">提升为管理员</button>
            <button v-else-if="u.username !== myName" class="mini-btn" @click="setRole(u, 'user')">降级</button>
            <span v-else class="user-self">不能修改自己的角色</span>
          </div>
        </div>
        <div v-if="!users.length" class="user-empty">暂无用户</div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useConfigStore } from '../stores/config.js'
import * as api from '../api/config.js'
import * as authApi from '../api/auth.js'
import ConfigList from '../components/ConfigList.vue'
import LlmConfigForm from '../components/LlmConfigForm.vue'
import DbConfigForm from '../components/DbConfigForm.vue'

const store = useConfigStore()
const llmEditing = ref(null)
const dbEditing = ref(null)
// 配置全局共享，仅管理员可修改
const isAdmin = localStorage.getItem('role') === 'admin'
const myName = localStorage.getItem('username') || ''

// 用户管理（仅管理员）
const users = ref([])

onMounted(() => { store.loadAll(); loadUsers() })

async function loadUsers() {
  if (!isAdmin) return
  try { users.value = await authApi.listUsers() } catch (_) { users.value = [] }
}

async function setRole(u, role) {
  try {
    await authApi.setUserRole(u.id, role)
    u.role = role
  } catch (err) { alert('操作失败：' + (err.suggestion || err.message)) }
}

// 保存后：用返回的 view 更新编辑态（新建→变成编辑态，避免重复新建），并刷新列表
async function onLlmSubmit(form) {
  try {
    // 合并编辑态保留字段：默认标记（表单没有该字段，编辑默认项时不能丢）
    const payload = { ...form, is_default: llmEditing.value?.is_default || false }
    const view = await api.saveLlm(payload)
    llmEditing.value = view
    await store.loadAll()
    // 保存后测试连接（后端对掩码 key 会取真实 key）
    try {
      await api.testLlm({ ...view, api_key: view.api_key_masked || '' })
      alert('✅ 配置已保存，连接测试通过')
    } catch (err) {
      alert('配置已保存，但连接测试失败：\n' + (err.suggestion || err.message || JSON.stringify(err)))
    }
  } catch (err) {
    alert('保存失败：' + (err.suggestion || err.message || JSON.stringify(err)))
  }
}

async function onDbSubmit(form) {
  try {
    // 合并编辑态保留字段：charset / default_schema（表单没有这些字段）
    const payload = {
      ...form,
      charset: dbEditing.value?.charset || 'utf8mb4',
      default_schema: dbEditing.value?.default_schema ?? null
    }
    const view = await api.saveDb(payload)
    dbEditing.value = view
    await store.loadAll()
    try {
      await api.testDb({ ...view, password: view.password_masked || '' })
      alert('✅ 配置已保存，连接测试通过')
    } catch (err) {
      alert('配置已保存，但连接测试失败：\n' + (err.suggestion || err.message || JSON.stringify(err)))
    }
  } catch (err) {
    alert('保存失败：' + (err.suggestion || err.message || JSON.stringify(err)))
  }
}

// 设默认：复用 save 接口，带脱敏 key/密码，后端 upsert 时保留原密文、只改 is_default
async function setLlmDefault(it) { await api.saveLlm({ ...it, is_default: true }); await store.loadAll() }
async function setDbDefault(it)  { await api.saveDb({ ...it, is_default: true });  await store.loadAll() }

async function removeLlm(it) { await api.removeLlm(it.id); if (llmEditing.value?.id === it.id) llmEditing.value = null; await store.loadAll() }
async function removeDb(it)  { await api.removeDb(it.id);  if (dbEditing.value?.id === it.id)  dbEditing.value = null;  await store.loadAll() }

// 重命名：复用 save 接口（带脱敏 key/密码，后端保留原密文，只改 name）
async function renameLlm(it, name) { try { await api.saveLlm({ ...it, name }); await store.loadAll() } catch (err) { alert('重命名失败：' + (err.suggestion || err.message)) } }
async function renameDb(it, name)  { try { await api.saveDb({ ...it, name });  await store.loadAll() } catch (err) { alert('重命名失败：' + (err.suggestion || err.message)) } }
</script>

<style scoped>
.config-page { max-width: 960px; margin: 0 auto; }

.page-header { margin-bottom: 24px; }
.h2 {
  margin: 0 0 6px;
  font-size: 22px; font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.02em;
}
.tip {
  margin: 0;
  color: var(--text-tertiary);
  font-size: 13px; line-height: 1.6;
}
.tip b { color: var(--text-secondary); font-weight: 600; }

.block { margin-bottom: 28px; }
.section-title {
  display: flex; align-items: center; gap: 8px;
  font-size: 15px; font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-light);
}
.section-title svg { color: var(--brand-start); }

.row { display: grid; grid-template-columns: 340px 1fr; gap: 16px; align-items: start; }
@media (max-width: 820px) { .row { grid-template-columns: 1fr; } }

/* ── 用户管理 ── */
.user-list {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-primary);
  padding: 8px;
  box-shadow: var(--shadow-sm);
}
.user-row {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 10px 12px; border-radius: var(--radius-sm);
}
.user-row:hover { background: var(--bg-tertiary); }
.user-info { display: flex; align-items: center; gap: 8px; min-width: 0; }
.user-name { font-weight: 600; font-size: 13px; color: var(--text-primary); }
.user-self { font-size: 12px; color: var(--text-tertiary); }
.user-list .badge {
  font-size: 11px; padding: 2px 8px; border-radius: var(--radius-xl); font-weight: 500; flex: none;
}
.user-list .badge.admin { background: rgba(0, 0, 0, 0.08); color: var(--brand-start); }
.user-list .badge.user { background: var(--bg-tertiary); color: var(--text-secondary); }
.user-ops { display: flex; align-items: center; gap: 8px; flex: none; }
.mini-btn {
  background: none; border: 1px solid var(--border-color);
  border-radius: var(--radius-sm); padding: 5px 10px;
  font-size: 12px; color: var(--text-secondary); cursor: pointer;
  transition: var(--transition);
}
.mini-btn:hover { border-color: var(--brand-start); color: var(--brand-start); }
.user-empty { color: var(--text-tertiary); font-size: 13px; padding: 12px; text-align: center; }
</style>
