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
          :subtitle="(it) => `${it.model_name} · ${it.base_url}`"
          @create="llmEditing = null" @select="(it) => llmEditing = it"
          @set-default="setLlmDefault" @remove="removeLlm" @rename="renameLlm" />
        <LlmConfigForm class="col-form" :initial-data="llmEditing" @submit="onLlmSubmit" />
      </div>
    </section>

    <section class="block">
      <div class="section-title">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>
        数据库配置
      </div>
      <div class="row">
        <ConfigList class="col-list" title="数据库配置" :items="store.dbList" :current-id="store.currentDbId"
          :subtitle="(it) => `${it.host}:${it.port}${it.default_schema ? ' · ' + it.default_schema : ' · 全部业务库'}`"
          @create="dbEditing = null" @select="(it) => dbEditing = it"
          @set-default="setDbDefault" @remove="removeDb" @rename="renameDb" />
        <DbConfigForm class="col-form" :initial-data="dbEditing" @submit="onDbSubmit" />
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useConfigStore } from '../stores/config.js'
import * as api from '../api/config.js'
import ConfigList from '../components/ConfigList.vue'
import LlmConfigForm from '../components/LlmConfigForm.vue'
import DbConfigForm from '../components/DbConfigForm.vue'

const store = useConfigStore()
const llmEditing = ref(null)
const dbEditing = ref(null)

onMounted(() => store.loadAll())

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
</style>
