<template>
  <div class="auth-layout">
    <!-- ── Left Hero Panel ── -->
    <div class="hero-panel">
      <div class="hero-dots"></div>
      <div class="hero-orb hero-orb-1"></div>
      <div class="hero-orb hero-orb-2"></div>

      <div class="hero-content">
        <div class="hero-brand">
          <div class="hero-logo">🐧</div>
          <div>
            <div class="hero-title">AgentHub</div>
            <div class="hero-subtitle">Agent Orchestrator Platform</div>
          </div>
        </div>

        <div class="agents-orbit" aria-hidden="true">
          <div class="orbit-ring"></div>
          <img v-for="(icon, i) in agentIcons" :key="i"
            :src="icon.src" :alt="icon.name"
            class="orbit-icon"
            :style="orbitStyle(i, agentIcons.length)"
          />
          <div class="orbit-hub">
            <div class="orbit-hub-inner">🚀</div>
          </div>
        </div>

        <div class="hero-steps">
          <div v-for="(step, i) in steps" :key="i" class="hero-step">
            <div class="hero-step-num">{{ i + 1 }}</div>
            <div class="hero-step-text">{{ step }}</div>
          </div>
        </div>

        <div class="hero-pills">
          <span v-for="pill in pills" :key="pill" class="hero-pill">{{ pill }}</span>
        </div>
      </div>
    </div>

    <!-- ── Right Form Panel ── -->
    <div class="form-panel">
      <div class="form-inner fade-in-up">
        <!-- Mobile logo -->
        <div class="mobile-logo">
          <div class="mobile-logo-icon">🐧</div>
          <h1 class="mobile-logo-name">AgentHub</h1>
        </div>

        <h2 class="form-heading">Create account</h2>
        <p class="form-sub">Join the Agent Orchestrator Platform</p>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          class="auth-form"
          @submit.prevent="handleRegister"
        >
          <el-form-item prop="username">
            <el-input
              v-model="form.username"
              placeholder="Username (4-50 chars, a-z 0-9 _ -)"
              size="large"
              :prefix-icon="User"
              class="auth-input"
            />
          </el-form-item>

          <el-form-item prop="display_name">
            <el-input
              v-model="form.display_name"
              placeholder="Display name (optional)"
              size="large"
              :prefix-icon="Avatar"
              class="auth-input"
            />
          </el-form-item>

          <el-form-item prop="email">
            <el-input
              v-model="form.email"
              placeholder="Email (optional)"
              size="large"
              :prefix-icon="Message"
              class="auth-input"
            />
          </el-form-item>

          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="Password (min 8 chars)"
              size="large"
              :prefix-icon="Lock"
              show-password
              class="auth-input"
            />
          </el-form-item>

          <el-form-item prop="confirmPassword">
            <el-input
              v-model="form.confirmPassword"
              type="password"
              placeholder="Confirm password"
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
              <span v-if="!loading" class="btn-label">Create Account</span>
              <span v-else class="btn-spinner">
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
                <span class="typing-dot"></span>
              </span>
            </button>
          </el-form-item>

          <div v-if="errorMsg" class="auth-error">{{ errorMsg }}</div>

          <div class="auth-switch">
            Already have an account?
            <router-link :to="{ name: 'login', query: route.query }" class="auth-link">
              Sign in
            </router-link>
          </div>
        </el-form>

        <div class="provider-strip">
          <div class="provider-strip-label">Supports leading AI providers</div>
          <div class="provider-icons">
            <img v-for="p in providers" :key="p.name" :src="p.src" :alt="p.name" class="provider-icon" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { authApi } from '@/api/auth'
import { User, Lock, Message, Avatar } from '@element-plus/icons-vue'
import type { FormInstance, FormItemRule, FormRules } from 'element-plus'

import claudecodeIcon from '@/assets/icons/claudecode-color.svg'
import codexIcon from '@/assets/icons/codex-color.svg'
import opencodeIcon from '@/assets/icons/opencode.svg'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)
const errorMsg = ref('')

const form = reactive({
  username: '',
  display_name: '',
  email: '',
  password: '',
  confirmPassword: '',
})

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

const pills = ['Free to Join', 'No Credit Card', 'Instant Access']
const steps = [
  'Create your account in seconds',
  'Configure AI agents with custom prompts',
  'Orchestrate parallel conversations',
]

function orbitStyle(i: number, total: number) {
  const angle = (i / total) * 360
  const r = 90
  const rad = (angle * Math.PI) / 180
  const x = Math.cos(rad) * r
  const y = Math.sin(rad) * r
  return {
    transform: `translate(calc(-50% + ${x}px), calc(-50% + ${y}px))`,
    animationDelay: `${i * 0.6}s`,
  }
}

const validateConfirmPassword: FormItemRule['validator'] = (_rule, value, cb) => {
  if (!value) return cb(new Error('Please confirm your password'))
  if (value !== form.password) return cb(new Error('Passwords do not match'))
  cb()
}

const validateEmail: FormItemRule['validator'] = (_rule, value, cb) => {
  if (!value) return cb()
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return cb(new Error('Invalid email format'))
  cb()
}

const rules: FormRules = {
  username: [
    { required: true, message: 'Please enter username', trigger: 'blur' },
    { min: 4, max: 50, message: 'Username must be 4-50 characters', trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_-]+$/, message: 'Only letters, digits, _ and - are allowed', trigger: 'blur' },
  ],
  password: [
    { required: true, message: 'Please enter password', trigger: 'blur' },
    { min: 8, max: 128, message: 'Password must be at least 8 characters', trigger: 'blur' },
  ],
  confirmPassword: [{ required: true, validator: validateConfirmPassword, trigger: 'blur' }],
  email: [{ validator: validateEmail, trigger: 'blur' }],
  display_name: [{ max: 100, message: 'Display name too long', trigger: 'blur' }],
}

async function handleRegister() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  errorMsg.value = ''

  try {
    await authApi.register({
      username: form.username,
      password: form.password,
      email: form.email || undefined,
      display_name: form.display_name || undefined,
    })
    const tokens = await authApi.login({ username: form.username, password: form.password })
    auth.setSession(tokens)
    const redirect = (route.query.redirect as string) || '/chat'
    router.push(redirect)
  } catch (err) {
    errorMsg.value = err instanceof Error ? err.message : '注册失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-layout {
  display: flex;
  min-height: 100vh;
  background: var(--color-surface);
}

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
  gap: 28px;
  padding: 40px 32px;
  max-width: 400px;
  width: 100%;
}

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
.orbit-hub-inner { font-size: 22px; }
@keyframes hub-pulse {
  0%, 100% { box-shadow: 0 0 24px rgba(99, 102, 241, 0.5), 0 0 48px rgba(99, 102, 241, 0.2); }
  50% { box-shadow: 0 0 40px rgba(99, 102, 241, 0.7), 0 0 80px rgba(99, 102, 241, 0.35); }
}

/* Steps */
.hero-steps {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
  animation: hero-enter 0.6s 0.3s var(--ease-out) both;
}
.hero-step {
  display: flex;
  align-items: center;
  gap: 12px;
}
.hero-step-num {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: rgba(99, 102, 241, 0.5);
  border: 1px solid rgba(99, 102, 241, 0.6);
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.hero-step-text {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
}

.hero-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  animation: hero-enter 0.6s 0.45s var(--ease-out) both;
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
  overflow-y: auto;
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
  margin: 0 0 24px;
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

.provider-strip {
  margin-top: 28px;
  padding-top: 20px;
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

@media (max-width: 768px) {
  .hero-panel { display: none; }
  .mobile-logo { display: flex; }
}

:global(html.dark) .form-panel {
  background: var(--color-surface);
}
</style>
