<template>
  <div class="min-h-screen bg-gradient-to-br from-surface via-brand-light/30 to-surface flex items-center justify-center relative overflow-hidden">
    <!-- Decorative background -->
    <div class="absolute inset-0 overflow-hidden pointer-events-none">
      <div class="absolute -top-40 -right-40 w-80 h-80 bg-brand/5 rounded-full blur-3xl"></div>
      <div class="absolute -bottom-40 -left-40 w-80 h-80 bg-brand/8 rounded-full blur-3xl"></div>
    </div>

    <div class="w-full max-w-md p-8 relative z-10">
      <!-- Logo -->
      <div class="text-center mb-8">
        <div class="w-16 h-16 rounded-2xl bg-gradient-to-br from-brand to-brand-dark mx-auto flex items-center justify-center text-4xl mb-4 shadow-glow">
          🐧
        </div>
        <h1 class="text-2xl font-bold text-on-surface tracking-tight">Create account</h1>
        <p class="text-[13px] text-on-surface-variant mt-1.5">Join AgentHub Orchestrator Platform</p>
      </div>

      <!-- Register Form -->
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        class="glass-panel rounded-2xl p-6 shadow-float border border-outline-variant"
        @submit.prevent="handleRegister"
      >
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            placeholder="Username (4-50 chars, a-z 0-9 _ -)"
            size="large"
            :prefix-icon="User"
            class="!rounded-xl"
          />
        </el-form-item>

        <el-form-item prop="display_name">
          <el-input
            v-model="form.display_name"
            placeholder="Display name (optional)"
            size="large"
            :prefix-icon="Avatar"
            class="!rounded-xl"
          />
        </el-form-item>

        <el-form-item prop="email">
          <el-input
            v-model="form.email"
            placeholder="Email (optional)"
            size="large"
            :prefix-icon="Message"
            class="!rounded-xl"
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
            class="!rounded-xl"
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
            class="!rounded-xl"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            class="w-full !rounded-xl !bg-gradient-to-r !from-brand !to-brand-dark !border-0 !shadow-soft hover:!shadow-glow !h-11 !font-semibold"
            :loading="loading"
            native-type="submit"
          >
            Create Account
          </el-button>
        </el-form-item>

        <div v-if="errorMsg" class="text-center text-[12px] text-error mb-2">
          {{ errorMsg }}
        </div>

        <div class="text-center text-[13px] text-on-surface-variant">
          Already have an account?
          <router-link
            :to="{ name: 'login', query: route.query }"
            class="text-brand font-semibold hover:underline ml-1"
          >
            Sign in
          </router-link>
        </div>
      </el-form>
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

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)
const errorMsg = ref<string>('')

const form = reactive({
  username: '',
  display_name: '',
  email: '',
  password: '',
  confirmPassword: '',
})

// 与 backend/schemas/auth.py RegisterRequest 校验规则对齐
const validateConfirmPassword: FormItemRule['validator'] = (_rule, value, cb) => {
  if (!value) return cb(new Error('Please confirm your password'))
  if (value !== form.password) return cb(new Error('Passwords do not match'))
  cb()
}

const validateEmail: FormItemRule['validator'] = (_rule, value, cb) => {
  if (!value) return cb()  // optional
  // 简易 email 校验,后端会用 EmailStr 严格校验
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
    return cb(new Error('Invalid email format'))
  }
  cb()
}

const rules: FormRules = {
  username: [
    { required: true, message: 'Please enter username', trigger: 'blur' },
    { min: 4, max: 50, message: 'Username must be 4-50 characters', trigger: 'blur' },
    {
      pattern: /^[a-zA-Z0-9_-]+$/,
      message: 'Only letters, digits, _ and - are allowed',
      trigger: 'blur',
    },
  ],
  password: [
    { required: true, message: 'Please enter password', trigger: 'blur' },
    { min: 8, max: 128, message: 'Password must be at least 8 characters', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, validator: validateConfirmPassword, trigger: 'blur' },
  ],
  email: [{ validator: validateEmail, trigger: 'blur' }],
  display_name: [{ max: 100, message: 'Display name too long', trigger: 'blur' }],
}

async function handleRegister() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  errorMsg.value = ''

  try {
    // 1. 注册 → 拿到 UserPublic (不含 token)
    await authApi.register({
      username: form.username,
      password: form.password,
      email: form.email || undefined,
      display_name: form.display_name || undefined,
    })

    // 2. 自动登录 → 一步到位
    const tokens = await authApi.login({
      username: form.username,
      password: form.password,
    })
    auth.setSession(tokens)

    const redirect = (route.query.redirect as string) || '/chat'
    router.push(redirect)
  } catch (err) {
    errorMsg.value = err instanceof Error ? err.message : '注册失败,请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>
