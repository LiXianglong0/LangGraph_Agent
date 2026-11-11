import { createRouter, createWebHistory } from 'vue-router'
import AppShell from '../layouts/AppShell.vue'

const routes = [
  {
    path: '/',
    component: AppShell,
    children: [
      {
        path: '',
        name: 'home',
        component: () => import('../views/HomeView.vue'),
        meta: { title: '首页' },
      },
      {
        path: 'chat',
        name: 'chat',
        component: () => import('../views/ChatView.vue'),
        meta: { title: '智能对话' },
      },
      {
        path: 'agents',
        name: 'agents',
        component: () => import('../views/AgentsView.vue'),
        meta: { title: 'Agent' },
      },
      {
        path: 'agents/:id',
        name: 'agent-detail',
        component: () => import('../views/AgentDetailView.vue'),
        meta: { title: 'Agent 详情' },
      },
      {
        path: 'agents/:id/chat',
        name: 'agent-chat',
        component: () => import('../views/ChatView.vue'),
        meta: { title: 'Agent 对话' },
      },
      {
        path: 'settings/model',
        name: 'settings-model',
        component: () => import('../views/settings/ModelSettingsView.vue'),
        meta: { title: '模型服务' },
      },
      {
        path: 'settings/knowledge',
        name: 'settings-knowledge',
        component: () => import('../views/settings/KnowledgeSettingsView.vue'),
        meta: { title: '知识库' },
      },
      {
        path: 'settings/system',
        name: 'settings-system',
        component: () => import('../views/settings/SystemSettingsView.vue'),
        meta: { title: '系统' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.afterEach((to) => {
  const page = to.meta?.title
  document.title = page ? `${page} · LangGraph Agent` : 'LangGraph Agent'
})

export default router
