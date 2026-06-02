<template>
  <nav class="w-[160px] h-full flex flex-col py-4 shrink-0 border-r border-rail-border relative overflow-hidden"
       style="background: linear-gradient(180deg, #1a1040 0%, #2d1b69 60%, #1a1040 100%);">
    <!-- subtle grid texture -->
    <div class="absolute inset-0 pointer-events-none" style="background-image: radial-gradient(rgba(255,255,255,0.03) 1px, transparent 1px); background-size: 20px 20px;"></div>
    <!-- Logo -->
    <div class="flex items-center gap-2.5 px-4 mb-4">
      <div
        class="w-9 h-9 rounded-lg bg-white/15 flex items-center justify-center text-2xl shrink-0 cursor-pointer select-none"
        :class="penguinWiggling ? 'penguin-wiggle' : ''"
        @click="wigglePenguin"
      >🐧</div>
      <span class="logo-text text-white text-[15px] leading-none">AgentHub</span>
    </div>

    <!-- Search Button -->
    <button
      class="mx-3 flex items-center gap-2.5 py-2 px-3 rounded-lg text-white/50 hover:text-white/80 hover:bg-white/5 cursor-pointer transition-all duration-200"
      @click="showSearchDialog"
    >
      <el-icon :size="18"><Search /></el-icon>
      <span class="text-[13px] font-medium">Search</span>
    </button>

    <!-- Divider -->
    <div class="mx-4 h-px bg-white/10 my-3"></div>

    <!-- Primary Nav Icons -->
    <div class="flex-1 flex flex-col gap-1 w-full px-2">
      <NavRailItem
        v-for="item in navItems"
        :key="item.id"
        :icon="item.icon"
        :label="item.label"
        :active="isActive(item)"
        @click="navigateTo(item.routeName)"
      />
    </div>

    <!-- Bottom Icons -->
    <div class="flex flex-col gap-1 w-full px-2 border-t border-rail-border pt-3 mt-3">
      <NavRailItem :icon="QuestionFilled" label="Support" @click="showSupportDialog" />
      <NavRailItem :icon="Setting" label="Settings" />
      <NavRailItem :icon="DArrowLeft" label="Collapse" @click="uiStore.toggleNavRail" />
    </div>

    <!-- ── Contributors Dialog ── -->
    <Teleport to="body">
      <Transition name="overlay-fade">
        <div
          v-if="supportVisible"
          class="fixed inset-0 z-[200] flex items-center justify-center"
          style="background: rgba(10,6,30,0.75); backdrop-filter: blur(6px);"
          @click.self="supportVisible = false"
        >
          <!-- Detail panel -->
          <Transition name="detail-slide">
            <div
              v-if="activeContributor"
              class="absolute right-0 top-0 bottom-0 w-[360px] z-10 flex flex-col overflow-hidden"
              :style="{ background: activeContributor.detailBg }"
            >
              <button
                class="absolute top-4 right-4 w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 flex items-center justify-center text-white transition-all"
                @click="activeContributor = null"
              >✕</button>
              <div class="p-8 pt-12 flex flex-col h-full overflow-y-auto custom-scrollbar">
                <!-- Avatar large -->
                <div
                  class="w-20 h-20 rounded-3xl flex items-center justify-center text-white text-3xl font-black mb-4 shadow-xl"
                  :style="{ background: activeContributor.avatarGradient }"
                >
                  {{ activeContributor.initials }}
                </div>
                <div class="text-white text-xl font-bold mb-0.5">{{ activeContributor.name }}</div>
                <div class="text-white/50 text-[12px] mb-1">{{ activeContributor.alias }}</div>
                <span
                  class="inline-block text-[11px] font-bold px-3 py-1 rounded-full mb-4 w-fit"
                  :style="{ background: activeContributor.tagBg, color: activeContributor.tagColor }"
                >{{ activeContributor.role }}</span>
                <a
                  :href="`mailto:${activeContributor.email}`"
                  class="text-[12px] text-white/60 hover:text-white/90 mb-6 transition-colors"
                >{{ activeContributor.email }}</a>
                <div class="text-white/30 text-[10px] font-bold uppercase tracking-widest mb-3">工作内容</div>
                <ul class="space-y-2">
                  <li
                    v-for="(item, i) in activeContributor.workItems"
                    :key="i"
                    class="flex gap-2 text-[13px] text-white/80 leading-relaxed"
                  >
                    <span class="mt-1.5 shrink-0 w-1.5 h-1.5 rounded-full" :style="{ background: activeContributor.dotColor }"></span>
                    {{ item }}
                  </li>
                </ul>
              </div>
            </div>
          </Transition>

          <!-- Cards grid -->
          <div
            class="relative z-20 transition-all duration-300"
            :class="activeContributor ? 'mr-[360px]' : ''"
          >
            <div class="text-center mb-8">
              <div class="text-white/40 text-[11px] uppercase tracking-widest mb-1">AgentHub</div>
              <div class="text-white text-2xl font-black">🐧 Contributors</div>
            </div>

            <!-- 5 cards in a slightly staggered layout -->
            <div class="flex flex-wrap gap-4 justify-center max-w-[640px]">
              <div
                v-for="(person, idx) in contributors"
                :key="person.email"
                class="contributor-float-card relative cursor-pointer select-none"
                :style="{ animationDelay: `${idx * 0.12}s`, '--card-glow': person.glowColor }"
                @click="activeContributor = person"
              >
                <!-- Glow blob behind card -->
                <div
                  class="absolute -inset-2 rounded-3xl blur-xl opacity-40"
                  :style="{ background: person.avatarGradient }"
                ></div>
                <!-- Card body -->
                <div
                  class="relative rounded-2xl p-5 w-[172px] flex flex-col gap-3 border border-white/10"
                  style="background: rgba(255,255,255,0.06); backdrop-filter: blur(12px);"
                >
                  <div
                    class="w-12 h-12 rounded-xl flex items-center justify-center text-white font-black text-lg shadow-lg"
                    :style="{ background: person.avatarGradient }"
                  >{{ person.initials }}</div>
                  <div>
                    <div class="text-white font-bold text-[13px] leading-tight">{{ person.name }}</div>
                    <div class="text-white/40 text-[11px] mt-0.5">{{ person.alias }}</div>
                  </div>
                  <span
                    class="text-[10px] font-bold px-2 py-0.5 rounded-full w-fit"
                    :style="{ background: person.tagBg, color: person.tagColor }"
                  >{{ person.role }}</span>
                  <div class="text-white/50 text-[11px] italic leading-snug line-clamp-2">{{ person.tagline }}</div>
                </div>
              </div>
            </div>

            <div class="text-center mt-6 text-white/25 text-[11px]">点击卡片查看详情</div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </nav>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUIStore } from '@/stores/ui'
import NavRailItem from './NavRailItem.vue'
import { ChatDotRound, User, MagicStick, QuestionFilled, Setting, Search, DArrowLeft } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'

const router = useRouter()
const route = useRoute()
const uiStore = useUIStore()

const supportVisible = ref(false)
const activeContributor = ref<(typeof contributors)[number] | null>(null)
const penguinWiggling = ref(false)
let penguinTimer: ReturnType<typeof setTimeout> | null = null

function wigglePenguin() {
  penguinWiggling.value = false
  requestAnimationFrame(() => { penguinWiggling.value = true })
  clearTimeout(penguinTimer)
  penguinTimer = setTimeout(() => { penguinWiggling.value = false }, 600)
}

function scheduleRandomWiggle() {
  const delay = 4000 + Math.random() * 8000  // 4~12s 随机
  penguinTimer = setTimeout(() => {
    wigglePenguin()
    scheduleRandomWiggle()
  }, delay)
}

onMounted(() => { scheduleRandomWiggle() })
onUnmounted(() => { if (penguinTimer) clearTimeout(penguinTimer) })

const contributors = [
  {
    name: '沫路',
    alias: 'Adam Zhang',
    initials: 'AZ',
    avatarGradient: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
    glowColor: 'rgba(99,102,241,0.6)',
    detailBg: 'linear-gradient(160deg, #1a1040 0%, #312e81 100%)',
    role: '后端核心架构',
    tagBg: 'rgba(139,92,246,0.25)',
    tagColor: '#c4b5fd',
    dotColor: '#8b5cf6',
    tagline: '系统最重的几块都在这里',
    email: 'adam.zhang03@sap.com',
    workItems: [
      '数据库与基建：数据结构设计、ORM 落地、Alembic 迁移、UTC 时区对齐',
      '通信协议层：AgentEvent 统一事件模型、AgentAdapter 抽象接口、块级流式 SSE 协议、19 个 Orchestrator 工具 input schema',
      '主 Agent (Orchestrator) 全栈：八步 agent loop、上下文压缩、错误恢复、prompt_builder 六层管道、tool_registry $ref 展开 / 截断、子 Thread 唤醒机制',
      'Hook 体系：HookManager 调度中心、PreExecutionHook（黑名单+路径校验）、ApprovalHook（审批闭环）、PostExecutionHook（异步审计）',
      '服务层接通：Chat / Conversation / Message / Prompt 各 Service、HTTP 端点',
      '结构化日志：structlog + stdlib 桥接，contextvars 绑定 trace_id',
      '端到端联调：Windows 子进程兼容、SSE 时序修复、群聊 MVP 跑通、DB 僵尸 thread 收尸、连接池调优',
      'Prompt 工程：主 Agent 提示词调优、19 工具描述瘦身、占位符防御与自检清单',
      '会话管理 API：成员增删、token 用量聚合（messages + threads 两表）',
      '群聊体验：建会话流程拉直、主 Agent 默认注入与"群主"角色固化',
    ],
  },
  {
    name: '玛叔叔',
    alias: 'Wang Chenhui / Uzemiu',
    initials: 'WC',
    avatarGradient: 'linear-gradient(135deg, #3b82f6, #06b6d4)',
    glowColor: 'rgba(59,130,246,0.6)',
    detailBg: 'linear-gradient(160deg, #0c1a3a 0%, #0e3a5c 100%)',
    role: '前端 90% 工作量',
    tagBg: 'rgba(6,182,212,0.2)',
    tagColor: '#67e8f9',
    dotColor: '#06b6d4',
    tagline: '整套 IM 界面全是他写的',
    email: 'chenhui.wang@sap.com',
    workItems: [
      '聊天界面：三栏布局、侧栏折叠、splitpane、contenteditable 输入框 + @mentions + 回复引用、消息气泡、自动滚动',
      '消息块组件：thinking / tool use / code / artifact / image / approval 块、CodeBlock（diff + 行号）、shiki 代码高亮、markdown 渲染',
      'Agent / Skill 管理：Agent Builder 双栏页面、CRUD UI、Agent 表单 + 嵌入式聊天',
      '路由与布局：router-driven 布局、LeftPanel + RouterView 改造、侧栏驱动统一',
      '审批与状态：ApprovalBlock UI、SSE 流式渲染、消息点赞踩反馈、停止生成、置顶会话 + 未读徽章',
      'Artifact 预览：sandboxed iframe、SVG、代码渲染',
      'API 层对接：前端 API 与后端 schema 对齐、ApiResponse envelope 解包、HTTP 拦截器',
    ],
  },
  {
    name: '令姐姐',
    alias: 'Wu Lvsheng / Musuyin',
    initials: 'WL',
    avatarGradient: 'linear-gradient(135deg, #10b981, #0d9488)',
    glowColor: 'rgba(16,185,129,0.6)',
    detailBg: 'linear-gradient(160deg, #052e16 0%, #064e3b 100%)',
    role: 'Adapter 层 + 子系统',
    tagBg: 'rgba(16,185,129,0.2)',
    tagColor: '#6ee7b7',
    dotColor: '#10b981',
    tagline: '子 Agent 接入这一整套都是她',
    email: 'lvsheng.wu@sap.com',
    workItems: [
      'Adapter 层：块级流式协议对齐、ClaudeAdapter（CLI subprocess 模式）、子 Agent system_prompt 注入、内置 Agent 提示词与身份解耦',
      'Codex Adapter：适配新版 CLI（exec 子命令 + 移除 --no-interactive）',
      'MCP 服务 + Agent 模板：MCP 客户端层、三类内置 Agent 人格（coder / research / reviewer）',
      '模块四 + 五全栈：Agent CRUD、Skill CRUD、LLM 辅助 Agent 创建、Skill 注入主 Agent',
      'API 优化：移除硬编码 user_id 改从 X-User-Id 注入、limit/offset 分页、消息列表游标校验防跨会话泄露、N+1 查询消除',
      'D7-blocker 修复：seed_from_db 改同步 Session、_run_thread 自起独立 SessionLocal',
      '集成测试响应解包、Code Review 问题修复',
    ],
  },
  {
    name: '冯瑜轩',
    alias: 'Feng Yuxuan',
    initials: 'FY',
    avatarGradient: 'linear-gradient(135deg, #f59e0b, #ef4444)',
    glowColor: 'rgba(245,158,11,0.6)',
    detailBg: 'linear-gradient(160deg, #2d1500 0%, #451a03 100%)',
    role: '模块六 + 八',
    tagBg: 'rgba(245,158,11,0.2)',
    tagColor: '#fcd34d',
    dotColor: '#f59e0b',
    tagline: '关键路径上的功能实装',
    email: 'yuxuan.feng@sap.com',
    workItems: [
      '模块六：消息操作（点赞 / 踩 / 软删除 / 清除反馈）、会话补全、归属校验',
      '模块八：WebSocket 端点、审批决策协议、approval_decision 处理、Hook 与 WS 闭环',
    ],
  },
  {
    name: '刘盘',
    alias: 'nevergottagiveyouup',
    initials: 'LP',
    avatarGradient: 'linear-gradient(135deg, #ec4899, #8b5cf6)',
    glowColor: 'rgba(236,72,153,0.6)',
    detailBg: 'linear-gradient(160deg, #2d0a1a 0%, #3b0764 100%)',
    role: 'OpenCode 适配',
    tagBg: 'rgba(236,72,153,0.2)',
    tagColor: '#f9a8d4',
    dotColor: '#ec4899',
    tagline: '提示词工程 + OpenCode 适配',
    email: 'yf2685@nyu.edu',
    workItems: [
      'OpenCode Adapter 初步适配 + 测试通过',
      '主 Agent 提示词注入策略调试',
      '脚本提示词去格式化处理',
    ],
  },
]

const navItems = [
  { id: 'chat', icon: ChatDotRound, label: 'Chat', routeName: 'chat' as const },
  { id: 'agents', icon: User, label: 'Agents', routeName: 'agents' as const },
  { id: 'skills', icon: MagicStick, label: 'Skills', routeName: 'skills' as const },
] as const

function isActive(item: { id: string; routeName: string }): boolean {
  if (item.id === 'chat') return route.name === 'chat' || route.name === 'chat-detail'
  if (item.id === 'agents') return route.name === 'agents' || route.name === 'agent-create' || route.name === 'agent-edit'
  if (item.id === 'skills') return route.name === 'skills' || route.name === 'skill-create' || route.name === 'skill-edit'
  return route.name === item.routeName
}

function navigateTo(routeName: string) {
  if (uiStore.sidebarCollapsed) uiStore.sidebarCollapsed = false
  router.push({ name: routeName })
}

function showSearchDialog() {
  ElMessageBox.prompt('', 'Search', {
    confirmButtonText: 'Search',
    cancelButtonText: 'Cancel',
    inputPlaceholder: 'Search conversations, agents, skills...',
    customStyle: { borderRadius: '16px' },
  }).catch(() => {})
}

function showSupportDialog() {
  activeContributor.value = null
  supportVisible.value = true
}
</script>

<style scoped>
/* Floating card animation */
.contributor-float-card {
  animation: float-card 3.5s ease-in-out infinite alternate;
  transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.2s ease;
}
.contributor-float-card:hover {
  transform: translateY(-8px) scale(1.04) !important;
  animation-play-state: paused;
}
.contributor-float-card:nth-child(2) { animation-duration: 3.8s; }
.contributor-float-card:nth-child(3) { animation-duration: 4.1s; animation-direction: alternate-reverse; }
.contributor-float-card:nth-child(4) { animation-duration: 3.6s; }
.contributor-float-card:nth-child(5) { animation-duration: 4.3s; animation-direction: alternate-reverse; }
@keyframes float-card {
  from { transform: translateY(0px); }
  to   { transform: translateY(-10px); }
}

/* Overlay fade */
.overlay-fade-enter-active, .overlay-fade-leave-active { transition: opacity 0.25s ease; }
.overlay-fade-enter-from, .overlay-fade-leave-to { opacity: 0; }

/* Detail slide */
.detail-slide-enter-active { transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.25s ease; }
.detail-slide-leave-active { transition: transform 0.2s ease, opacity 0.2s ease; }
.detail-slide-enter-from { transform: translateX(100%); opacity: 0; }
.detail-slide-leave-to   { transform: translateX(100%); opacity: 0; }

/* Line clamp */
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Penguin wiggle */
.penguin-wiggle {
  animation: penguin-wiggle 0.6s cubic-bezier(0.36, 0.07, 0.19, 0.97);
}
@keyframes penguin-wiggle {
  0%   { transform: rotate(0deg) scale(1); }
  15%  { transform: rotate(-18deg) scale(1.15); }
  35%  { transform: rotate(16deg) scale(1.1); }
  55%  { transform: rotate(-12deg) scale(1.05); }
  70%  { transform: rotate(8deg) scale(1.02); }
  85%  { transform: rotate(-4deg) scale(1.01); }
  100% { transform: rotate(0deg) scale(1); }
}

/* Logo text */
.logo-text {
  font-family: 'Orbitron', 'Exo 2', 'Rajdhani', system-ui, sans-serif;
  font-weight: 700;
  letter-spacing: 0.06em;
  background: linear-gradient(135deg, #e0d7ff 0%, #a78bfa 60%, #7c3aed 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
</style>
