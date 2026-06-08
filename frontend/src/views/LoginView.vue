<template>
  <div class="auth-layout">
    <!-- ── Left Hero Panel ── -->
    <div class="hero-panel">
      <!-- Dot grid background -->
      <div class="hero-dots"></div>
      <!-- Glow orbs -->
      <div class="hero-orb hero-orb-1"></div>
      <div class="hero-orb hero-orb-2"></div>

      <div class="hero-content">
        <!-- Brand -->
        <div class="hero-brand">
          <div class="hero-logo">🐧</div>
          <div>
            <div class="hero-title">AgentHub</div>
            <div class="hero-subtitle">{{ t('auth.brandSubtitle') }}</div>
          </div>
        </div>

        <!-- Floating agents orbit -->
        <div class="agents-orbit" aria-hidden="true">
          <div class="orbit-ring"></div>
          <img v-for="(icon, i) in agentIcons" :key="i"
            :src="icon.src" :alt="icon.name"
            class="orbit-icon"
            :style="orbitStyle(i, agentIcons.length)"
          />
          <!-- Center hub -->
          <div class="orbit-hub">
            <div class="orbit-hub-inner">⚡</div>
          </div>
        </div>

        <!-- Feature pills -->
        <div class="hero-pills">
          <span v-for="pill in pills" :key="pill" class="hero-pill">{{ pill }}</span>
        </div>

        <!-- Stats row -->
        <div class="hero-stats">
          <div v-for="s in stats" :key="s.labelKey" class="hero-stat">
            <div class="hero-stat-value">{{ s.value }}</div>
            <div class="hero-stat-label">{{ t(s.labelKey) }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Right Form Panel ── -->
    <div class="form-panel">
      <div class="form-inner fade-in-up">
        <!-- Mobile logo (hidden on desktop) -->
        <div class="mobile-logo">
          <div class="mobile-logo-icon">🐧</div>
          <h1 class="mobile-logo-name">AgentHub</h1>
        </div>

        <h2 class="form-heading">{{ t('auth.loginTitle') }}</h2>
        <p class="form-sub">{{ t('auth.loginSubtitle') }}</p>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          class="auth-form"
          @submit.prevent="handleLogin"
        >
          <el-form-item prop="username">
            <el-input
              v-model="form.username"
              :placeholder="t('auth.username')"
              size="large"
              :prefix-icon="User"
              class="auth-input"
            />
          </el-form-item>

          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              :placeholder="t('auth.password')"
              size="large"
              :prefix-icon="Lock"
              show-password
              class="auth-input"
            />
          </el-form-item>

          <el-form-item>
            <button
              type="submit"
              class="auth-submit-btn"
              :class="{ loading }"
              :disabled="loading"
            >
              <span v-if="!loading" class="btn-label">{{ t('auth.signIn') }}</span>
              <span v-else class="btn-spinner">
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
              </span>
            </button>
          </el-form-item>

          <div v-if="errorMsg" class="auth-error">{{ errorMsg }}</div>

          <div class="auth-switch">
            {{ t('auth.newHere') }}
            <router-link :to="{ name: 'register', query: route.query }" class="auth-link">
              {{ t('auth.createAccountLink') }}
            </router-link>
          </div>
        </el-form>

        <!-- Provider strip -->
        <div class="provider-strip">
          <div class="provider-strip-label">{{ t('auth.providersLabel') }}</div>
          <div class="provider-icons">
            <img v-for="p in providers" :key="p.name" :src="p.src" :alt="p.name" class="provider-icon" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { authApi } from '@/api/auth'
import { User, Lock } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'

import claudecodeIcon from '@/assets/icons/claudecode-color.svg'
import codexIcon from '@/assets/icons/codex-color.svg'
import opencodeIcon from '@/assets/icons/opencode.svg'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)
const errorMsg = ref('')

const form = reactive({ username: '', password: '' })

const rules = computed<FormRules>(() => ({
  username: [{ required: true, message: t('auth.validation.usernameRequired'), trigger: 'blur' }],
  password: [{ required: true, message: t('auth.validation.passwordRequired'), trigger: 'blur' }],
}))

const agentIcons = [
  { src: claudecodeIcon, name: 'Claude Code' },
  { src: codexIcon, name: 'Codex' },
  { src: opencodeIcon, name: 'OpenCode' },
]

const providers = [
  { src: claudecodeIcon, name: 'Claude Code' },
  { src: codexIcon, name: 'Codex' },
  { src: opencodeIcon, name: 'OpenCode' },
]

const pills = computed(() => [
  t('auth.featureMultiAgent'),
  t('auth.featureStreaming'),
  t('auth.featureParallelExecution'),
  t('auth.featureDiffPreview'),
])

const stats = [
  { value: '3', labelKey: 'auth.statProviders' },
  { value: '∞', labelKey: 'auth.statConcurrentAgents' },
  { value: 'SSE', labelKey: 'auth.statRealTimeStream' },
]

function orbitStyle(i: number, total: number) {
  const angle = (i / total) * 360
  const r = 90 // px radius
  const rad = (angle * Math.PI) / 180
  const x = Math.cos(rad) * r
  const y = Math.sin(rad) * r
  const delay = i * 0.6
  return {
    transform: `translate(calc(-50% + ${x}px), calc(-50% + ${y}px))`,
    animationDelay: `${delay}s`,
  }
}

async function handleLogin() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  errorMsg.value = ''

  try {
    const tokens = await authApi.login({ username: form.username, password: form.password })
    auth.setSession(tokens)
    const redirect = (route.query.redirect as string) || '/chat'
    router.push(redirect)
  } catch (err) {
    errorMsg.value = err instanceof Error ? err.message : t('auth.loginFailed')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* ── Layout ── */
.auth-layout {
  display: flex;
  min-height: 100vh;
  background: var(--color-surface);
}

/* ── Hero Panel ── */
.hero-panel {
  position: relative;
  flex: 0 0 46%;
  background: linear-gradient(155deg, #1a1040 0%, #2a1860 45%, #1e1050 100%);
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.hero-dots {
  position: absolute;
  inset: 0;
  background-image: radial-gradient(rgba(255, 255, 255, 0.07) 1px, transparent 1px);
  background-size: 28px 28px;
  pointer-events: none;
}

.hero-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  pointer-events: none;
}
.hero-orb-1 {
  width: 320px;
  height: 320px;
  background: radial-gradient(circle, rgba(99, 102, 241, 0.35) 0%, transparent 70%);
  top: -80px;
  right: -60px;
  animation: orb-drift 8s ease-in-out infinite;
}
.hero-orb-2 {
  width: 240px;
  height: 240px;
  background: radial-gradient(circle, rgba(139, 92, 246, 0.25) 0%, transparent 70%);
  bottom: -40px;
  left: -40px;
  animation: orb-drift 10s ease-in-out infinite reverse;
}

@keyframes orb-drift {
  0%, 100% { transform: translate(0, 0); }
  33% { transform: translate(20px, -15px); }
  66% { transform: translate(-10px, 20px); }
}

.hero-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 32px;
  padding: 40px 32px;
  max-width: 400px;
  width: 100%;
}

/* Brand */
.hero-brand {
  display: flex;
  align-items: center;
  gap: 14px;
  animation: hero-enter 0.6s var(--ease-out) both;
}
.hero-logo {
  width: 52px;
  height: 52px;
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.6), rgba(139, 92, 246, 0.4));
  border: 1px solid rgba(255, 255, 255, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  backdrop-filter: blur(8px);
  box-shadow: 0 8px 32px rgba(99, 102, 241, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.15);
}
.hero-title {
  font-size: 26px;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: -0.02em;
  line-height: 1.2;
}
.hero-subtitle {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.5);
  margin-top: 2px;
  letter-spacing: 0.02em;
}

/* Orbit */
.agents-orbit {
  position: relative;
  width: 240px;
  height: 240px;
  flex-shrink: 0;
  animation: hero-enter 0.6s 0.15s var(--ease-out) both;
}

.orbit-ring {
  position: absolute;
  inset: 20px;
  border-radius: 50%;
  border: 1px dashed rgba(255, 255, 255, 0.12);
  animation: orbit-rotate 18s linear infinite;
}

@keyframes orbit-rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.orbit-icon {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.15);
  padding: 5px;
  backdrop-filter: blur(8px);
  animation: icon-float 3s ease-in-out infinite;
  object-fit: contain;
}

@keyframes icon-float {
  0%, 100% { filter: brightness(0.9); }
  50% { filter: brightness(1.2); }
}

.orbit-hub {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 54px;
  height: 54px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.8), rgba(139, 92, 246, 0.6));
  border: 1px solid rgba(255, 255, 255, 0.25);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 30px rgba(99, 102, 241, 0.5), 0 0 60px rgba(99, 102, 241, 0.2);
  animation: hub-pulse 2.5s ease-in-out infinite;
}
.orbit-hub-inner {
  font-size: 22px;
}

@keyframes hub-pulse {
  0%, 100% { box-shadow: 0 0 24px rgba(99, 102, 241, 0.5), 0 0 48px rgba(99, 102, 241, 0.2); }
  50% { box-shadow: 0 0 40px rgba(99, 102, 241, 0.7), 0 0 80px rgba(99, 102, 241, 0.35); }
}

/* Pills */
.hero-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  animation: hero-enter 0.6s 0.3s var(--ease-out) both;
}
.hero-pill {
  padding: 4px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.15);
  color: rgba(255, 255, 255, 0.75);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.02em;
  backdrop-filter: blur(4px);
}

/* Stats */
.hero-stats {
  display: flex;
  gap: 24px;
  animation: hero-enter 0.6s 0.45s var(--ease-out) both;
}
.hero-stat {
  text-align: center;
}
.hero-stat-value {
  font-size: 22px;
  font-weight: 700;
  color: #ffffff;
  line-height: 1;
}
.hero-stat-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.45);
  margin-top: 4px;
  letter-spacing: 0.03em;
}

@keyframes hero-enter {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ── Form Panel ── */
.form-panel {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
  background: var(--color-surface);
}

.form-inner {
  width: 100%;
  max-width: 380px;
}

.mobile-logo {
  display: none;
  align-items: center;
  gap: 10px;
  margin-bottom: 28px;
}
.mobile-logo-icon {
  font-size: 28px;
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: linear-gradient(135deg, var(--color-brand), var(--color-brand-dark));
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 16px rgba(99, 102, 241, 0.35);
}
.mobile-logo-name {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-on-surface);
}

.form-heading {
  font-size: 26px;
  font-weight: 700;
  color: var(--color-on-surface);
  letter-spacing: -0.02em;
  margin: 0 0 6px;
}
.form-sub {
  font-size: 14px;
  color: var(--color-on-surface-variant);
  margin: 0 0 28px;
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.auth-input :deep(.el-input__wrapper) {
  border-radius: 12px !important;
  height: 46px;
}

.auth-submit-btn {
  width: 100%;
  height: 46px;
  border-radius: 12px;
  border: none;
  background: linear-gradient(135deg, var(--color-brand) 0%, #8b5cf6 50%, var(--color-brand-dark) 100%);
  background-size: 200% 100%;
  color: #ffffff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.25s var(--ease-out);
  box-shadow: 0 4px 20px rgba(99, 102, 241, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 4px;
}
.auth-submit-btn:hover:not(:disabled) {
  background-position: right center;
  box-shadow: 0 6px 28px rgba(99, 102, 241, 0.5);
  transform: translateY(-1px);
}
.auth-submit-btn:active:not(:disabled) {
  transform: translateY(0);
  box-shadow: 0 2px 12px rgba(99, 102, 241, 0.35);
}
.auth-submit-btn:disabled {
  opacity: 0.75;
  cursor: not-allowed;
}
.btn-spinner {
  display: flex;
  gap: 4px;
  align-items: center;
}

.auth-error {
  text-align: center;
  font-size: 12px;
  color: var(--color-error);
  padding: 6px 0;
}

.auth-switch {
  text-align: center;
  font-size: 13px;
  color: var(--color-on-surface-variant);
  padding-top: 4px;
}
.auth-link {
  color: var(--color-brand);
  font-weight: 600;
  text-decoration: none;
  margin-left: 4px;
}
.auth-link:hover {
  text-decoration: underline;
}

/* Provider strip */
.provider-strip {
  margin-top: 36px;
  padding-top: 24px;
  border-top: 1px solid var(--color-outline-variant);
}
.provider-strip-label {
  font-size: 11px;
  color: var(--color-on-surface-variant);
  text-align: center;
  margin-bottom: 12px;
  letter-spacing: 0.03em;
}
.provider-icons {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
}
.provider-icon {
  width: 24px;
  height: 24px;
  object-fit: contain;
  opacity: 0.55;
  transition: opacity 0.2s, transform 0.2s;
}
.provider-icon:hover {
  opacity: 1;
  transform: scale(1.1);
}

/* ── Responsive: hide hero on mobile ── */
@media (max-width: 768px) {
  .hero-panel {
    display: none;
  }
  .mobile-logo {
    display: flex;
  }
}

/* ── Dark Mode ── */
:global(html.dark) .form-panel {
  background: var(--color-surface);
}
:global(html.dark) .auth-submit-btn {
  box-shadow: 0 4px 20px rgba(99, 102, 241, 0.25);
}
:global(html.dark) .auth-submit-btn:hover:not(:disabled) {
  box-shadow: 0 6px 28px rgba(99, 102, 241, 0.4);
}
</style>
