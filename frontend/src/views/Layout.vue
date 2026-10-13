<template>
  <el-container style="height:100vh">
    <el-aside width="224px" class="aside">
      <div class="logo">
        <span class="logo-icon">🏛</span>
        <div class="logo-text">
          <div class="logo-name">菏泽科技博物馆</div>
          <div class="logo-sub">预约与门禁管理</div>
        </div>
      </div>
      <el-menu :default-active="activePath" router text-color="#b8c4d8"
               active-text-color="#ffffff" class="menu">
        <el-menu-item v-for="item in menus" :key="item.path" :index="item.path"
                      v-show="!item.adminOnly || userInfo.role === 'admin'">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu>
      <div class="aside-footer">
        <el-tag effect="dark" size="small" style="background:rgba(255,255,255,.14);border:none">
          v2.0
        </el-tag>
      </div>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-left">
          <span class="page-title">{{ $route.meta.title || '管理后台' }}</span>
        </div>
        <div class="header-right">
          <div class="gate-entry" @click="$router.push('/gate')">
            <span class="gate-dot"></span> 闸机终端
          </div>
          <el-dropdown @command="onUserCmd">
            <div class="user-chip">
              <el-avatar :size="30" style="background:var(--hz-primary-light)">
                {{ avatarText }}
              </el-avatar>
              <span class="user-name">{{ displayName }}</span>
              <el-tag size="small" :type="userInfo.role === 'admin' ? 'danger' : 'primary'" effect="plain">
                {{ roleLabel }}
              </el-tag>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">
                  <el-icon><SwitchButton /></el-icon>退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'

const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}')
const router = useRouter()
const route = useRoute()

const menus = [
  { path: '/dashboard', icon: 'DataBoard', label: '数据看板' },
  { path: '/reservations', icon: 'Tickets', label: '预约管理' },
  { path: '/check-records', icon: 'CircleCheck', label: '核销记录' },
  { path: '/announcements', icon: 'Bell', label: '公告管理' },
  { path: '/exhibits', icon: 'OfficeBuilding', label: '展品管理' },
  { path: '/venue', icon: 'Location', label: '场馆配置' },
  { path: '/slots', icon: 'Clock', label: '时段容量' },
  { path: '/blacklist', icon: 'Warning', label: '黑名单' },
  { path: '/accounts', icon: 'UserFilled', label: '账号权限', adminOnly: true },
]

const activePath = computed(() => '/' + (route.path.split('/')[1] || 'dashboard'))
const roleLabel = computed(() => userInfo.role === 'admin' ? '系统管理员' : '场馆管理员')
const displayName = computed(() => userInfo.real_name || userInfo.username || '未登录')
const avatarText = computed(() => displayName.value.slice(0, 1).toUpperCase())

function onUserCmd(cmd) {
  if (cmd === 'logout') {
    localStorage.removeItem('token')
    localStorage.removeItem('userInfo')
    ElMessage.success('已退出登录')
    router.push('/login')
  }
}
</script>

<style scoped>
.aside {
  background: linear-gradient(180deg, #16294a 0%, #1d3f72 100%);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.logo {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 20px 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.logo-icon {
  font-size: 26px;
  width: 44px; height: 44px;
  display: flex; align-items: center; justify-content: center;
  background: rgba(255, 255, 255, 0.12);
  border-radius: 12px;
}
.logo-name { color: #fff; font-size: 16px; font-weight: 700; letter-spacing: 1px; }
.logo-sub { color: #8fa3c4; font-size: 11px; margin-top: 2px; letter-spacing: 2px; }

.menu { border-right: none; flex: 1; padding: 10px 0; background: transparent; }
.menu :deep(.el-menu-item) {
  height: 46px;
  margin: 3px 10px;
  border-radius: 9px;
  transition: all 0.18s;
}
.menu :deep(.el-menu-item:hover) { background: rgba(255, 255, 255, 0.08); }
.menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(90deg, #2b5aa0, #3a6db5);
  box-shadow: 0 2px 10px rgba(43, 90, 160, 0.5);
}
.aside-footer { padding: 14px 20px; border-top: 1px solid rgba(255, 255, 255, 0.08); }

.header {
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 1px 4px rgba(29, 63, 114, 0.08);
  z-index: 5;
}
.page-title { font-size: 17px; font-weight: 700; color: var(--hz-text); }
.header-right { display: flex; align-items: center; gap: 18px; }

.gate-entry {
  display: flex; align-items: center; gap: 7px;
  padding: 6px 14px;
  border: 1px solid #b7e4c7;
  background: #edfaf1;
  color: var(--hz-success);
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}
.gate-entry:hover { background: #d9f5e4; box-shadow: 0 2px 8px rgba(34, 160, 90, 0.2); }
.gate-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--hz-success);
  box-shadow: 0 0 0 3px rgba(34, 160, 90, 0.18);
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 3px rgba(34, 160, 90, 0.18); }
  50% { box-shadow: 0 0 0 6px rgba(34, 160, 90, 0.08); }
}

.user-chip {
  display: flex; align-items: center; gap: 9px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 10px;
  transition: background 0.2s;
}
.user-chip:hover { background: #f4f6fa; }
.user-name { font-size: 14px; font-weight: 600; }

.main { background: var(--hz-bg); padding: 18px 24px; overflow: auto; }
</style>
