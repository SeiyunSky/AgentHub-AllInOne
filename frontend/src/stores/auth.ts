import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserPublic, TokenResponse } from '@/api/auth'

const LS_KEYS = {
  accessToken: 'auth.access_token',
  refreshToken: 'auth.refresh_token',
  user: 'auth.user',
  // 旧 key 兜底清理
  legacyToken: 'token',
  legacyUsername: 'username',
  legacyUserId: 'user_id',
} as const

function readUser(): UserPublic | null {
  const raw = localStorage.getItem(LS_KEYS.user)
  if (!raw) return null
  try {
    return JSON.parse(raw) as UserPublic
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string | null>(localStorage.getItem(LS_KEYS.accessToken))
  const refreshToken = ref<string | null>(localStorage.getItem(LS_KEYS.refreshToken))
  const user = ref<UserPublic | null>(readUser())

  const isLoggedIn = computed(() => !!accessToken.value)
  const username = computed(() => user.value?.username ?? null)
  const displayName = computed(() => user.value?.display_name || user.value?.username || null)

  function setSession(tokens: TokenResponse) {
    accessToken.value = tokens.access_token
    refreshToken.value = tokens.refresh_token
    user.value = tokens.user
    localStorage.setItem(LS_KEYS.accessToken, tokens.access_token)
    localStorage.setItem(LS_KEYS.refreshToken, tokens.refresh_token)
    localStorage.setItem(LS_KEYS.user, JSON.stringify(tokens.user))
    // 清掉旧 MVP 模式残留
    localStorage.removeItem(LS_KEYS.legacyToken)
    localStorage.removeItem(LS_KEYS.legacyUsername)
    localStorage.removeItem(LS_KEYS.legacyUserId)
  }

  function setAccessToken(t: string) {
    accessToken.value = t
    localStorage.setItem(LS_KEYS.accessToken, t)
  }

  function clear() {
    accessToken.value = null
    refreshToken.value = null
    user.value = null
    localStorage.removeItem(LS_KEYS.accessToken)
    localStorage.removeItem(LS_KEYS.refreshToken)
    localStorage.removeItem(LS_KEYS.user)
  }

  return {
    accessToken,
    refreshToken,
    user,
    isLoggedIn,
    username,
    displayName,
    setSession,
    setAccessToken,
    clear,
  }
})
