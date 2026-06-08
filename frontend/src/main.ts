import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import router from './router/index'
import { useAuthStore } from './stores/auth'
import { i18n } from './i18n'

import './style.css'
import 'element-plus/dist/index.css'

const app = createApp(App)

// Register Element Plus Icons globally
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

const pinia = createPinia()
app.use(pinia)
app.use(router)
app.use(ElementPlus)
app.use(i18n)

// 监听 http.ts 派发的 token 失效事件:清状态 + 跳登录页
window.addEventListener('auth:expired', () => {
  const auth = useAuthStore()
  auth.clear()
  const current = router.currentRoute.value
  if (current.name !== 'login') {
    router.push({ name: 'login', query: { redirect: current.fullPath } })
  }
})

app.mount('#app')
