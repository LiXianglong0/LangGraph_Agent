/**
 * Agent 目录：优先从后端 /api/agents（数据库）加载，失败则用本地兜底。
 */
import { computed, ref, watch } from 'vue'
import { fetchAgents } from '../api'
import { allTools, persistUiConfig, ragflow } from './settings'

const AGENT_KEY = 'langgraph_selected_agent'

/** 网络失败时的兜底目录 */
const FALLBACK_CATALOG = [
  {
    id: 'general',
    code: 'AGENT1',
    name: '通用助手',
    summary: '日常问答、多工具协作的通用对话入口。',
    description: '面向一般问答与任务协助。',
    features: ['多轮对话', '本地工具'],
    tags: ['默认'],
    tools: null,
    ragEnabled: false,
    systemPrompt: '你是通用助手，回答简洁可执行。',
    flowchart: `flowchart TD
  U[用户] --> A[通用助手]
  A --> R[回复]`,
  },
]

export const agentCatalog = ref([...FALLBACK_CATALOG])
export const agentsLoading = ref(false)
export const agentsError = ref('')

const storedId = localStorage.getItem(AGENT_KEY) || 'general'
export const selectedAgentId = ref(storedId)

export const selectedAgent = computed(() => {
  const list = agentCatalog.value
  return list.find((a) => a.id === selectedAgentId.value) || list[0] || FALLBACK_CATALOG[0]
})

watch(selectedAgentId, (id) => {
  localStorage.setItem(AGENT_KEY, id)
})

export function getAgent(id) {
  return agentCatalog.value.find((a) => a.id === id) || null
}

/** 启动 / 进入 Agent 页时拉取目录 */
export async function loadAgents() {
  agentsLoading.value = true
  agentsError.value = ''
  try {
    const data = await fetchAgents()
    const list = data.agents || []
    if (list.length) {
      agentCatalog.value = list
      if (!list.some((a) => a.id === selectedAgentId.value)) {
        selectedAgentId.value = list[0].id
      }
    }
  } catch (e) {
    agentsError.value = e.message || String(e)
    if (!agentCatalog.value.length) {
      agentCatalog.value = [...FALLBACK_CATALOG]
    }
  } finally {
    agentsLoading.value = false
  }
}

export function applyAgent(agentId) {
  const agent = getAgent(agentId)
  if (!agent) return false

  selectedAgentId.value = agent.id
  ragflow.enabled = Boolean(agent.ragEnabled)

  if (agent.tools === null || agent.tools === undefined) {
    allTools.value.forEach((t) => {
      t.enabled = true
    })
  } else {
    const allow = new Set(agent.tools)
    allTools.value.forEach((t) => {
      t.enabled = allow.has(t.name)
    })
  }

  persistUiConfig()
  return true
}

/** @deprecated 兼容旧引用 */
export const AGENT_CATALOG = new Proxy([], {
  get(_t, prop) {
    if (prop === Symbol.iterator) {
      return agentCatalog.value[Symbol.iterator].bind(agentCatalog.value)
    }
    if (prop === 'length') return agentCatalog.value.length
    if (prop === 'find') return agentCatalog.value.find.bind(agentCatalog.value)
    if (prop === 'map') return agentCatalog.value.map.bind(agentCatalog.value)
    if (prop === 'some') return agentCatalog.value.some.bind(agentCatalog.value)
    if (typeof prop === 'string' && /^\d+$/.test(prop)) {
      return agentCatalog.value[Number(prop)]
    }
    const v = agentCatalog.value[prop]
    return typeof v === 'function' ? v.bind(agentCatalog.value) : v
  },
})
