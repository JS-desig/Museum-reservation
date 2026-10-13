import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/login', component: () => import('../views/Login.vue'), meta: { public: true } },
  {
    path: '/gate',
    component: () => import('../views/GateTerminal.vue'),
    meta: { public: true, standalone: true },
  },
  {
    path: '/',
    component: () => import('../views/Layout.vue'),
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', component: () => import('../views/Dashboard.vue'), meta: { title: '数据看板' } },
      { path: 'reservations', component: () => import('../views/Reservations.vue'), meta: { title: '预约管理' } },
      { path: 'check-records', component: () => import('../views/CheckRecords.vue'), meta: { title: '核销记录' } },
      { path: 'announcements', component: () => import('../views/Announcements.vue'), meta: { title: '公告管理' } },
      { path: 'exhibits', component: () => import('../views/Exhibits.vue'), meta: { title: '展品管理' } },
      { path: 'venue', component: () => import('../views/VenueConfig.vue'), meta: { title: '场馆配置' } },
      { path: 'slots', component: () => import('../views/Slots.vue'), meta: { title: '时段容量' } },
      { path: 'blacklist', component: () => import('../views/Blacklist.vue'), meta: { title: '黑名单' } },
      { path: 'accounts', component: () => import('../views/Accounts.vue'), meta: { title: '账号权限', adminOnly: true } },
    ],
  },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(to => {
  if (to.meta.public) return true
  if (!localStorage.getItem('token')) return '/login'
  return true
})

export default router
