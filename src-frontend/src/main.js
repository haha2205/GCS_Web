import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'

// 创建 Vue 应用实例
const app = createApp(App)

// 使用 Pinia（状态管理）
app.use(createPinia())

// 使用 Vue Router（路由管理）
app.use(router)

// 挂载应用
app.mount('#app')