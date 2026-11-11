/**
 * 全局配置与会话状态（localStorage 持久化，供多页面共享）。
 */
import { computed, reactive, ref, watch } from 'vue'
import { fetchDefaults } from '../api'

const THREAD_KEY = 'langgraph_thread_id'
const USER_KEY = 'langgraph_user_id'
const UI_CONFIG_KEY = 'langgraph_ui_config'

export const config = reactive({
  api_key: '',
  model: 'glm-4-flash',
  base_url: 'https://open.bigmodel.cn/api/paas/v4/',
  temperature: 0.7,
})

export const ragflow = reactive({
  enabled: false,
  base_url: 'http://127.0.0.1:8088',
  api_key: '',
  dataset_ids_text: '',
  page_size: 6,
  similarity_threshold: 0.2,
})

export const allTools = ref([])
export const hasEnvKey = ref(false)
export const threadId = ref(localStorage.getItem(THREAD_KEY) || 'web-session')
export const userId = ref(localStorage.getItem(USER_KEY) || 'demo')
export const bootError = ref('')
export const bootReady = ref(false)

const persistReady = ref(false)

export const toolNames = computed(() =>
  allTools.value.filter((t) => t.enabled).map((t) => t.name),
)

export const datasetIds = computed(() =>
  ragflow.dataset_ids_text
    .split(/[,，\s]+/)
    .map((s) => s.trim())
    .filter(Boolean),
)

export function ragflowPayload() {
  return {
    enabled: ragflow.enabled,
    base_url: ragflow.base_url,
    api_key: ragflow.api_key,
    dataset_ids: datasetIds.value,
    page_size: Number(ragflow.page_size) || 6,
    similarity_threshold: Number(ragflow.similarity_threshold) || 0.2,
  }
}

function readStoredUiConfig() {
  try {
    const raw = localStorage.getItem(UI_CONFIG_KEY)
    if (!raw) return null
    const data = JSON.parse(raw)
    return data && typeof data === 'object' ? data : null
  } catch {
    return null
  }
}

export function persistUiConfig() {
  if (!persistReady.value) return
  localStorage.setItem(
    UI_CONFIG_KEY,
    JSON.stringify({
      config: { ...config },
      ragflow: { ...ragflow },
      threadId: threadId.value,
      userId: userId.value,
      tools: Object.fromEntries(allTools.value.map((t) => [t.name, Boolean(t.enabled)])),
    }),
  )
  localStorage.setItem(THREAD_KEY, threadId.value || 'web-session')
  localStorage.setItem(USER_KEY, (userId.value || 'demo').trim() || 'demo')
}

function applyStoredUiConfig(stored) {
  if (!stored) return
  if (stored.config) Object.assign(config, stored.config)
  if (stored.ragflow) Object.assign(ragflow, stored.ragflow)
  if (stored.threadId) threadId.value = stored.threadId
  if (stored.userId) userId.value = stored.userId
}

/** 应用启动时加载一次 */
export async function bootstrapSettings() {
  bootError.value = ''
  const stored = readStoredUiConfig()
  applyStoredUiConfig(stored)

  try {
    const data = await fetchDefaults()
    hasEnvKey.value = data.has_env_api_key
    const toolEnableMap = stored?.tools || {}
    allTools.value = (data.tools || []).map((t) => {
      let enabled = true
      if (Object.prototype.hasOwnProperty.call(toolEnableMap, t.name)) {
        enabled = Boolean(toolEnableMap[t.name])
      } else if (t.name === 'knowledge_search') {
        enabled = stored ? Boolean(ragflow.enabled) : Boolean(data.ragflow?.enabled)
      }
      return { ...t, enabled }
    })

    if (!stored) {
      config.model = data.model
      config.base_url = data.base_url
      config.temperature = data.temperature
      if (data.ragflow) {
        ragflow.enabled = Boolean(data.ragflow.enabled)
        ragflow.base_url = data.ragflow.base_url || ragflow.base_url
        ragflow.api_key = data.ragflow.api_key || ''
        ragflow.dataset_ids_text = (data.ragflow.dataset_ids || []).join(',')
        ragflow.page_size = data.ragflow.page_size || 6
        ragflow.similarity_threshold = data.ragflow.similarity_threshold ?? 0.2
      }
    }
  } catch (e) {
    bootError.value = `无法连接后端：${e.message}（确认 FastAPI 在 :8001 运行）`
  } finally {
    persistReady.value = true
    bootReady.value = true
    persistUiConfig()
  }
}

watch([config, ragflow, allTools, threadId, userId], persistUiConfig, { deep: true })
