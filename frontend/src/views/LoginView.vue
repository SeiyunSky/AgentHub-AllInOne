<template>
  <div class="login-page" :class="{ 'is-light': !isDark }">

    <!-- ══════════════════════════
         左侧品牌面板
         ══════════════════════════ -->
    <aside class="brand-panel">
      <div class="brand-inner">

        <!-- 左上角大标题 Logo -->
        <div class="top-logo">
          <span class="top-logo-penguin">🐧</span>
          <span class="top-logo-name">AgentHub</span>
        </div>

        <!-- 手写艺术字标题区 -->
        <div class="hero-section">
          <h1 class="hero-script">Multi‑Agent Orchestration Platform</h1>
          <p class="hero-desc">
            Coordinate multiple AI agents in parallel, stream results in real time
            and execute code in isolated sandboxes — all from one interface.
          </p>
        </div>

        <!-- 轮换玻璃屏 — 3D 倾斜展示 -->
        <div class="carousel-area">
          <div class="carousel-3d-wrap">
            <div class="carousel-viewport">
              <div class="carousel-track" :style="{ transform: `translateX(-${slide * 100}%)` }">

              <!-- 屏1：工作流图 -->
              <div class="carousel-slide">
                <div class="glass-screen">
                  <div class="screen-bar">
                    <span class="dot" style="background:#ff5f57"/><span class="dot" style="background:#febc2e"/><span class="dot" style="background:#28c840"/>
                    <span class="screen-title">Workflow</span>
                  </div>
                  <div class="wf-canvas">
                    <div class="wf-node wf-input">
                      <div class="wf-node-dot green"/>
                      <span>Input</span>
                    </div>
                    <svg class="wf-svg" viewBox="0 0 260 130" fill="none" overflow="visible">
                      <path d="M52 65 Q90 65 108 40" stroke="rgba(167,139,250,0.6)" stroke-width="1.2" stroke-dasharray="4 3">
                        <animate attributeName="stroke-dashoffset" from="14" to="0" dur="1.4s" repeatCount="indefinite"/>
                      </path>
                      <path d="M52 65 H108" stroke="rgba(167,139,250,0.6)" stroke-width="1.2" stroke-dasharray="4 3">
                        <animate attributeName="stroke-dashoffset" from="14" to="0" dur="1.2s" repeatCount="indefinite"/>
                      </path>
                      <path d="M52 65 Q90 65 108 90" stroke="rgba(167,139,250,0.6)" stroke-width="1.2" stroke-dasharray="4 3">
                        <animate attributeName="stroke-dashoffset" from="14" to="0" dur="1.6s" repeatCount="indefinite"/>
                      </path>
                      <path d="M162 40 Q185 40 208 65" stroke="rgba(167,139,250,0.5)" stroke-width="1.2" stroke-dasharray="4 3">
                        <animate attributeName="stroke-dashoffset" from="0" to="14" dur="1.4s" repeatCount="indefinite"/>
                      </path>
                      <path d="M162 65 H208" stroke="rgba(167,139,250,0.5)" stroke-width="1.2" stroke-dasharray="4 3">
                        <animate attributeName="stroke-dashoffset" from="0" to="14" dur="1.2s" repeatCount="indefinite"/>
                      </path>
                      <path d="M162 90 Q185 90 208 65" stroke="rgba(167,139,250,0.5)" stroke-width="1.2" stroke-dasharray="4 3">
                        <animate attributeName="stroke-dashoffset" from="0" to="14" dur="1.6s" repeatCount="indefinite"/>
                      </path>
                    </svg>
                    <div class="wf-agents">
                      <div class="wf-agent-node">
                        <img :src="providers[0].src" :alt="providers[0].name"/>
                        <span>{{ providers[0].name }}</span>
                      </div>
                      <div class="wf-agent-node wf-hub">
                        <span class="hub-icon">⚡</span>
                      </div>
                      <div class="wf-agent-node">
                        <img :src="providers[1].src" :alt="providers[1].name"/>
                        <span>{{ providers[1].name }}</span>
                      </div>
                    </div>
                    <div class="wf-node wf-output">
                      <div class="wf-node-dot purple"/>
                      <span>Result</span>
                    </div>
                  </div>
                  <div class="screen-foot">
                    <span class="foot-dot"/>3 agents · parallel · SSE streaming
                  </div>
                </div>
              </div>

              <!-- 屏2：工作流截图 -->
              <div class="carousel-slide">
                <div class="glass-screen">
                  <div class="screen-bar">
                    <span class="dot" style="background:#ff5f57"/><span class="dot" style="background:#febc2e"/><span class="dot" style="background:#28c840"/>
                    <span class="screen-title">Workflow</span>
                  </div>
                  <div class="screen-img-wrap">
                    <img src="/login/workflow.png" alt="Workflow" class="screen-img"/>
                  </div>
                </div>
              </div>

              <!-- 屏3：贡献者 -->
              <div class="carousel-slide">
                <div class="glass-screen">
                  <div class="screen-bar">
                    <span class="dot" style="background:#ff5f57"/><span class="dot" style="background:#febc2e"/><span class="dot" style="background:#28c840"/>
                    <span class="screen-title">Contributors</span>
                  </div>
                  <div class="contrib-body">
                    <div v-for="c in contributors" :key="c.name" class="contrib-card">
                      <img :src="c.avatar" :alt="c.name" class="contrib-avatar"/>
                      <div class="contrib-info">
                        <div class="contrib-name">{{ c.name }}</div>
                        <div class="contrib-role">{{ c.role }}</div>
                      </div>
                      <div class="contrib-badge">Core</div>
                    </div>
                    <div class="contrib-note">Open source · contributions welcome</div>
                  </div>
                </div>
              </div>

            </div><!-- /carousel-track -->
            </div><!-- /carousel-viewport -->
          </div><!-- /carousel-3d-wrap -->

          <!-- 轮换指示点 -->
          <div class="carousel-dots">
            <button v-for="i in 3" :key="i" class="cdot" :class="{ active: slide === i-1 }" @click="slide = i-1"/>
          </div>
        </div>

        <!-- 功能特性小方块 -->
        <div class="feat-chips">
          <div v-for="f in features" :key="f.label" class="feat-chip">
            <span class="chip-icon" v-html="f.svg"/>
            <div class="chip-text">
              <strong>{{ f.label }}</strong>
              <span>{{ f.desc }}</span>
            </div>
          </div>
        </div>

        <!-- 底部 Support -->
        <div class="brand-footer">
          <div class="footer-team">
            <span class="footer-team-name">🐧 咕嘎一辈子队</span>
          </div>
          <div class="footer-bottom">
            <button class="support-btn" @click="showSupport = true">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4">
                <circle cx="8" cy="8" r="6.5"/>
                <path d="M8 11v-1M8 8a2 2 0 1 0-2-2"/>
              </svg>
              Support
            </button>
            <span class="footer-sep">·</span>
            <span class="footer-ver">v0.1.0</span>
          </div>
        </div>

      </div>
    </aside>

    <!-- ══════════════════════════
         右侧：表单面板
         ══════════════════════════ -->
    <main class="form-panel">

      <button class="theme-toggle" @click="toggleDark" :title="isDark ? 'Switch to light' : 'Switch to dark'">
        <svg v-if="isDark" viewBox="0 0 20 20" fill="currentColor">
          <path d="M17.293 13.293A8 8 0 016.707 2.707a8 8 0 1010.586 10.586z"/>
        </svg>
        <svg v-else viewBox="0 0 20 20" fill="currentColor">
          <path d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm0 13a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zm8-5a1 1 0 01-1 1h-1a1 1 0 110-2h1a1 1 0 011 1zM4 10a1 1 0 01-1 1H2a1 1 0 110-2h1a1 1 0 011 1zm12.95-5.364a1 1 0 010 1.414l-.707.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM6.172 15.243a1 1 0 010 1.414l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 0zM17.364 15.95a1 1 0 01-1.414 0l-.707-.707a1 1 0 011.414-1.414l.707.707a1 1 0 010 1.414zM6.172 4.757a1 1 0 01-1.414 0l-.707-.707a1 1 0 011.414-1.414l.707.707a1 1 0 010 1.414zM10 6a4 4 0 100 8 4 4 0 000-8z"/>
        </svg>
      </button>

      <!-- Logo above card -->
      <div class="form-logo">
        <svg class="form-logo-icon" viewBox="0 0 60 66" fill="none">
          <path d="M30 2L58 20V58H2V20L30 2Z" fill="currentColor"/>
          <path d="M30 16L46 26V46H38V34H22V46H14V26L30 16Z" fill="var(--bg-form)"/>
        </svg>
        <span class="form-logo-name">AgentHub</span>
      </div>

      <div class="glass-card" :class="{ shake: shaking }">

        <div class="m-logo">
          <svg viewBox="0 0 28 28" fill="none">
            <rect width="28" height="28" rx="8" fill="rgba(255,255,255,0.1)"/>
            <path d="M14 6L20 10V18L14 22L8 18V10L14 6Z" stroke="white" stroke-width="1.5" stroke-linejoin="round"/>
            <circle cx="14" cy="14" r="2.5" fill="white" fill-opacity="0.9"/>
          </svg>
          <span>AgentHub</span>
        </div>

        <h2 class="card-title">Sign in</h2>
        <p class="card-sub">Welcome back — enter your credentials to continue.</p>

        <form @submit.prevent="handleSubmit" novalidate>

          <div class="field" :class="{ 'field--error': errors.username }">
            <label for="inp-user">Username</label>
            <input id="inp-user" v-model="form.username" type="text"
              placeholder="your-username" autocomplete="username"
              @blur="validate('username')"/>
            <span v-if="errors.username" class="field-err">{{ errors.username }}</span>
          </div>

          <div class="field" :class="{ 'field--error': errors.password }">
            <label for="inp-pwd">Password</label>
            <div class="pwd-wrap">
              <input id="inp-pwd" v-model="form.password"
                :type="showPwd ? 'text' : 'password'"
                placeholder="••••••••" autocomplete="current-password"
                @blur="validate('password')"/>
              <button type="button" class="eye" @click="showPwd = !showPwd" tabindex="-1">
                <svg v-if="!showPwd" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/>
                  <path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd"/>
                </svg>
                <svg v-else viewBox="0 0 20 20" fill="currentColor">
                  <path fill-rule="evenodd" d="M3.707 2.293a1 1 0 00-1.414 1.414l14 14a1 1 0 001.414-1.414l-1.473-1.473A10.014 10.014 0 0019.542 10C18.268 5.943 14.478 3 10 3a9.958 9.958 0 00-4.512 1.074l-1.78-1.781zm4.261 4.26l1.514 1.515a2.003 2.003 0 012.45 2.45l1.514 1.514a4 4 0 00-5.478-5.478z" clip-rule="evenodd"/>
                  <path d="M12.454 16.697L9.75 13.992a4 4 0 01-3.742-3.741L2.335 6.578A9.98 9.98 0 00.458 10c1.274 4.057 5.064 7 9.542 7 .847 0 1.669-.105 2.454-.303z"/>
                </svg>
              </button>
            </div>
            <span v-if="errors.password" class="field-err">{{ errors.password }}</span>
          </div>

          <div v-if="globalErr" class="alert-err">{{ globalErr }}</div>

          <button type="submit" class="btn-submit" :class="{ 'btn--success': done }" :disabled="loading || done">
            <svg v-if="done" viewBox="0 0 20 20" fill="currentColor" width="18" height="18">
              <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/>
            </svg>
            <span v-else-if="!loading">Continue</span>
            <span v-else class="dots"><i/><i/><i/></span>
          </button>

        </form>

        <p class="register-line">
          Don't have an account?
          <router-link :to="{ name: 'register', query: route.query }">Sign up</router-link>
        </p>

        <div class="provider-row">
          <img v-for="p in providers" :key="p.name" :src="p.src" :alt="p.name"/>
        </div>

      </div>
    </main>

    <!-- Support 弹窗 -->
    <Teleport to="body">
      <div v-if="showSupport" class="support-overlay" @click.self="showSupport = false">
        <div class="support-modal">
          <div class="support-header">
            <h3>Support</h3>
            <button class="support-close" @click="showSupport = false">
              <svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/></svg>
            </button>
          </div>
          <div class="support-body">
            <p>AgentHub is an open-source multi-agent orchestration platform.</p>
            <div class="support-links">
              <a href="https://github.com/SeiyunSky/AgentHub-AllInOne" target="_blank" class="support-link">
                <svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 21.795 24 17.295 24 12c0-6.63-5.37-12-12-12"/></svg>
                GitHub Repository
              </a>
              <a href="mailto:support@agenthub.app" class="support-link">
                <svg viewBox="0 0 20 20" fill="currentColor"><path d="M2.003 5.884L10 9.882l7.997-3.998A2 2 0 0016 4H4a2 2 0 00-1.997 1.884z"/><path d="M18 8.118l-8 4-8-4V14a2 2 0 002 2h12a2 2 0 002-2V8.118z"/></svg>
                Email Support
              </a>
              <a href="https://github.com/issues" target="_blank" class="support-link">
                <svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>
                Report an Issue
              </a>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore, applyAccent } from '@/stores/theme'
import { authApi } from '@/api/auth'

import claudecodeIcon from '@/assets/icons/claudecode-color.svg'
import codexIcon       from '@/assets/icons/codex-color.svg'
import opencodeIcon    from '@/assets/icons/opencode.svg'

const router     = useRouter()
const route      = useRoute()
const auth       = useAuthStore()
const themeStore = useThemeStore()

// ── Theme ─────────────────────────────────
const isDark = ref(document.documentElement.classList.contains('dark'))
function toggleDark() {
  isDark.value = !isDark.value
  document.documentElement.classList.toggle('dark', isDark.value)
  applyAccent(themeStore.accent, isDark.value)
}

// ── Carousel ──────────────────────────────
const slide = ref(0)
let autoTimer: ReturnType<typeof setInterval>
onMounted(() => { autoTimer = setInterval(() => { slide.value = (slide.value + 1) % 3 }, 4000) })
onUnmounted(() => clearInterval(autoTimer))

// ── Support modal ─────────────────────────
const showSupport = ref(false)

// ── Form ──────────────────────────────────
const form      = reactive({ username: '', password: '' })
const errors    = reactive({ username: '', password: '' })
const globalErr = ref('')
const loading   = ref(false)
const done      = ref(false)
const showPwd   = ref(false)
const shaking   = ref(false)

function validate(field: 'username' | 'password') {
  errors[field] = form[field].trim() ? '' :
    (field === 'username' ? 'Username is required' : 'Password is required')
  return !errors[field]
}
function shake() {
  shaking.value = false
  requestAnimationFrame(() => { shaking.value = true; setTimeout(() => { shaking.value = false }, 480) })
}
async function handleSubmit() {
  if (!validate('username') | !validate('password')) { shake(); return }
  loading.value = true; globalErr.value = ''
  try {
    const tokens = await authApi.login({ username: form.username, password: form.password })
    auth.setSession(tokens)
    done.value = true
    setTimeout(() => router.push((route.query.redirect as string) || '/chat'), 750)
  } catch (e) {
    globalErr.value = e instanceof Error ? e.message : 'Login failed. Please try again.'
    shake()
  } finally { loading.value = false }
}

// ── Static data ───────────────────────────
const providers = [
  { src: claudecodeIcon, name: 'Claude Code' },
  { src: codexIcon,      name: 'Codex' },
  { src: opencodeIcon,   name: 'OpenCode' },
]
const contributors = [
  { name: 'Adam',    role: 'Core Maintainer', avatar: '/contributors/adam.png' },
  { name: 'Uzemiu',  role: 'Contributor',     avatar: '/contributors/uzemiu.png' },
  { name: 'Musuyin', role: 'Contributor',     avatar: '/contributors/musuyin.png' },
]
const features = [
  { label: 'Parallel Agents',         desc: 'Multiple AI models run simultaneously',    svg: `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><rect x="1" y="1" width="6" height="6" rx="1.5"/><rect x="9" y="1" width="6" height="6" rx="1.5"/><rect x="1" y="9" width="6" height="6" rx="1.5"/><rect x="9" y="9" width="6" height="6" rx="1.5"/></svg>` },
  { label: 'Real‑time SSE Streaming', desc: 'Live token-by-token output delivery',      svg: `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><path d="M2 8h12M8 2l4 6-4 6"/></svg>` },
  { label: 'Docker Sandbox',          desc: 'Isolated, safe code execution environment', svg: `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><rect x="1" y="5" width="14" height="9" rx="1.5"/><path d="M4 5V4a2 2 0 0 1 4 0v1"/><path d="M5 10l2 2 4-4"/></svg>` },
]
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Caveat:wght@700&family=Syne:wght@800&display=swap');

/* ══════════════════════════════════════════
   CSS 变量 — 暗色（高级深墨）
   ══════════════════════════════════════════ */
.login-page {
  --bg-brand:       #0c0c14;
  --bg-form:        #0f0f18;
  --form-orb-a:     rgba(99, 102, 241, 0.22);
  --form-orb-b:     rgba(139, 92, 246, 0.18);
  --form-orb-c:     rgba(59,  130, 246, 0.12);
  --card-bg:        rgba(255,255,255,0.05);
  --card-border:    rgba(255,255,255,0.10);
  --card-top:       rgba(255,255,255,0.18);
  --card-shadow:    0 24px 64px rgba(0,0,0,0.6), 0 1px 0 rgba(255,255,255,0.06) inset;
  --text-primary:   #eeedf8;
  --text-muted:     rgba(255,255,255,0.40);
  --text-subtle:    rgba(255,255,255,0.20);
  --inp-bg:         rgba(255,255,255,0.04);
  --inp-border:     rgba(255,255,255,0.10);
  --inp-border-foc: rgba(139,92,246,0.7);
  --inp-color:      #eeedf8;
  --inp-ph:         rgba(255,255,255,0.18);
  --btn-bg:         #5b21b6;
  --btn-bg-hover:   #6d28d9;
  --btn-success:    #059669;
  --err-text:       #fca5a5;
  --err-border:     rgba(239,68,68,0.25);
  --err-bg:         rgba(239,68,68,0.08);
  --divider:        rgba(255,255,255,0.06);
  --toggle-bg:      rgba(255,255,255,0.06);
  --toggle-border:  rgba(255,255,255,0.10);
  --toggle-color:   rgba(255,255,255,0.40);
  --screen-bg:      rgba(255, 220, 150, 0.10);
  --screen-border:  rgba(255, 200, 100, 0.30);
  --chip-bg:        rgba(255, 220, 150, 0.08);
  --chip-border:    rgba(255, 200, 100, 0.22);

  display: flex;
  min-height: 100vh;
  width: 100%;
  font-family: 'Inter', ui-sans-serif, system-ui, sans-serif;
}

/* CSS 变量 — 亮色（白色系，干净） */
.login-page.is-light {
  --bg-brand:       #13111e;
  --bg-form:        #ffffff;
  --form-orb-a:     rgba(99, 102, 241, 0.08);
  --form-orb-b:     rgba(139, 92, 246, 0.07);
  --form-orb-c:     rgba(59,  130, 246, 0.05);
  --card-bg:        rgba(255,255,255,0.90);
  --card-border:    rgba(0,0,0,0.08);
  --card-top:       rgba(255,255,255,1.0);
  --card-shadow:    0 8px 40px rgba(0,0,0,0.10), 0 1px 0 rgba(255,255,255,0.9) inset;
  --text-primary:   #1a1730;
  --text-muted:     #6b7280;
  --text-subtle:    #9ca3af;
  --inp-bg:         #f9f9fc;
  --inp-border:     rgba(0,0,0,0.12);
  --inp-border-foc: #6d28d9;
  --inp-color:      #1a1730;
  --inp-ph:         #c0bdd0;
  --btn-bg:         #5b21b6;
  --btn-bg-hover:   #6d28d9;
  --btn-success:    #059669;
  --err-text:       #dc2626;
  --err-border:     rgba(239,68,68,0.25);
  --err-bg:         rgba(239,68,68,0.05);
  --divider:        rgba(0,0,0,0.07);
  --toggle-bg:      rgba(0,0,0,0.05);
  --toggle-border:  rgba(0,0,0,0.10);
  --toggle-color:   #6b7280;
  --screen-bg:      rgba(255,255,255,0.55);
  --screen-border:  rgba(180,100,20,0.20);
  --chip-bg:        rgba(255,255,255,0.50);
  --chip-border:    rgba(180,100,20,0.18);
}

/* ══════════════════════════════════════════
   左侧品牌面板
   ══════════════════════════════════════════ */
.brand-panel {
  flex: 0 0 52%;
  background: linear-gradient(160deg, #3d2008 0%, #2e1a06 50%, #1f1104 100%);
  background-image:
    radial-gradient(ellipse 70% 50% at 70% 10%, rgba(251,146,60,0.45) 0%, transparent 60%),
    radial-gradient(ellipse 55% 65% at 10% 85%, rgba(245,158,11,0.30) 0%, transparent 60%),
    radial-gradient(ellipse 45% 45% at 50% 50%, rgba(234,88,12,0.15) 0%, transparent 70%);
  border-right: 1px solid rgba(255,255,255,0.05);
  overflow: visible;
  position: relative;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 0;
}
/* 亮色模式：左侧改成浅橙黄 */
.login-page.is-light .brand-panel {
  background: linear-gradient(160deg, #fff8f0 0%, #fff3e0 50%, #fef0d0 100%);
  background-image:
    radial-gradient(ellipse 70% 50% at 70% 10%, rgba(251,146,60,0.20) 0%, transparent 60%),
    radial-gradient(ellipse 55% 65% at 10% 85%, rgba(245,158,11,0.15) 0%, transparent 60%),
    radial-gradient(ellipse 45% 45% at 50% 50%, rgba(234,88,12,0.08) 0%, transparent 70%);
  border-right: 1px solid rgba(0,0,0,0.06);
}

/* Logo 固定在面板左上角 */
.top-logo {
  position: absolute;
  top: 28px;
  left: 36px;
  display: flex;
  align-items: center;
  gap: 9px;
  z-index: 10;
  white-space: nowrap;
}
.top-logo-penguin {
  font-size: 22px;
  line-height: 1;
  flex-shrink: 0;
}
.top-logo-name {
  font-family: 'Syne', sans-serif;
  font-size: 20px;
  font-weight: 800;
  color: rgba(255,255,255,0.90);
  letter-spacing: -0.02em;
  line-height: 1;
}

.brand-inner {
  max-width: 520px;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 96px 36px 48px 36px;
  overflow: hidden;
  align-items: flex-start;
}

/* ── 手写艺术字标题区 ── */
.hero-section { display: flex; flex-direction: column; gap: 10px; align-items: flex-start; width: 100%; }
.hero-script {
  font-family: 'Caveat', cursive;
  font-size: 28px;
  font-weight: 700;
  line-height: 1.12;
  margin: 0;
  white-space: nowrap;
  text-align: left;
  background: linear-gradient(135deg, #f0ecff 0%, #c4b5fd 40%, #818cf8 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.hero-desc {
  font-family: 'Caveat', cursive;
  font-size: 16px;
  line-height: 1.5;
  color: rgba(255,255,255,0.42);
  margin: 0;
  text-align: left;
  width: 100%;
}

/* ══════════════════════════════════════════
   轮换玻璃屏 — 3D 倾斜
   ══════════════════════════════════════════ */
.carousel-area {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 3D 透视容器 */
.carousel-3d-wrap {
  perspective: 900px;
  perspective-origin: 50% 45%;
}

/* viewport 加倾斜 */
.carousel-viewport {
  overflow: hidden;
  border-radius: 14px;
  transform: rotateY(-10deg) rotateX(4deg) scale(0.97);
  transform-style: preserve-3d;
  box-shadow:
    2px 8px 32px rgba(0,0,0,0.5),
    0 1px 0 rgba(255,255,255,0.08) inset,
    -4px 0 24px rgba(0,0,0,0.3);
}

.carousel-track {
  display: flex;
  transition: transform 0.5s cubic-bezier(0.4, 0, 0.2, 1);
}
.carousel-slide {
  flex: 0 0 100%;
  min-width: 0;
}

/* 玻璃屏共用 */
.glass-screen {
  border-radius: 14px;
  background: var(--screen-bg);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid var(--screen-border);
  border-top-color: rgba(255,255,255,0.15);
  overflow: hidden;
  height: 280px;
  display: flex;
  flex-direction: column;
}
.screen-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 9px 13px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  background: rgba(255,255,255,0.03);
  flex-shrink: 0;
}
.dot { display: block; width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.screen-title {
  font-size: 11px;
  font-family: ui-monospace, monospace;
  color: rgba(255,255,255,0.28);
  margin-left: 4px;
}
.screen-foot {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 13px;
  border-top: 1px solid rgba(255,255,255,0.05);
  font-size: 10.5px;
  font-family: ui-monospace, monospace;
  color: rgba(255,255,255,0.28);
  flex-shrink: 0;
}
.foot-dot { width: 6px; height: 6px; border-radius: 50%; background: #22c55e; flex-shrink: 0; }

/* ── 屏：图片展示 ── */
.screen-img-wrap {
  flex: 1;
  overflow: hidden;
}
.screen-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: top left;
  display: block;
}

/* ── 屏1：工作流 ── */
.wf-canvas {
  padding: 14px 12px 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
  flex: 1;
  position: relative;
}
.wf-svg {
  position: absolute;
  inset: 0;
  width: 100%; height: 100%;
  pointer-events: none;
}
.wf-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  border-radius: 8px;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.09);
  font-size: 10px;
  color: rgba(255,255,255,0.55);
  z-index: 1;
  flex-shrink: 0;
}
.wf-node-dot { width: 7px; height: 7px; border-radius: 50%; }
.wf-node-dot.green  { background: #22c55e; }
.wf-node-dot.purple { background: #a78bfa; }
.wf-agents { display: flex; flex-direction: column; gap: 6px; z-index: 1; }
.wf-agent-node {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 8px;
  border-radius: 7px;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.09);
  font-size: 9px;
  color: rgba(255,255,255,0.50);
}
.wf-agent-node img { width: 14px; height: 14px; object-fit: contain; border-radius: 3px; }
.wf-hub {
  background: linear-gradient(135deg, rgba(91,33,182,0.5), rgba(109,40,217,0.35)) !important;
  border-color: rgba(167,139,250,0.25) !important;
  justify-content: center;
}
.hub-icon { font-size: 14px; }

/* ── 屏2：功能卡片 ── */
.feat-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 8px;
  padding: 12px;
  flex: 1;
  align-content: start;
}
.feat-card {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 9px;
  padding: 10px 8px;
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.feat-card-icon { color: rgba(167,139,250,0.75); display: flex; }
.feat-card-icon :deep(svg) { width: 14px; height: 14px; }
.feat-card-label { font-size: 10px; font-weight: 600; color: rgba(255,255,255,0.72); line-height: 1.3; }
.feat-card-desc  { font-size: 9.5px; color: rgba(255,255,255,0.30); line-height: 1.4; }

/* ── 屏3：贡献者 ── */
.contrib-body { padding: 12px; display: flex; flex-direction: column; gap: 8px; flex: 1; }
.contrib-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 9px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.07);
}
.contrib-avatar { width: 30px; height: 30px; border-radius: 50%; object-fit: cover; }
.contrib-name { font-size: 12px; font-weight: 600; color: rgba(255,255,255,0.78); }
.contrib-role { font-size: 10px; color: rgba(255,255,255,0.30); }
.contrib-badge {
  margin-left: auto;
  font-size: 9.5px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(91,33,182,0.22);
  border: 1px solid rgba(167,139,250,0.25);
  color: rgba(167,139,250,0.85);
}
.contrib-note {
  font-size: 10.5px;
  color: rgba(255,255,255,0.20);
  text-align: center;
  padding-top: 2px;
}

/* 轮换指示点 */
.carousel-dots { display: flex; justify-content: center; gap: 6px; }
.cdot {
  width: 6px; height: 6px; border-radius: 50%;
  background: rgba(255,255,255,0.18);
  border: none; cursor: pointer; padding: 0;
  transition: background 0.2s, transform 0.2s;
}
.cdot.active { background: rgba(167,139,250,0.75); transform: scale(1.3); }

/* ══════════════════════════════════════════
   功能特性小方块 — 3列横排
   ══════════════════════════════════════════ */
.feat-chips {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
.feat-chip {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  padding: 12px 10px;
  border-radius: 10px;
  background: var(--chip-bg);
  border: 1px solid var(--chip-border);
  backdrop-filter: blur(8px);
  transition: background 0.15s;
}
.feat-chip:hover { background: rgba(255,255,255,0.07); }
.chip-icon {
  flex-shrink: 0;
  width: 26px; height: 26px;
  border-radius: 7px;
  background: rgba(91,33,182,0.22);
  border: 1px solid rgba(167,139,250,0.18);
  display: flex; align-items: center; justify-content: center;
  color: rgba(167,139,250,0.80);
}
.chip-icon :deep(svg) { width: 13px; height: 13px; }
.chip-text strong {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: rgba(255,255,255,0.78);
  line-height: 1.3;
}
.chip-text span {
  font-size: 10px;
  color: rgba(255,255,255,0.32);
  margin-top: 2px;
  display: block;
  line-height: 1.4;
}

/* ══════════════════════════════════════════
   底部 Support
   ══════════════════════════════════════════ */
.brand-footer {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
  padding-top: 8px;
  width: 100%;
}
.footer-team {
  display: flex;
  align-items: center;
}
.footer-team-name {
  font-size: 14px;
  font-weight: 600;
  color: rgba(255,255,255,0.65);
  letter-spacing: 0.01em;
}
.login-page.is-light .footer-team-name {
  color: rgba(100,50,10,0.75);
}
.footer-bottom {
  display: flex;
  align-items: center;
  gap: 10px;
}
.support-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 13px;
  color: rgba(255,255,255,0.35);
  padding: 0;
  transition: color 0.15s;
  font-family: inherit;
}
.support-btn svg { width: 14px; height: 14px; }
.support-btn:hover { color: rgba(255,255,255,0.65); }
.footer-sep { color: rgba(255,255,255,0.12); font-size: 13px; }
.footer-ver { font-size: 12px; color: rgba(255,255,255,0.22); font-family: ui-monospace, monospace; }

/* ══════════════════════════════════════════
   右侧表单面板 Logo
   ══════════════════════════════════════════ */
.form-logo {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  margin-bottom: 20px;
  width: 100%;
  max-width: 380px;
}
.form-logo-icon {
  width: 56px;
  height: 62px;
  color: var(--text-primary);
}
.form-logo-name {
  font-family: 'Syne', sans-serif;
  font-size: 28px;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: -0.03em;
  line-height: 1;
}

/* ══════════════════════════════════════════
   右侧表单面板
   ══════════════════════════════════════════ */
.form-panel {
  flex: 1;
  position: relative;
  background:
    radial-gradient(ellipse 60% 50% at 25% 15%, var(--form-orb-a) 0%, transparent 65%),
    radial-gradient(ellipse 50% 60% at 85% 85%, var(--form-orb-b) 0%, transparent 65%),
    radial-gradient(ellipse 35% 35% at 65% 40%, var(--form-orb-c) 0%, transparent 65%),
    var(--bg-form);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 32px;
}
.theme-toggle {
  position: absolute; top: 18px; right: 18px;
  width: 36px; height: 36px; border-radius: 9px;
  border: 1px solid var(--toggle-border);
  background: var(--toggle-bg); color: var(--toggle-color);
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  transition: background 0.15s, color 0.15s; backdrop-filter: blur(8px);
}
.theme-toggle svg { width: 15px; height: 15px; }
.theme-toggle:hover { background: rgba(255,255,255,0.08); color: var(--text-primary); }

.glass-card {
  width: 100%; max-width: 380px; padding: 36px 32px; border-radius: 18px;
  background: var(--card-bg);
  backdrop-filter: blur(32px) saturate(160%);
  -webkit-backdrop-filter: blur(32px) saturate(160%);
  border: 1px solid var(--card-border); border-top-color: var(--card-top);
  box-shadow: var(--card-shadow);
}
.glass-card.shake { animation: card-shake 0.44s ease both; }
@keyframes card-shake {
  0%,100% { transform: translateX(0); }
  20%,60%  { transform: translateX(-7px); }
  40%,80%  { transform: translateX(7px); }
}
.m-logo { display: none; align-items: center; gap: 8px; margin-bottom: 20px; font-size: 14px; font-weight: 600; color: var(--text-primary); }
.m-logo svg { width: 24px; height: 24px; display: block; }
.card-title { font-size: 22px; font-weight: 700; color: var(--text-primary); letter-spacing: -0.025em; margin: 0 0 6px; }
.card-sub { font-size: 13px; color: var(--text-muted); margin: 0 0 28px; line-height: 1.55; }

.field { display: flex; flex-direction: column; gap: 6px; margin-bottom: 14px; }
.field label { font-size: 12px; font-weight: 500; color: var(--text-muted); letter-spacing: 0.01em; }
.field input, .pwd-wrap input {
  width: 100%; height: 42px; padding: 0 14px; border-radius: 9px;
  border: 1px solid var(--inp-border); background: var(--inp-bg);
  color: var(--inp-color); font-size: 14px; font-family: inherit; outline: none;
  box-sizing: border-box; transition: border-color 0.15s, box-shadow 0.15s; caret-color: var(--btn-bg);
}
.field input::placeholder, .pwd-wrap input::placeholder { color: var(--inp-ph); }
.field input:focus, .pwd-wrap input:focus { border-color: var(--inp-border-foc); box-shadow: 0 0 0 3px rgba(109,40,217,0.12); }
.field--error input, .field--error .pwd-wrap input { border-color: rgba(239,68,68,0.5) !important; box-shadow: none !important; }
.field-err { font-size: 12px; color: var(--err-text); }

.pwd-wrap { position: relative; }
.pwd-wrap input { padding-right: 40px; }
.eye { position: absolute; right: 11px; top: 50%; transform: translateY(-50%); background: none; border: none; cursor: pointer; padding: 0; color: var(--text-subtle); display: flex; align-items: center; transition: color 0.15s; }
.eye svg { width: 16px; height: 16px; display: block; }
.eye:hover { color: var(--text-muted); }

.alert-err { padding: 10px 13px; border-radius: 8px; border: 1px solid var(--err-border); background: var(--err-bg); font-size: 13px; color: var(--err-text); margin-bottom: 14px; line-height: 1.45; }

.btn-submit {
  width: 100%; height: 42px; border-radius: 9px; border: none;
  background: var(--btn-bg); color: #fff; font-size: 14px; font-weight: 500;
  cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px;
  transition: background 0.15s, transform 0.1s; margin-top: 4px; letter-spacing: 0.01em;
}
.btn-submit:hover:not(:disabled) { background: var(--btn-bg-hover); }
.btn-submit:active:not(:disabled) { transform: scale(0.99); }
.btn-submit:disabled { opacity: 0.7; cursor: not-allowed; }
.btn-submit.btn--success { background: var(--btn-success) !important; }

.dots { display: flex; gap: 4px; align-items: center; }
.dots i { display: block; width: 5px; height: 5px; border-radius: 50%; background: rgba(255,255,255,0.85); animation: dot-b 1.2s ease-in-out infinite; }
.dots i:nth-child(2) { animation-delay: 0.14s; }
.dots i:nth-child(3) { animation-delay: 0.28s; }
@keyframes dot-b { 0%,60%,100% { transform:translateY(0);opacity:.4; } 30% { transform:translateY(-5px);opacity:1; } }

.register-line { margin-top: 16px; text-align: center; font-size: 13px; color: var(--text-muted); }
.register-line a { color: var(--btn-bg); font-weight: 500; text-decoration: none; margin-left: 4px; }
.register-line a:hover { text-decoration: underline; }

.provider-row { display: flex; justify-content: center; gap: 10px; margin-top: 18px; padding-top: 16px; border-top: 1px solid var(--divider); }
.provider-row img { width: 18px; height: 18px; object-fit: contain; opacity: 0.30; transition: opacity 0.15s; }
.login-page.is-light .provider-row img { filter: none; }
.provider-row img:hover { opacity: 0.65; }

/* ══════════════════════════════════════════
   Support 弹窗
   ══════════════════════════════════════════ */
.support-overlay {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(0,0,0,0.65); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center;
}
.support-modal {
  width: 420px; max-width: calc(100vw - 32px);
  background: #141220; border: 1px solid rgba(255,255,255,0.09);
  border-radius: 16px; overflow: hidden;
  box-shadow: 0 24px 64px rgba(0,0,0,0.6);
}
.support-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 18px 20px 16px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.support-header h3 { margin: 0; font-size: 15px; font-weight: 600; color: rgba(255,255,255,0.88); }
.support-close { background: none; border: none; cursor: pointer; color: rgba(255,255,255,0.35); display: flex; align-items: center; transition: color 0.15s; padding: 2px; }
.support-close svg { width: 18px; height: 18px; }
.support-close:hover { color: rgba(255,255,255,0.75); }
.support-body { padding: 16px 20px 20px; display: flex; flex-direction: column; gap: 14px; }
.support-body p { margin: 0; font-size: 13px; color: rgba(255,255,255,0.40); line-height: 1.55; }
.support-links { display: flex; flex-direction: column; gap: 8px; }
.support-link {
  display: flex; align-items: center; gap: 10px;
  padding: 11px 14px; border-radius: 9px;
  background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.07);
  color: rgba(255,255,255,0.65); font-size: 13px; font-weight: 500;
  text-decoration: none; transition: background 0.15s, color 0.15s;
}
.support-link svg { width: 16px; height: 16px; flex-shrink: 0; color: rgba(167,139,250,0.65); }
.support-link:hover { background: rgba(255,255,255,0.08); color: #fff; }

/* ══════════════════════════════════════════
   亮色模式 — 左侧面板文字颜色覆盖
   ══════════════════════════════════════════ */
.login-page.is-light .top-logo-name {
  color: #3d1a04;
}
.login-page.is-light .top-logo-penguin {
  filter: none;
}
.login-page.is-light .hero-script {
  background: linear-gradient(135deg, #92400e 0%, #b45309 50%, #d97706 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.login-page.is-light .hero-desc {
  color: rgba(80, 40, 5, 0.65);
}
.login-page.is-light .chip-text strong {
  color: rgba(60, 30, 5, 0.85);
}
.login-page.is-light .chip-text span {
  color: rgba(80, 40, 5, 0.55);
}
.login-page.is-light .chip-icon {
  background: rgba(180, 83, 9, 0.12);
  border-color: rgba(180, 83, 9, 0.20);
  color: #b45309;
}
.login-page.is-light .cdot {
  background: rgba(120, 60, 10, 0.25);
}
.login-page.is-light .cdot.active {
  background: #b45309;
}
.login-page.is-light .support-btn {
  color: rgba(80, 40, 5, 0.55);
}
.login-page.is-light .support-btn:hover {
  color: rgba(80, 40, 5, 0.85);
}
.login-page.is-light .footer-sep,
.login-page.is-light .footer-ver {
  color: rgba(80, 40, 5, 0.40);
}

/* ══════════════════════════════════════════
   响应式
   ══════════════════════════════════════════ */
@media (max-width: 900px) {
  .brand-panel { display: none; }
  .form-panel { padding: 24px 16px; }
  .glass-card { max-width: 100%; }
  .m-logo { display: flex; }
}
@media (max-width: 480px) {
  .glass-card { padding: 28px 20px; }
}
</style>
