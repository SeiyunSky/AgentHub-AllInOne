<template>
  <div class="min-h-screen bg-gradient-to-br from-surface via-brand-light/30 to-surface flex items-center justify-center">
    <div class="text-center">
      <div v-if="status === 'loading'" class="text-on-surface-variant text-sm">
        <div class="w-8 h-8 border-2 border-brand border-t-transparent rounded-full animate-spin mx-auto mb-3"></div>
        正在完成登录...
      </div>
      <div v-else-if="status === 'error'" class="text-error text-sm">
        {{ errorMsg }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import type { TokenResponse, UserPublic } from '@/api/auth'

const router = useRouter()
const auth = useAuthStore()

const status = ref<'loading' | 'error'>('loading')
const errorMsg = ref('')

onMounted(() => {
  const params = new URLSearchParams(window.location.search)

  const error = params.get('error')
  if (error) {
    status.value = 'error'
    errorMsg.value = decodeURIComponent(error.replace(/\+/g, ' '))
    setTimeout(() => router.replace({ name: 'login', query: { error: errorMsg.value } }), 2000)
    return
  }

  const accessToken = params.get('access_token')
  const refreshToken = params.get('refresh_token')
  const expiresIn = Number(params.get('expires_in') ?? '86400')
  const username = params.get('username') ?? ''
  const displayName = params.get('display_name') ?? username

  if (!accessToken || !refreshToken || !username) {
    status.value = 'error'
    errorMsg.value = '登录参数缺失，请重试'
    setTimeout(() => router.replace({ name: 'login' }), 2000)
    return
  }

  // 构造最小 UserPublic（id 由后续 /me 补全，此处用空串占位）
  const user: UserPublic = {
    id: '',
    username,
    display_name: displayName,
  }

  const tokenResponse: TokenResponse = {
    access_token: accessToken,
    refresh_token: refreshToken,
    token_type: 'bearer',
    expires_in: expiresIn,
    user,
  }

  auth.setSession(tokenResponse)

  // 跳转目标（支持 redirect query，否则进 chat）
  const redirect = params.get('redirect') || '/chat'
  router.replace(redirect)
})
</script>
