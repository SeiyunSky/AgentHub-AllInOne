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
        <h1 class="text-2xl font-bold text-on-surface tracking-tight">AgentHub</h1>
        <p class="text-[13px] text-on-surface-variant mt-1.5">Agent Orchestrator Platform</p>
      </div>

      <!-- Login Form -->
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        class="glass-panel rounded-2xl p-6 shadow-float border border-outline-variant"
        @submit.prevent="handleLogin"
      >
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            placeholder="Username"
            size="large"
            :prefix-icon="User"
            class="!rounded-xl"
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="Password"
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
            Sign In
          </el-button>
        </el-form-item>

        <!-- 分割线 -->
        <div class="flex items-center gap-3 my-1">
          <div class="flex-1 h-px bg-outline-variant"></div>
          <span class="text-[11px] text-on-surface-variant">or</span>
          <div class="flex-1 h-px bg-outline-variant"></div>
        </div>

        <!-- 微软账号登录 -->
        <el-form-item>
          <el-button
            size="large"
            class="w-full !rounded-xl !border !border-outline-variant !bg-surface hover:!bg-surface-variant !h-11 !font-medium !text-on-surface"
            :loading="msLoading"
            @click.prevent="handleMicrosoftLogin"
          >
            <img
              src="https://learn.microsoft.com/en-us/entra/identity-platform/media/howto-add-branding-in-apps/ms-symbollockup_mssymbol_19.svg"
              alt="Microsoft"
              class="w-4 h-4 mr-2"
              @error="(e) => (e.target as HTMLImageElement).style.display = 'none'"
            />
            Sign in with Microsoft
          </el-button>
        </el-form-item>

        <div v-if="errorMsg" class="text-center text-[12px] text-error mb-2">
          {{ errorMsg }}
        </div>

        <div class="text-center text-[13px] text-on-surface-variant">
          New here?
          <router-link
            :to="{ name: 'register', query: route.query }"
            class="text-brand font-semibold hover:underline ml-1"
          >
            Create an account
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
import { User, Lock } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)
const msLoading = ref(false)
const errorMsg = ref<string>('')

const form = reactive({
  username: '',
  password: '',
})

const rules: FormRules = {
  username: [{ required: true, message: 'Please enter username', trigger: 'blur' }],
  password: [{ required: true, message: 'Please enter password', trigger: 'blur' }],
}

async function handleLogin() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  errorMsg.value = ''

  try {
    const tokens = await authApi.login({
      username: form.username,
      password: form.password,
    })
    auth.setSession(tokens)

    const redirect = (route.query.redirect as string) || '/chat'
    router.push(redirect)
  } catch (err) {
    errorMsg.value = err instanceof Error ? err.message : '登录失败,请稍后重试'
  } finally {
    loading.value = false
  }
}

async function handleMicrosoftLogin() {
  msLoading.value = true
  errorMsg.value = ''
  try {
    const { url } = await authApi.getMicrosoftOAuthUrl()
    window.location.href = url
  } catch (err) {
    msLoading.value = false
    errorMsg.value = err instanceof Error ? err.message : '微软登录初始化失败,请稍后重试'
  }
}
</script>