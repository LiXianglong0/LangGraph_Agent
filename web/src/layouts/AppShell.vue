<script setup>
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { loadAgents } from '../stores/agents'
import { bootError, bootstrapSettings, bootReady } from '../stores/settings'

const route = useRoute()

const navPrimary = [
  { to: '/', label: '首页', name: 'home' },
  { to: '/chat', label: '智能对话', name: 'chat' },
  { to: '/agents', label: 'Agent', name: 'agents' },
]

const navSettings = [
  { to: '/settings/model', label: '模型服务', name: 'settings-model' },
  { to: '/settings/knowledge', label: '知识库', name: 'settings-knowledge' },
  { to: '/settings/system', label: '系统', name: 'settings-system' },
]

const pageTitle = computed(() => route.meta?.title || '控制台')

onMounted(async () => {
  if (!bootReady.value) await bootstrapSettings()
  await loadAgents()
})
</script>

<template>
  <div class="shell">
    <aside class="nav">
      <div class="brand">
        <div class="brand-mark" aria-hidden="true">LG</div>
        <div>
          <div class="brand-name">LangGraph</div>
          <div class="brand-sub">Agent Console</div>
        </div>
      </div>

      <nav class="nav-block">
        <div class="nav-label">工作台</div>
        <RouterLink
          v-for="item in navPrimary"
          :key="item.name"
          :to="item.to"
          class="nav-item"
          :class="{
            active:
              route.name === item.name ||
              (item.name === 'agents' && String(route.name || '').startsWith('agent')),
          }"
        >
          {{ item.label }}
        </RouterLink>
      </nav>

      <nav class="nav-block">
        <div class="nav-label">配置</div>
        <RouterLink
          v-for="item in navSettings"
          :key="item.name"
          :to="item.to"
          class="nav-item"
          :class="{ active: route.name === item.name }"
        >
          {{ item.label }}
        </RouterLink>
      </nav>

      <div class="nav-foot">
        <div class="nav-foot-title">可扩展模块</div>
        <div class="nav-foot-text">Agent 目录已开放；后续可继续扩展任务流与审计。</div>
      </div>
    </aside>

    <div class="workspace">
      <header class="topbar">
        <h1>{{ pageTitle }}</h1>
        <div class="topbar-meta">FastAPI · Vue · RAGFlow</div>
      </header>

      <div v-if="bootError" class="shell-banner">{{ bootError }}</div>

      <main class="page">
        <RouterView />
      </main>
    </div>
  </div>
</template>
