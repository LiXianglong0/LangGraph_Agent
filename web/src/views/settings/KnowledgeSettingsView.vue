<script setup>
import { ref } from 'vue'
import { pingRagflow, saveConfig } from '../../api'
import {
  hasEnvKey,
  config,
  persistUiConfig,
  ragflow,
  ragflowPayload,
} from '../../stores/settings'

const pinging = ref(false)
const saving = ref(false)
const tip = ref('')
const error = ref('')

async function onPing() {
  pinging.value = true
  tip.value = ''
  error.value = ''
  try {
    const res = await pingRagflow(ragflowPayload())
    tip.value = res.ok
      ? `连通正常：${res.preview || 'ok'}`
      : `探测失败：${res.message || res.preview || 'unknown'}`
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    pinging.value = false
  }
}

async function onSave() {
  saving.value = true
  tip.value = ''
  error.value = ''
  try {
    // 探测用临时开启，保存时按页面勾选为准
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
</script>

<template>
  <div class="settings-page">
    <header class="settings-head">
      <h2>知识库（RAGFlow）</h2>
      <p>连接独立部署的 RAGFlow。Dataset ID 在知识库地址栏末尾复制；对话页可一键开关检索。</p>
    </header>

    <div v-if="error" class="banner">{{ error }}</div>
    <div v-if="tip" class="banner tip">{{ tip }}</div>

    <section class="card-form">
      <label class="tool-item">
        <input v-model="ragflow.enabled" type="checkbox" />
        <span>默认启用 knowledge_search</span>
      </label>

      <label>RAGFlow 地址</label>
      <input v-model="ragflow.base_url" type="text" placeholder="http://127.0.0.1:8088" />

      <label>RAGFlow API Key</label>
      <input v-model="ragflow.api_key" type="password" />

      <label>Dataset IDs（逗号分隔）</label>
      <input v-model="ragflow.dataset_ids_text" type="text" placeholder="dataset_id_1,dataset_id_2" />

      <label>page_size</label>
      <input v-model.number="ragflow.page_size" type="number" min="1" max="30" />

      <label>similarity_threshold</label>
      <input
        v-model.number="ragflow.similarity_threshold"
        type="number"
        min="0"
        max="1"
        step="0.05"
      />

      <div class="form-actions">
        <button class="ghost" type="button" :disabled="pinging" @click="onPing">
          {{ pinging ? '探测中…' : '探测 RAGFlow' }}
        </button>
        <button type="button" :disabled="saving" @click="onSave">
          {{ saving ? '同步中…' : '同步到 .env' }}
        </button>
      </div>
    </section>
  </div>
</template>
