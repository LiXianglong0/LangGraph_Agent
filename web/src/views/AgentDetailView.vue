<script setup>
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MermaidBlock from '../components/MermaidBlock.vue'
import { applyAgent, getAgent, selectedAgentId } from '../stores/agents'

const route = useRoute()
const router = useRouter()

const agent = computed(() => getAgent(String(route.params.id || '')))

onMounted(() => {
  if (!agent.value) router.replace('/agents')
})

function enterUse() {
  if (!agent.value) return
  applyAgent(agent.value.id)
  // 每个 Agent 独立会话前缀，避免串上下文
  const tid = `${agent.value.id}-${Math.random().toString(16).slice(2, 8)}`
  router.push({ name: 'agent-chat', params: { id: agent.value.id }, query: { t: tid } })
}
</script>

<template>
  <div v-if="agent" class="agent-detail">
    <button class="ghost small back" type="button" @click="router.push('/agents')">
      ← 返回目录
    </button>

    <header class="agent-detail-head">
      <div>
        <div class="agent-code">{{ agent.code }}</div>
        <h2>{{ agent.name }}</h2>
        <p class="lead">{{ agent.summary }}</p>
      </div>
      <div class="agent-detail-actions">
        <span v-if="agent.id === selectedAgentId" class="agent-badge">当前选用</span>
        <button type="button" @click="enterUse">选择使用 · 进入操作</button>
      </div>
    </header>

    <section class="agent-section">
      <h3>功能说明</h3>
      <p class="agent-desc">{{ agent.description }}</p>
      <ul class="feature-list">
        <li v-for="(f, i) in agent.features" :key="i">{{ f }}</li>
      </ul>
    </section>

    <section class="agent-section">
      <h3>能力配置</h3>
      <div class="agent-meta block">
        <div>
          <strong>工具</strong>
          <span>{{ agent.tools === null ? '全部本地工具' : agent.tools.join(', ') }}</span>
        </div>
        <div>
          <strong>知识库 RAG</strong>
          <span>{{ agent.ragEnabled ? '默认开启' : '默认关闭' }}</span>
        </div>
        <div>
          <strong>标签</strong>
          <span>{{ agent.tags.join(' · ') }}</span>
        </div>
      </div>
    </section>

    <section class="agent-section">
      <h3>工作流程图</h3>
      <p class="panel-hint">进入使用后，对话将按此流程调用模型与工具。</p>
      <MermaidBlock :code="agent.flowchart" />
    </section>

    <div class="agent-detail-foot">
      <button type="button" @click="enterUse">选择使用 · 进入 {{ agent.code }}</button>
      <button class="ghost" type="button" @click="router.push('/agents')">返回目录</button>
    </div>
  </div>
</template>
