import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '../views/ChatView.vue'
import ConfigView from '../views/ConfigView.vue'
import LoginView from '../views/LoginView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView },
    { path: '/', redirect: '/chat' },
    { path: '/chat', name: 'chat', component: ChatView },
    { path: '/config', component: ConfigView }
  ]
})

// 登录守卫：未登录只能访问 /login
router.beforeEach((to) => {
  const hasToken = !!localStorage.getItem('token')
  if (to.path !== '/login' && !hasToken) return '/login'
  if (to.path === '/login' && hasToken) return '/chat'
})

export default router
