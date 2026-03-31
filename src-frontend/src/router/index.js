import { createRouter, createWebHashHistory, createWebHistory } from 'vue-router'
import ApolloLayout from '@/components/layout/ApolloLayout.vue'

function createAppHistory() {
  if (typeof window !== 'undefined' && window.location.protocol === 'file:') {
    return createWebHashHistory()
  }

  return createWebHistory()
}

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
  history: createAppHistory(),
  routes
})

export default router