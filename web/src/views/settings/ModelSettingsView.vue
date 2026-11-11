<script setup>
import { ref } from 'vue'
import { saveConfig } from '../../api'
import {
  config,
  hasEnvKey,
  ragflowPayload,
  persistUiConfig,
} from '../../stores/settings'

const saving = ref(false)
const tip = ref('')
const error = ref('')

async function onSave() {
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
</script>

<template>
  <div class="settings-page">
    <header class="settings-head">
      <h2>模型服务</h2>
      <p>API Key、Base URL、默认模型等相对稳定的连接参数。对话页仍可临时改模型与温度。</p>
    </header>

    <div v-if="error" class="banner">{{ error }}</div>
    <div v-if="tip" class="banner tip">{{ tip }}</div>

    <section class="card-form">
      <label>智谱 API Key</label>
      <input
        v-model="config.api_key"
        type="password"
        :placeholder="hasEnvKey ? '已配置 .env，可留空不覆盖' : '请输入 API Key'"
      />

      <label>模型 Base URL</label>
      <input v-model="config.base_url" type="text" />

      <label>默认模型</label>
      <input v-model="config.model" type="text" />

      <label>默认 Temperature：{{ config.temperature }}</label>
      <input v-model.number="config.temperature" type="range" min="0" max="1" step="0.1" />

      <div class="form-actions">
        <button type="button" :disabled="saving" @click="onSave">
          {{ saving ? '同步中…' : '同步到 .env' }}
        </button>
      </div>
    </section>
  </div>
</template>
