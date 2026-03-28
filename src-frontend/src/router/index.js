import { createRouter, createWebHistory } from 'vue-router'
import ApolloLayout from '@/components/layout/ApolloLayout.vue'

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

export default router