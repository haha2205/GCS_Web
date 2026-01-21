import { createRouter, createWebHistory } from 'vue-router'
import ApolloLayout from '@/components/layout/ApolloLayout.vue'
import { useDroneStore } from '@/store/drone'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: ApolloLayout,
    meta: { requiresAuth: false }
  },
  // 通配符路由：捕获所有未知路径并重定向到根路径
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 全局路由守卫：初始化 WebSocket 连接
router.beforeEach((to, from, next) => {
  const droneStore = useDroneStore()
  // 在首次导航时自动连接 WebSocket
  if (from.name === undefined && to.name === 'Home') {
    droneStore.connect()
  }
  next()
})

export default router