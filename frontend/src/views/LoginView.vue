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
        <div class="w-16 h-16 rounded-2xl bg-gradient-to-br from-brand to-brand-dark mx-auto flex items-center justify-center text-white text-2xl font-bold mb-4 shadow-glow">
          N
        </div>
        <h1 class="text-2xl font-bold text-on-surface tracking-tight">Nexus AI</h1>
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

        <div class="text-center text-[11px] text-on-surface-variant">
          Demo mode — enter any username/password
        </div>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { User, Lock } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)

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

  // Mock login - no backend yet
  setTimeout(() => {
    auth.setToken('mock-token-' + Date.now(), form.username)
    loading.value = false

    // Redirect to chat or the original destination
    const redirect = route.query.redirect as string || '/chat'
    router.push(redirect)
  }, 500)
}
</script>