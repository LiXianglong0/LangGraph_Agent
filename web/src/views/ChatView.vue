<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  deleteUserThread,
  downloadRagflowDocument,
  fetchThreadMessages,
  fetchUserThreads,
  sendChat,
} from '../api'
import { applyAgent, getAgent, selectedAgent } from '../stores/agents'
import {
  allTools,
  config,
  hasEnvKey,
  ragflow,
  ragflowPayload,
  threadId,
  toolNames,
  userId,
} from '../stores/settings'

const route = useRoute()
const router = useRouter()

const routeAgent = computed(() => {
  if (route.name !== 'agent-chat') return null
  return getAgent(String(route.params.id || ''))
})

const activeAgent = computed(() => routeAgent.value || selectedAgent.value)

/** 专用 Agent：工具清单固定，且默认不开知识库 */
const isDedicatedAgent = computed(() => {
  const a = activeAgent.value
  if (!a) return false
  return Array.isArray(a.tools) && a.tools.length > 0
})

const agentThreadPrefix = computed(() => {
  const id = activeAgent.value?.id
  return id ? `${id}-` : ''
})

function isAgentThread(tid) {
  const prefix = agentThreadPrefix.value
  return Boolean(prefix && String(tid || '').startsWith(prefix))
}

const loading = ref(false)
const error = ref('')
const tip = ref('')
const input = ref('')
const messages = ref([])
const listRef = ref(null)
const panelOpen = ref(true)
const threads = ref([])
const threadsLoading = ref(false)

/** 左侧历史：当前专用 Agent 会话置顶；专用模式下只展示本 Agent */
const displayThreads = computed(() => {
  const list = threads.value || []
  if (!routeAgent.value) return list
  const mine = []
  const others = []
  for (const t of list) {
    if (isAgentThread(t.thread_id)) mine.push(t)
    else others.push(t)
  }
  if (isDedicatedAgent.value) return mine
  return [...mine, ...others]
})

const lockedTools = computed(() => {
  if (!isDedicatedAgent.value) return null
  return new Set(activeAgent.value.tools || [])
})

async function refreshThreadList() {
  threadsLoading.value = true
  try {
    const data = await fetchUserThreads(userId.value)
    threads.value = data.threads || []
  } catch {
    threads.value = []
  } finally {
    threadsLoading.value = false
  }
}

async function loadHistory() {
  try {
    const data = await fetchThreadMessages(threadId.value)
    messages.value = (data.messages || []).map((m) => ({
      role: m.role,
      content: m.content,
      sources: [],
    }))
    await scrollBottom()
  } catch {
    /* 后端未就绪时保持空白 */
  }
}

function newSession() {
  const prefix = agentThreadPrefix.value || 'web-'
  threadId.value = `${prefix}${Math.random().toString(16).slice(2, 10)}`
  messages.value = []
  error.value = ''
  tip.value = ''
  if (route.name === 'agent-chat' && activeAgent.value?.id) {
    router.replace({
      name: 'agent-chat',
      params: { id: activeAgent.value.id },
      query: { t: threadId.value },
    })
  }
}

async function openThread(tid) {
  if (!tid || tid === threadId.value) return
  threadId.value = tid
  error.value = ''
  tip.value = ''
  await loadHistory()
}

async function removeThread(tid) {
  if (!tid || !confirm('从历史列表中移除该会话？')) return
  try {
    await deleteUserThread(userId.value, tid)
    if (threadId.value === tid) newSession()
    await refreshThreadList()
  } catch (e) {
    error.value = e.message || String(e)
  }
}

async function onUserBlur() {
  const uid = (userId.value || '').trim() || 'demo'
  userId.value = uid
  await refreshThreadList()
}

async function onSend() {
  const text = input.value.trim()
  if (!text || loading.value) return
  if (!config.api_key && !hasEnvKey.value) {
    error.value = '请先在「模型服务」配置智谱 API Key，或写入后端 .env'
    return
  }

  error.value = ''
  tip.value = ''
  messages.value.push({ role: 'user', content: text, sources: [] })
  input.value = ''
  loading.value = true
  await scrollBottom()

  try {
    const res = await sendChat({
      message: text,
      thread_id: threadId.value,
      user_id: userId.value,
      config: {
        api_key: config.api_key,
        model: config.model,
        base_url: config.base_url,
        temperature: Number(config.temperature),
        tool_names: toolNames.value,
        ragflow: ragflowPayload(),
        agent_id: activeAgent.value?.id || '',
        system_prompt: activeAgent.value?.systemPrompt || '',
      },
    })
    messages.value.push({
      role: 'assistant',
      content: res.answer,
      sources: res.sources || [],
    })
    await refreshThreadList()
  } catch (e) {
    const msg = e.message || String(e)
    error.value = msg
    messages.value.push({ role: 'assistant', content: `调用失败：${msg}`, sources: [] })
  } finally {
    loading.value = false
    await scrollBottom()
  }
}

async function onDownloadSource(src) {
  tip.value = ''
  error.value = ''
  try {
    tip.value = `正在下载：${src.name || src.document_id}`
    await downloadRagflowDocument({
      dataset_id: src.dataset_id,
      document_id: src.document_id,
      ragflow: ragflowPayload(),
    })
    tip.value = `已开始下载：${src.name || src.document_id}`
  } catch (e) {
    error.value = e.message || String(e)
  }
}

async function scrollBottom() {
  await nextTick()
  if (listRef.value) listRef.value.scrollTop = listRef.value.scrollHeight
}

function onKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    onSend()
  }
}

function formatTime(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

/** 专用 Agent 会话左侧名称固定显示 Agent 名称 */
function threadDisplayName(t) {
  if (isAgentThread(t?.thread_id) && activeAgent.value?.name) {
    const code = activeAgent.value.code || ''
    const name = activeAgent.value.name || ''
    return code ? `${code} · ${name}` : name
  }
  return t?.title || t?.thread_id || ''
}

watch(userId, () => {
  refreshThreadList()
})

watch(
  () => [route.name, route.params.id, activeAgent.value?.id],
  () => {
    if (route.name !== 'agent-chat') return
    applyAgent(String(route.params.id || activeAgent.value?.id || ''))
    // 专用 Agent 强制关闭知识库，并锁定工具勾选
    if (isDedicatedAgent.value) {
      ragflow.enabled = false
      const allow = lockedTools.value
      allTools.value.forEach((t) => {
        t.enabled = allow ? allow.has(t.name) : t.enabled
      })
    }
  },
  { immediate: true },
)

onMounted(async () => {
  if (route.name === 'agent-chat') {
    const id = String(route.params.id || '')
    if (!getAgent(id)) {
      router.replace('/agents')
      return
    }
    applyAgent(id)
    const q = typeof route.query.t === 'string' ? route.query.t : ''
    if (q) {
      threadId.value = q
      messages.value = []
    } else if (!isAgentThread(threadId.value)) {
      // 进入专用 Agent 时，若当前会话不属于本 Agent，自动开新会话置顶
      newSession()
    }
  }
  await refreshThreadList()
  await loadHistory()
})
</script>

<template>
  <div class="chat-page" :class="{ 'panel-collapsed': !panelOpen }">
    <aside class="history-rail">
      <div class="history-head">
        <label>当前用户</label>
        <input
          v-model="userId"
          type="text"
          placeholder="如 zhangsan"
          @blur="onUserBlur"
          @keyup.enter="onUserBlur"
        />
        <button class="ghost small" type="button" @click="newSession">新建对话</button>
      </div>
      <div class="history-list">
        <div v-if="routeAgent" class="history-section-label">
          {{ activeAgent.code }} 会话置顶
        </div>
        <div v-if="threadsLoading" class="history-empty">加载中…</div>
        <div v-else-if="!displayThreads.length" class="history-empty">
          暂无本 Agent 历史。发送消息后将出现在此列表顶部。
        </div>
        <button
          v-for="t in displayThreads"
          :key="t.thread_id"
          class="history-item"
          type="button"
          :class="{
            active: t.thread_id === threadId,
            pinned: isAgentThread(t.thread_id),
          }"
          @click="openThread(t.thread_id)"
        >
          <div class="history-title">
            <span v-if="isAgentThread(t.thread_id)" class="history-pin">置顶</span>
            {{ threadDisplayName(t) }}
          </div>
          <div class="history-meta">
            <span>{{ formatTime(t.updated_at) }}</span>
            <span class="history-del" @click.stop="removeThread(t.thread_id)">删除</span>
          </div>
        </button>
      </div>
    </aside>

    <section class="chat-main">
      <div class="chat-toolbar">
        <div class="session-row">
          <span class="session-tag">{{ activeAgent.code }} · {{ activeAgent.name }}</span>
          <span class="session-tag muted">会话 {{ threadId }}</span>
        </div>
        <div class="toolbar-actions">
          <RouterLink
            v-if="route.name === 'agent-chat'"
            class="ghost small link-btn"
            :to="`/agents/${activeAgent.id}`"
          >
            功能说明
          </RouterLink>
          <RouterLink class="ghost small link-btn" to="/agents">Agent 目录</RouterLink>
          <button class="ghost small" type="button" @click="panelOpen = !panelOpen">
            {{ panelOpen ? '收起参数' : '展开参数' }}
          </button>
        </div>
      </div>

      <div v-if="error" class="banner">{{ error }}</div>
      <div v-if="tip" class="banner tip">{{ tip }}</div>

      <div ref="listRef" class="messages">
        <div v-if="!messages.length" class="empty">
          正在使用 {{ activeAgent.code }} {{ activeAgent.name }}：{{ activeAgent.summary }}
          左侧可管理历史；右侧可调本轮参数。
        </div>
        <div v-for="(m, i) in messages" :key="i" class="msg" :class="m.role">
          <div class="role">{{ m.role === 'user' ? '你' : '助手' }}</div>
          <div class="content">{{ m.content }}</div>
          <div v-if="m.sources?.length" class="sources">
            <div class="sources-title">相关文件（与回答中的 [n] 对应，点击下载）</div>
            <button
              v-for="(s, j) in m.sources"
              :key="`${s.document_id}-${j}`"
              class="source-link"
              type="button"
              :title="s.document_id"
              @click="onDownloadSource(s)"
            >
              <span class="src-idx">[{{ s.index || j + 1 }}]</span>
              {{ s.name || s.document_id }}
              <span v-if="s.score != null" class="score">{{ Number(s.score).toFixed(3) }}</span>
            </button>
          </div>
        </div>
      </div>

      <div class="composer">
        <textarea
          v-model="input"
          rows="3"
          placeholder="输入问题，Enter 发送，Shift+Enter 换行"
          :disabled="loading"
          @keydown="onKeydown"
        />
        <button type="button" :disabled="loading" @click="onSend">
          {{ loading ? '思考中…' : '发送' }}
        </button>
      </div>
    </section>

    <aside v-show="panelOpen" class="chat-panel">
      <h3>本轮参数</h3>
      <p class="panel-hint">仅放对话时常用的灵活项；Key / 地址等请到配置菜单。</p>

      <label>模型</label>
      <input v-model="config.model" type="text" />

      <label>Temperature：{{ config.temperature }}</label>
      <input v-model.number="config.temperature" type="range" min="0" max="1" step="0.1" />

      <label class="tool-item" :class="{ locked: isDedicatedAgent && !activeAgent.ragEnabled }">
        <input
          v-model="ragflow.enabled"
          type="checkbox"
          :disabled="isDedicatedAgent && !activeAgent.ragEnabled"
        />
        <span>启用知识库检索</span>
        <span v-if="isDedicatedAgent && !activeAgent.ragEnabled" class="lock-hint">本 Agent 禁用</span>
      </label>

      <label>工具</label>
      <div class="tools">
        <label
          v-for="t in allTools"
          :key="t.name"
          class="tool-item"
          :class="{ locked: lockedTools && !lockedTools.has(t.name) }"
          :title="t.description"
        >
          <input
            v-model="t.enabled"
            type="checkbox"
            :disabled="Boolean(lockedTools) && !lockedTools.has(t.name)"
          />
          <span>{{ t.name }}</span>
        </label>
      </div>
    </aside>
  </div>
</template>
