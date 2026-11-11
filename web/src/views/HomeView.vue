<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { config, hasEnvKey, ragflow } from '../stores/settings'

const router = useRouter()
const apiOk = ref(null)
const checking = ref(false)

const ragReady = computed(
  () =>
    Boolean(ragflow.enabled) &&
    Boolean(ragflow.base_url?.trim()) &&
    Boolean(ragflow.api_key?.trim()) &&
    Boolean(ragflow.dataset_ids_text?.trim()),
)

const modelReady = computed(() => Boolean(config.api_key || hasEnvKey.value))

async function checkApi() {
  checking.value = true
  try {
    const res = await fetch('/api/health')
    apiOk.value = res.ok
  } catch {
    apiOk.value = false
  } finally {
    checking.value = false
  }
}

onMounted(checkApi)
</script>

<template>
  <div class="home">
    <section class="hero-panel">
      <p class="eyebrow">工作台概览</p>
      <h2>用统一控制台管理对话、模型与知识库</h2>
      <p class="lead">
        对话在独立页面进行；稳定配置进入左侧菜单。后续扩展功能可按模块继续挂载。
      </p>
      <div class="hero-actions">
        <button type="button" @click="router.push('/chat')">进入智能对话</button>
        <button class="ghost" type="button" @click="router.push('/settings/knowledge')">
          配置知识库
        </button>
      </div>
    </section>

    <section class="status-grid">
      <article class="status-card">
        <div class="status-kicker">Agent API</div>
        <div class="status-value" :class="apiOk === null ? '' : apiOk ? 'ok' : 'bad'">
          {{ apiOk === null ? '检测中' : apiOk ? '运行中' : '未连接' }}
        </div>
        <p>默认端口 8001。后端异常时对话不可用。</p>
        <button class="ghost small" type="button" :disabled="checking" @click="checkApi">
          {{ checking ? '检测中…' : '重新检测' }}
        </button>
      </article>

      <article class="status-card">
        <div class="status-kicker">模型服务</div>
        <div class="status-value" :class="modelReady ? 'ok' : 'warn'">
          {{ modelReady ? '已就绪' : '待配置' }}
        </div>
        <p>当前模型：{{ config.model || '—' }}</p>
        <button class="ghost small" type="button" @click="router.push('/settings/model')">
          打开模型配置
        </button>
      </article>

      <article class="status-card">
        <div class="status-kicker">知识库</div>
        <div class="status-value" :class="ragReady ? 'ok' : 'warn'">
          {{ ragReady ? '已启用' : '未完整配置' }}
        </div>
        <p>{{ ragflow.base_url || '未填写 RAGFlow 地址' }}</p>
        <button class="ghost small" type="button" @click="router.push('/settings/knowledge')">
          打开知识库配置
        </button>
      </article>
    </section>

    <section class="module-grid">
      <h3>功能入口</h3>
      <div class="modules">
        <button class="module" type="button" @click="router.push('/agents')">
          <strong>Agent</strong>
          <span>浏览并选用助手预设</span>
        </button>
        <button class="module" type="button" @click="router.push('/chat')">
          <strong>智能对话</strong>
          <span>问答、工具调用、知识库引用与源文件下载</span>
        </button>
        <button class="module" type="button" @click="router.push('/settings/model')">
          <strong>模型服务</strong>
          <span>API Key、Base URL、默认模型等稳定项</span>
        </button>
        <button class="module" type="button" @click="router.push('/settings/knowledge')">
          <strong>知识库</strong>
          <span>RAGFlow 地址、Dataset、检索参数</span>
        </button>
        <button class="module muted" type="button" disabled>
          <strong>更多模块</strong>
          <span>预留：多 Agent、任务编排、审计日志…</span>
        </button>
      </div>
    </section>
  </div>
</template>
