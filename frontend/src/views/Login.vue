<template>
  <div class="login-wrap">
    <!-- 背景装饰 -->
    <div class="bg-deco bg-deco-1"></div>
    <div class="bg-deco bg-deco-2"></div>
    <div class="bg-deco bg-deco-3"></div>

    <div class="login-panel">
      <!-- 左侧品牌区 -->
      <div class="brand-side">
        <div class="brand-mark">🏛</div>
        <h1 class="brand-title">菏泽市科技博物馆</h1>
        <p class="brand-sub">预约与门禁一体化管理平台</p>
        <ul class="brand-features">
          <li>实名预约 · 免费不免票</li>
          <li>闸机核销 · 客流实时管控</li>
          <li>数据看板 · 全链路对账</li>
        </ul>
      </div>

      <!-- 右侧表单区 -->
      <div class="form-side">
        <h2 class="form-title">欢迎登录</h2>
        <p class="form-hint">请使用后台管理员账号</p>
        <el-form :model="form" size="large" @keyup.enter="submit">
          <el-form-item>
            <el-input v-model="form.username" placeholder="用户名" clearable>
              <template #prefix><el-icon><User /></el-icon></template>
            </el-input>
          </el-form-item>
          <el-form-item>
            <el-input v-model="form.password" type="password" placeholder="密码" show-password>
              <template #prefix><el-icon><Lock /></el-icon></template>
            </el-input>
          </el-form-item>
          <el-button class="submit-btn" type="primary" size="large" :loading="loading" @click="submit">
            登 录
          </el-button>
        </el-form>
        <el-divider><span class="divider-text">演示账号</span></el-divider>
        <div class="demo-accounts">
          <div class="demo-item" @click="fill('admin', 'admin123')">
            <el-tag type="danger" size="small" effect="plain">admin</el-tag>
            <span>系统管理员 · admin / admin123</span>
          </div>
          <div class="demo-item" @click="fill('operator', 'operator123')">
            <el-tag type="primary" size="small" effect="plain">operator</el-tag>
            <span>场馆运营 · operator / operator123</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import http from '../api/http'

const form = reactive({ username: 'admin', password: '' })
const loading = ref(false)
const router = useRouter()

function fill(u, p) {
  form.username = u
  form.password = p
}

async function submit() {
  if (!form.username || !form.password) return ElMessage.warning('请输入用户名和密码')
  loading.value = true
  try {
    const { data } = await http.post('/admin/login', form)
    localStorage.setItem('token', data.token)
    localStorage.setItem('userInfo', JSON.stringify(data))
    router.push('/')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #12294d 0%, #1d3f72 45%, #2b5aa0 100%);
  position: relative;
  overflow: hidden;
}

/* 柔和光斑装饰 */
.bg-deco {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.35;
  pointer-events: none;
}
.bg-deco-1 { width: 480px; height: 480px; background: #4f8be0; top: -140px; left: -120px; }
.bg-deco-2 { width: 380px; height: 380px; background: #22a05a; bottom: -120px; right: -80px; opacity: 0.22; }
.bg-deco-3 { width: 300px; height: 300px; background: #e6a23c; bottom: 12%; left: 14%; opacity: 0.14; }

.login-panel {
  display: flex;
  width: 880px;
  max-width: calc(100vw - 48px);
  min-height: 500px;
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 24px 64px rgba(6, 18, 42, 0.45);
  position: relative;
  z-index: 1;
}

/* 左侧品牌 */
.brand-side {
  flex: 1;
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.14), rgba(255, 255, 255, 0.04));
  backdrop-filter: blur(8px);
  color: #fff;
  padding: 56px 44px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.brand-mark {
  font-size: 52px;
  width: 88px; height: 88px;
  display: flex; align-items: center; justify-content: center;
  background: rgba(255, 255, 255, 0.16);
  border-radius: 22px;
  margin-bottom: 28px;
}
.brand-title { font-size: 28px; font-weight: 700; letter-spacing: 2px; line-height: 1.4; }
.brand-sub { margin-top: 10px; font-size: 14px; opacity: 0.85; letter-spacing: 1px; }
.brand-features { margin-top: 44px; list-style: none; }
.brand-features li {
  padding: 9px 0;
  font-size: 14px;
  opacity: 0.92;
  display: flex;
  align-items: center;
  gap: 10px;
}
.brand-features li::before {
  content: '';
  width: 7px; height: 7px;
  border-radius: 50%;
  background: #6ee7a0;
  box-shadow: 0 0 8px #6ee7a0;
}

/* 右侧表单 */
.form-side {
  width: 400px;
  background: #fff;
  padding: 52px 44px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.form-title { font-size: 24px; font-weight: 700; color: var(--hz-text); }
.form-hint { margin: 8px 0 28px; color: var(--hz-text-secondary); font-size: 13px; }
.submit-btn { width: 100%; margin-top: 4px; letter-spacing: 6px; }

.divider-text { font-size: 12px; color: #b0b7c3; }
.demo-accounts { display: flex; flex-direction: column; gap: 10px; }
.demo-item {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 14px;
  background: #f7f9fc;
  border: 1px solid var(--hz-border);
  border-radius: 10px;
  font-size: 13px;
  color: var(--hz-text-secondary);
  cursor: pointer;
  transition: all 0.2s;
}
.demo-item:hover {
  border-color: var(--hz-primary);
  color: var(--hz-primary);
  background: var(--hz-primary-lighter);
}

@media (max-width: 820px) {
  .brand-side { display: none; }
  .form-side { width: 100%; }
}
</style>
