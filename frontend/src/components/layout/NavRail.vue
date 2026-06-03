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

    <!-- User card: 头像 + display_name + username + 退出按钮 -->
    <div
      v-if="auth.isLoggedIn"
      class="mx-2 mt-2 mb-1 px-2 py-2 rounded-xl flex items-center gap-2 group transition-all duration-200 hover:bg-white/8"
      style="background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.06);"
    >
      <!-- Avatar bubble -->
      <div
        class="w-8 h-8 rounded-lg flex items-center justify-center text-white font-bold text-[13px] shrink-0 shadow-sm"
        :style="{ background: avatarGradient }"
      >
        {{ avatarInitial }}
      </div>

      <!-- Name + username -->
      <div class="flex-1 min-w-0">
        <div class="text-white text-[12px] font-semibold truncate leading-tight">
          {{ auth.displayName }}
        </div>
        <div class="text-white/40 text-[10px] truncate leading-tight mt-0.5">
          @{{ auth.username }}
        </div>
      </div>

      <!-- Logout icon button (only visible on hover for cleanliness) -->
      <button
        class="w-7 h-7 rounded-md flex items-center justify-center text-white/50 hover:text-white hover:bg-white/10 transition-all opacity-0 group-hover:opacity-100 shrink-0"
        title="退出登录"
        @click="handleLogout"
      >
        <el-icon :size="15"><SwitchButton /></el-icon>
      </button>
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
                  class="w-20 h-20 rounded-3xl flex items-center justify-center text-white text-3xl font-black mb-4 shadow-xl overflow-hidden"
                  :style="{ background: activeContributor.avatarGradient }"
                >
                  <img
                    v-if="activeContributor.avatarImage"
                    :src="activeContributor.avatarImage"
                    :alt="activeContributor.name"
                    class="w-full h-full object-cover"
                  />
                  <template v-else>{{ activeContributor.initials }}</template>
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

                <!-- 分组渲染:前端 / 后端 / 测试,空组隐藏 -->
                <div class="space-y-5">
                  <div
                    v-for="group in workGroupsOf(activeContributor)"
                    :key="group.key"
                    class="space-y-2"
                  >
                    <div class="flex items-center gap-2">
                      <span
                        class="text-[10px] font-bold px-2 py-0.5 rounded-md tracking-wider"
                        :style="{ background: group.bg, color: group.color }"
                      >{{ group.label }}</span>
                      <span class="flex-1 h-px bg-white/10"></span>
                      <span class="text-[10px] text-white/30">{{ group.items.length }}</span>
                    </div>
                    <ul class="space-y-2 pl-1">
                      <li
                        v-for="(item, i) in group.items"
                        :key="i"
                        class="flex gap-2 text-[13px] text-white/80 leading-relaxed"
                      >
                        <span class="mt-1.5 shrink-0 w-1.5 h-1.5 rounded-full" :style="{ background: activeContributor.dotColor }"></span>
                        <span>{{ item }}</span>
                      </li>
                    </ul>
                  </div>
                </div>
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
                    class="w-12 h-12 rounded-xl flex items-center justify-center text-white font-black text-lg shadow-lg overflow-hidden"
                    :style="{ background: person.avatarGradient }"
                  >
                    <img
                      v-if="person.avatarImage"
                      :src="person.avatarImage"
                      :alt="person.name"
                      class="w-full h-full object-cover"
                    />
                    <template v-else>{{ person.initials }}</template>
                  </div>
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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUIStore } from '@/stores/ui'
import { useAuthStore } from '@/stores/auth'
import { authApi } from '@/api/auth'
import NavRailItem from './NavRailItem.vue'
import { ChatDotRound, User, MagicStick, QuestionFilled, Setting, Search, DArrowLeft, SwitchButton } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'

const router = useRouter()
const route = useRoute()
const uiStore = useUIStore()
const auth = useAuthStore()

// 头像首字母:优先 display_name 第一个字符,回退到 username
const avatarInitial = computed(() => {
  const src = auth.displayName || auth.username || '?'
  return src.charAt(0).toUpperCase()
})

// 根据 username 稳定哈希生成渐变色,每个用户固定一种配色
const AVATAR_PALETTES = [
  'linear-gradient(135deg, #6366f1, #8b5cf6)',  // indigo -> violet
  'linear-gradient(135deg, #3b82f6, #06b6d4)',  // blue -> cyan
  'linear-gradient(135deg, #10b981, #0d9488)',  // green -> teal
  'linear-gradient(135deg, #f59e0b, #ef4444)',  // amber -> red
  'linear-gradient(135deg, #ec4899, #8b5cf6)',  // pink -> violet
  'linear-gradient(135deg, #06b6d4, #0ea5e9)',  // cyan -> sky
  'linear-gradient(135deg, #f97316, #ec4899)',  // orange -> pink
] as const

const avatarGradient = computed(() => {
  const key = auth.username || auth.user?.id || 'default'
  let hash = 0
  for (let i = 0; i < key.length; i++) {
    hash = ((hash << 5) - hash + key.charCodeAt(i)) | 0
  }
  return AVATAR_PALETTES[Math.abs(hash) % AVATAR_PALETTES.length]
})

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
    avatarImage: '/contributors/adam.png',
    avatarGradient: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
    glowColor: 'rgba(99,102,241,0.6)',
    detailBg: 'linear-gradient(160deg, #1a1040 0%, #312e81 100%)',
    role: '后端核心架构',
    tagBg: 'rgba(139,92,246,0.25)',
    tagColor: '#c4b5fd',
    dotColor: '#8b5cf6',
    tagline: '后端架构 + 前端工具链 + 救火队长',
    email: 'adam.zhang03@sap.com',
    work: {
      backend: [
        '架构与基建：项目调研、整体架构设计、前后端框架搭建、数据结构设计、ORM 落地、Alembic 迁移、UTC 时区对齐、连接池调优',
        '通信协议：AgentEvent 统一事件模型、AgentAdapter 抽象接口、ContentBlock 数组化、块级流式 SSE 协议',
        '主 Agent (Orchestrator) 全栈：核心设计、八步 agent loop、上下文压缩、错误恢复、六层 prompt 管道、tool_registry $ref 展开 / 截断、19 个工具 input schema 与具体实装、子 Thread 唤醒机制',
        'Hook 体系：HookManager 调度中心 + 同步串行链 / 异步深拷贝投递、PreExecution（黑名单 + 路径穿越校验）、Approval（审批闭环 + 守卫）、PostExecution（异步审计）',
        '服务层与 HTTP 端点：Chat / Conversation / Message / Prompt 全套 Service、统一响应 envelope、agent_id 体系修复',
        '群聊与并行调度：群聊 MVP、conversation 成员增删、token 用量聚合（messages + threads 两表）、会话设置弹窗、主 Agent 默认注入 + 群主角色固化、子 Thread 排队 / 抢占 / 紧急中止',
        '会话沙箱：runtime/memory 沙箱端点（列文件 / 读 / 写 / 下载 / 上传）+ 越界路径校验',
        '审批工作流：审批工具实装 + 前后端协议对齐',
        '结构化日志：structlog + stdlib 桥接、console / JSON 双格式、contextvars 绑定 trace_id',
        'Auth 全栈：基于刘盘 JWT 基础进一步落地与端到端联调',
        'Prompt 工程：主 Agent 提示词调优、19 工具描述瘦身、占位符防御与派活前自检清单',
        '稳定性与救火：Windows cmd.exe 子进程兼容、SSE 时序、僵尸 thread 收尸、/chat/stop 锁释放、CancelledError 路径、count_tokens 404 降级、@ 子 Agent 上下文累积',
      ],
      frontend: [
        '前端 UI 整体打磨：Workflow 视图、Files 模块初版',
        '多 Agent 并行 streaming 气泡 + activity chip 实时反馈',
        '右侧面板重构：Workflow / Files / Preview 三 Tab 同级切换',
        '会话沙箱文件浏览闭环：文件列表 + sandboxFiles store + SSE 自刷新 + 下载 / 编辑 / 预览',
        '预览体验升级：Monaco readOnly 代码语法高亮、Markdown 双 Tab（渲染 / 源码）、扩展名→语言完整映射',
        '上传走沙箱：ChatInput 改造，Agent 立即能 read_file 读到附件',
        'Bug 修复：嵌套 button 导致 Approval 点击失效、@ 子 Agent 身份混乱锚定、SSE 连接未更新、停止按钮线程异常、feedback 端点改 POST + Vite 代理端口对齐',
      ],
      testing: [
        'Orchestrator loop 集成测试（CI 友好的 mock 实现 + 真 LLM 状态压缩本地脚本）',
        '集成测试补全与 5.27 开发进度总览文档',
      ],
    },
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
    tagline: 'IM 主界面 + 一整套消息块 UI 都是他写的',
    email: 'chenhui.wang@sap.com',
    work: {
      frontend: [
        '前端脚手架搭建 + 整体布局：Chat Layout、三栏布局、侧栏折叠、splitpane、PanelContainer 抽象、统一 splitter / 滚动条样式',
        '聊天输入：contenteditable 输入框 + @mentions + 回复引用 + 代码复制 + 输入框聊天切换',
        '消息块体系：thinking / tool use / code / artifact / image / approval / deployment 七类块、ApprovalBlock UI 与 SSE 流式修复、CollapsibleBlock 头部统一、Copy 按钮抽离',
        '代码与渲染：CodeBlock（diff + 行号）、shiki 代码高亮、Markdown 渲染、SSE 代码块渲染修复',
        'Artifact 预览：sandboxed iframe / SVG / 代码三种渲染、Artifact Edit 模式（Monaco 编辑器 + 文件同步）',
        'Agent / Skill 管理：Agent Builder 双栏 + 嵌入式聊天、Agent CRUD UI、Skill CRUD 前端、Agent 表单 splitpane、Agent 页面整体优化',
        '会话列表：archived 分类 / 时间戳 / 删除 / 归档限制、ConversationListItem 携带 agents 信息与排序、置顶会话 + 未读徽章、空状态卡片风格统一',
        '路由与布局：router-driven 布局、LeftPanel + RouterView 改造、sidebar nav 切主面板不切路由、Agent CRUD 路由化',
        '消息互动：MessageActions 绝对定位、点赞踩反应 UI 更新、自动滚动到底部、停止生成（含 mock SSE abort）',
        'API 层：前端 API 与后端 schema 对齐、ApiResponse envelope 拦截器解包',
      ],
      testing: [
        'Init mock 测试体系 + 简单冒烟测试',
      ],
    },
  },
  {
    name: '令姐姐',
    alias: 'Wu Lvsheng / Musuyin',
    initials: 'WL',
    avatarGradient: 'linear-gradient(135deg, #10b981, #0d9488)',
    glowColor: 'rgba(16,185,129,0.6)',
    detailBg: 'linear-gradient(160deg, #052e16 0%, #064e3b 100%)',
    role: 'Adapter 层 + Agent / Skill 子系统',
    tagBg: 'rgba(16,185,129,0.2)',
    tagColor: '#6ee7b7',
    dotColor: '#10b981',
    tagline: '子 Agent 接入这一整套都是她',
    email: 'lvsheng.wu@sap.com',
    work: {
      backend: [
        'Adapter 层：接口对齐 master 块级流式协议、AgentEvent 事件完善',
        'ClaudeAdapter：从 Anthropic SDK 切到 CLI subprocess 模式 + readline 64KB 限制绕过 + StreamInput 传 agent_name 修 agent_start',
        'Codex Adapter：适配新版 CLI（exec 子命令 + 移除 --no-interactive）+ 用户身份注入',
        'MCP 客户端层 + 三类内置 Agent 人格（coder / research / reviewer）',
        '子 Agent system_prompt 注入 + 内置 Agent 提示词与身份数据解耦',
        'Agent 管理全栈：CRUD API + LLM 辅助 Agent 创建 + 支持修改 type',
        'Skill 子系统全栈：CRUD API + Skill 注入主 Agent + 修改不写本地文件',
        'Agent 头像功能：后端静态服务 + 消息携带头像快照',
        'Diff 模块后端基础（未完全实现）',
        'D7-blocker 修复：seed_from_db 改同步 Session、_run_thread 自起独立 SessionLocal',
        'API 优化：移除硬编码 user_id 改 X-User-Id 注入、limit/offset 分页、消息列表游标校验防跨会话泄露、N+1 查询消除',
        '稳定性：CancelledError 分支漏 rollback 导致锁等待超时',
      ],
      frontend: [
        'Agent / Skill CRUD 改进配合（与玛叔叔联合）',
      ],
      testing: [
        '测试基础设施补全 + events 修订 + 数据结构文档同步',
        'Code Review 问题修复 + 集成测试响应解包',
      ],
    },
  },
  {
    name: '冯瑜轩',
    alias: 'Feng Yuxuan',
    initials: 'FY',
    avatarGradient: 'linear-gradient(135deg, #f59e0b, #ef4444)',
    glowColor: 'rgba(245,158,11,0.6)',
    detailBg: 'linear-gradient(160deg, #2d1500 0%, #451a03 100%)',
    role: '消息操作 + WebSocket',
    tagBg: 'rgba(245,158,11,0.2)',
    tagColor: '#fcd34d',
    dotColor: '#f59e0b',
    tagline: '消息互动 + 审批 WS 闭环',
    email: 'yuxuan.feng@sap.com',
    work: {
      backend: [
        '消息操作：点赞 / 踩 / 软删除 / 清除反馈、会话补全、归属校验',
        'WebSocket 端点 + 审批决策协议：approval_decision 处理、Hook ↔ WS 闭环',
      ],
    },
  },
  {
    name: '刘盘',
    alias: 'nevergottagiveyouup',
    initials: 'LP',
    avatarGradient: 'linear-gradient(135deg, #ec4899, #8b5cf6)',
    glowColor: 'rgba(236,72,153,0.6)',
    detailBg: 'linear-gradient(160deg, #2d0a1a 0%, #3b0764 100%)',
    role: 'Auth 全栈 + 单元测试 + OpenCode',
    tagBg: 'rgba(236,72,153,0.2)',
    tagColor: '#f9a8d4',
    dotColor: '#ec4899',
    tagline: '基建 + 测试 + OpenCode 适配',
    email: 'yf2685@nyu.edu',
    work: {
      backend: [
        'Auth 体系：hash + JWT + 非明文密码、auth 前后端打通',
        'OpenCode Adapter 初步适配 + 测试通过',
        '主 Agent 提示词注入策略（成功路径）+ 脚本提示词去格式化',
        'Token 计数透出 API',
      ],
      frontend: [
        '登录元素优化',
      ],
      testing: [
        '基础设施 + 业务层全部 unit 级通过 + 接通真 DB 验证',
        '单元测试体系搭建',
      ],
    },
  },
]

// 把 contributor 的 work 对象拆成有序 / 非空的分组,模板按这个渲染。
// 兼容 workItems(老格式)和 work(新格式),避免一次性必须改全部数据。
const WORK_GROUP_META = {
  backend:  { label: '后端',     bg: 'rgba(139,92,246,0.18)', color: '#c4b5fd' },
  frontend: { label: '前端',     bg: 'rgba(59,130,246,0.18)', color: '#93c5fd' },
  testing:  { label: '测试',     bg: 'rgba(16,185,129,0.18)', color: '#6ee7b7' },
  other:    { label: '其它',     bg: 'rgba(148,163,184,0.18)', color: '#cbd5e1' },
} as const

type WorkGroupKey = keyof typeof WORK_GROUP_META

interface ContribWithWork {
  work?: Partial<Record<WorkGroupKey, string[]>>
  workItems?: string[]
}

function workGroupsOf(c: ContribWithWork) {
  // 新格式:work 对象
  if (c.work) {
    const order: WorkGroupKey[] = ['backend', 'frontend', 'testing', 'other']
    return order
      .filter(k => Array.isArray(c.work?.[k]) && c.work![k]!.length > 0)
      .map(k => ({ key: k, items: c.work![k]!, ...WORK_GROUP_META[k] }))
  }
  // 老格式:workItems 平铺,作为"其它"一组渲染
  if (c.workItems?.length) {
    return [{ key: 'other' as const, items: c.workItems, ...WORK_GROUP_META.other }]
  }
  return []
}

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

async function handleLogout() {
  try {
    await ElMessageBox.confirm('确定要退出登录吗?', '退出登录', {
      confirmButtonText: '退出',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return  // 用户取消
  }

  // 调后端把 token 加入黑名单(失败也无所谓,只要本地清干净)
  try {
    await authApi.logout()
  } catch {
    // ignore: token 已经无效或网络错误,不影响后续清状态
  }
  auth.clear()
  router.push({ name: 'login' })
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
