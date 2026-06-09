import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/RegisterView.vue'),
    },
    {
      path: '/',
      component: () => import('@/components/layout/AppLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          redirect: '/chat',
        },
        {
          path: 'chat',
          name: 'chat',
          component: () => import('@/views/ChatView.vue'),
        },
        {
          path: 'chat/:conversationId',
          name: 'chat-detail',
          component: () => import('@/views/ChatView.vue'),
        },
        {
          path: 'agents',
          name: 'agents',
          component: () => import('@/views/AgentsView.vue'),
        },
        {
          path: 'agents/new',
          name: 'agent-create',
          component: () => import('@/views/AgentFormView.vue'),
        },
        {
          path: 'agents/:agentId',
          name: 'agent-edit',
          component: () => import('@/views/AgentFormView.vue'),
        },
        {
          path: 'skills',
          name: 'skills',
          component: () => import('@/views/SkillsView.vue'),
        },
        {
          path: 'skills/new',
          name: 'skill-create',
          component: () => import('@/views/SkillFormView.vue'),
        },
        {
          path: 'skills/:skillId',
          name: 'skill-edit',
          component: () => import('@/views/SkillFormView.vue'),
        },
        {
          path: 'mcp-servers',
          name: 'mcp-servers',
          component: () => import('@/views/MCPServersView.vue'),
        },
        {
          path: 'mcp-servers/new',
          name: 'mcp-server-create',
          component: () => import('@/views/MCPServerFormView.vue'),
        },
        {
          path: 'mcp-servers/:mcpServerId',
          name: 'mcp-server-edit',
          component: () => import('@/views/MCPServerFormView.vue'),
        },
      ],
    },
    {
      path: '/md-test',
      name: 'md-test',
      component: () => import('@/views/MarkdownTest.vue'),
    },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.matched.some(r => r.meta.requiresAuth) && !auth.isLoggedIn) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  // 已登录用户访问登录/注册页 → 直接进 chat
  if ((to.name === 'login' || to.name === 'register') && auth.isLoggedIn) {
    return { name: 'chat' }
  }
})

export default router
