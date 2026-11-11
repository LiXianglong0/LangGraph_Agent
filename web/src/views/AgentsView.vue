<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  agentCatalog,
  agentsError,
  agentsLoading,
  loadAgents,
  selectedAgentId,
} from '../stores/agents'

const router = useRouter()

function openDetail(id) {
  router.push(`/agents/${id}`)
}

onMounted(loadAgents)
</script>

<template>
  <div class="agents-page">
    <section class="agents-intro">
      <p class="eyebrow">Agent 目录</p>
      <h2>浏览 Agent</h2>
      <p class="lead">
        每个 Agent 有独立功能说明与流程图（保存在数据库）。点进详情查看配置，再选择「进入使用」开始操作。
      </p>
      <p v-if="agentsLoading" class="agents-current">加载中…</p>
      <p v-else-if="agentsError" class="banner">目录加载失败，已用本地兜底：{{ agentsError }}</p>
    </section>

    <div class="agent-grid">
      <article
        v-for="a in agentCatalog"
        :key="a.id"
        class="agent-card clickable"
        :class="{ active: a.id === selectedAgentId }"
        role="button"
        tabindex="0"
        @click="openDetail(a.id)"
        @keyup.enter="openDetail(a.id)"
      >
        <div class="agent-card-top">
          <div>
            <div class="agent-code">{{ a.code }}</div>
            <h3>{{ a.name }}</h3>
          </div>
          <span v-if="a.id === selectedAgentId" class="agent-badge">使用中</span>
        </div>
        <p class="agent-desc">{{ a.summary }}</p>
        <div class="agent-tags">
          <span v-for="tag in a.tags" :key="tag" class="agent-tag">{{ tag }}</span>
        </div>
        <div class="agent-actions">
          <button type="button" @click.stop="openDetail(a.id)">查看详情与流程</button>
        </div>
      </article>
    </div>
  </div>
</template>
