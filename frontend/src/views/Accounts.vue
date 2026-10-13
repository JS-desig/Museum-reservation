<template>
  <div>
    <el-card>
      <div class="toolbar">
        <span class="toolbar-title">后台账号</span>
        <span class="spacer"></span>
        <el-button v-if="me.role === 'admin'" type="primary" @click="openDlg()">新增账号</el-button>
      </div>
      <el-alert v-if="me.role !== 'admin'" title="仅系统管理员可管理账号" type="info" :closable="false" style="margin-bottom:16px" />
    <el-table :data="rows" border stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="username" label="用户名" width="140" />
      <el-table-column prop="real_name" label="姓名" width="140" />
      <el-table-column label="角色" width="130">
        <template #default="{ row }">
          <el-tag :type="row.role === 'admin' ? 'danger' : 'primary'">
            {{ row.role === 'admin' ? '系统管理员' : '场馆管理员' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status ? 'success' : 'info'">{{ row.status ? '启用' : '禁用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right" v-if="me.role === 'admin'">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDlg(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>
    </el-card>

    <el-card style="margin-top:16px">
      <template #header>
        <div class="card-head"><span class="card-head-bar"></span>操作审计日志（最近50条）</div>
      </template>
      <el-table :data="logs" border size="small">
        <el-table-column prop="created_at" label="时间" width="170" />
        <el-table-column prop="admin_name" label="操作人" width="110" />
        <el-table-column prop="action" label="动作" width="150" />
        <el-table-column prop="detail" label="详情" min-width="420" />
      </el-table>
    </el-card>

    <el-dialog v-model="dlg" :title="form.id ? '编辑账号' : '新增账号'" width="440px">
      <el-form label-width="80px">
        <el-form-item label="用户名"><el-input v-model="form.username" :disabled="!!form.id" /></el-form-item>
        <el-form-item :label="form.id ? '新密码' : '密码'">
          <el-input v-model="form.password" type="password" show-password
                    :placeholder="form.id ? '留空则不修改' : '至少6位'" />
        </el-form-item>
        <el-form-item label="姓名"><el-input v-model="form.real_name" /></el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role">
            <el-option label="系统管理员" value="admin" />
            <el-option label="场馆管理员" value="operator" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.status" :active-value="1" :inactive-value="0" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'

const me = JSON.parse(localStorage.getItem('userInfo') || '{}')
const rows = ref([])
const logs = ref([])
const dlg = ref(false)
const empty = { id: null, username: '', password: '', real_name: '', role: 'operator', status: 1 }
const form = reactive({ ...empty })

async function load() {
  const { data } = await http.get('/admin/users')
  rows.value = data
  const { data: ld } = await http.get('/admin/audit-logs', { params: { page: 1, size: 50 } })
  logs.value = ld.items
}
function openDlg(row) {
  Object.assign(form, row ? { ...row, password: '' } : empty)
  dlg.value = true
}
async function save() {
  if (form.id) await http.put(`/admin/users/${form.id}`, form)
  else await http.post('/admin/users', form)
  ElMessage.success('已保存')
  dlg.value = false
  load()
}
onMounted(load)
</script>

<style scoped>
.card-head { display: flex; align-items: center; gap: 8px; }
.card-head-bar {
  width: 4px; height: 16px;
  border-radius: 2px;
  background: var(--hz-primary);
}
</style>
