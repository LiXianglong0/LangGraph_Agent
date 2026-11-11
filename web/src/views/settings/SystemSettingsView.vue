<script setup>
import { ref } from 'vue'
import { saveConfig } from '../../api'
import {
  config,
  hasEnvKey,
  persistUiConfig,
  ragflowPayload,
  threadId,
} from '../../stores/settings'

const saving = ref(false)
const tip = ref('')
const error = ref('')

async function syncAll() {
  saving.value = true
  tip.value = ''
  error.value = ''
  try {
    const res = await saveConfig({
      api_key: config.api_key,
      model: config.model,
      base_url: config.base_url,
      temperature: Number(config.temperature),
      ragflow: ragflowPayload(),
    })
    tip.value = res.message || '已同步到 .env'
    persistUiConfig()
    if (config.api_key) hasEnvKey.value = true
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    saving.value = false
  }
}

function clearLocalCache() {
  localStorage.removeItem('langgraph_ui_config')
  tip.value = '已清除浏览器本地配置缓存（刷新后将重新从 .env / 默认值加载）'
}
</script>

<template>
  <div class="settings-page">
    <header class="settings-head">
      <h2>系统</h2>
      <p>环境同步、本地缓存与扩展说明。适合运维向操作，不放在对话页。</p>
    </header>

    <div v-if="error" class="banner">{{ error }}</div>
    <div v-if="tip" class="banner tip">{{ tip }}</div>

    <section class="card-form">
      <h3>环境同步</h3>
      <p class="panel-hint">
        将当前模型与知识库配置写入项目根目录 <code>.env</code>，供后端进程默认加载。
        API Key 留空则不覆盖已有值。
      </p>
      <div class="form-actions">
        <button type="button" :disabled="saving" @click="syncAll">
          {{ saving ? '同步中…' : '同步全部到 .env' }}
        </button>
        <button class="ghost" type="button" @click="clearLocalCache">清除本地缓存</button>
      </div>
    </section>

    <section class="card-form">
      <h3>运行信息</h3>
      <dl class="kv">
        <div><dt>当前会话 ID</dt><dd>{{ threadId }}</dd></div>
        <div><dt>默认模型</dt><dd>{{ config.model }}</dd></div>
        <div><dt>.env API Key</dt><dd>{{ hasEnvKey ? '已配置' : '未配置' }}</dd></div>
        <div><dt>前端</dt><dd>Vue 3 + Vite · 端口 5173</dd></div>
        <div><dt>后端</dt><dd>FastAPI · 端口 8001</dd></div>
      </dl>
    </section>

    <section class="card-form">
      <h3>后续扩展建议</h3>
      <ul class="bullets">
        <li>多 Agent / 编排：在「工作台」新增菜单与独立页面</li>
        <li>任务与审计：会话导出、调用日志、权限角色</li>
        <li>连接器：除 RAGFlow 外可再挂搜索、数据库、企业内部 API</li>
      </ul>
    </section>
  </div>
</template>
