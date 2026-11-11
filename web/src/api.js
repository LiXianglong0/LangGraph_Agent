/**
 * 调用后端 FastAPI。
 * 开发环境走 Vite 代理 /api → localhost:8001
 */

async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const detail = data.detail || res.statusText || '请求失败'
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return data
}

/** 拉取默认配置与工具列表 */
export function fetchDefaults() {
  return request('/api/defaults')
}

/** Agent 目录（数据库） */
export function fetchAgents() {
  return request('/api/agents')
}

export function fetchAgent(id) {
  return request(`/api/agents/${encodeURIComponent(id)}`)
}

export function saveAgent(payload) {
  return request(`/api/agents/${encodeURIComponent(payload.id)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

/** 发送一轮对话 */
export function sendChat({ message, thread_id, user_id, config }) {
  return request('/api/chat', {
    method: 'POST',
    body: JSON.stringify({ message, thread_id, user_id, config }),
  })
}

/** 按用户拉取历史会话列表 */
export function fetchUserThreads(user_id) {
  const id = encodeURIComponent(user_id || 'anonymous')
  return request(`/api/users/${id}/threads`)
}

/** 删除用户下某会话元数据 */
export function deleteUserThread(user_id, thread_id) {
  const uid = encodeURIComponent(user_id || 'anonymous')
  const tid = encodeURIComponent(thread_id)
  return request(`/api/users/${uid}/threads/${tid}`, { method: 'DELETE' })
}

/** 按会话 ID 拉取历史（后端进程未重启时可恢复 F5） */
export function fetchThreadMessages(thread_id) {
  const id = encodeURIComponent(thread_id || 'web-session')
  return request(`/api/threads/${id}/messages`)
}

/** 探测 RAGFlow 连通性 */
export function pingRagflow(ragflow) {
  return request('/api/ragflow/ping', {
    method: 'POST',
    body: JSON.stringify(ragflow),
  })
}

/** 将页面配置写入后端项目根目录 .env */
export function saveConfig(payload) {
  return request('/api/config/save', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

/** 经后端代理下载 RAGFlow 文档 */
export async function downloadRagflowDocument({ dataset_id, document_id, ragflow }) {
  const res = await fetch('/api/ragflow/download', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dataset_id, document_id, ragflow }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    const detail = data.detail || res.statusText || '下载失败'
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  const blob = await res.blob()
  let filename = document_id
  const cd = res.headers.get('Content-Disposition') || ''
  const star = /filename\*=UTF-8''([^;]+)/i.exec(cd)
  const plain = /filename="?([^";]+)"?/i.exec(cd)
  if (star) {
    filename = decodeURIComponent(star[1])
  } else if (plain) {
    filename = plain[1]
  }
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
