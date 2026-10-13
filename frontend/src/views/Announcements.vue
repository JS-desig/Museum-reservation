<template>
  <el-card>
    <div class="toolbar">
      <span class="toolbar-title">公告列表</span>
      <span class="spacer"></span>
      <el-button type="primary" @click="openDlg()">发布公告</el-button>
    </div>
    <el-table :data="rows" border stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="title" label="标题" min-width="320" />
      <el-table-column label="类型" width="110">
        <template #default="{ row }">
          <el-tag :type="{ notice: 'info', closure: 'danger', activity: 'success' }[row.type]">
            {{ { notice: '通知', closure: '临时闭馆', activity: '活动' }[row.type] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_published ? 'success' : 'info'">{{ row.is_published ? '已发布' : '草稿' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="publish_time" label="发布时间" width="170" />
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDlg(row)">编辑</el-button>
          <el-popconfirm title="确认删除?" @confirm="del(row)">
            <template #reference><el-button link type="danger">删除</el-button></template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dlg" :title="form.id ? '编辑公告' : '发布公告'" width="560px">
      <el-form label-width="80px">
        <el-form-item label="标题"><el-input v-model="form.title" /></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.type">
            <el-option label="通知" value="notice" />
            <el-option label="临时闭馆" value="closure" />
            <el-option label="活动" value="activity" />
          </el-select>
        </el-form-item>
        <el-form-item label="内容"><el-input v-model="form.content" type="textarea" :rows="4" /></el-form-item>
        <el-form-item label="立即发布"><el-switch v-model="form.is_published" :active-value="1" :inactive-value="0" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'

const rows = ref([])
const dlg = ref(false)
const form = reactive({ id: null, title: '', content: '', type: 'notice', is_published: 0 })

async function load() {
  const { data } = await http.get('/admin/announcements')
  rows.value = data
}
function openDlg(row) {
  Object.assign(form, row || { id: null, title: '', content: '', type: 'notice', is_published: 0 })
  dlg.value = true
}
async function save() {
  if (form.id) await http.put(`/admin/announcements/${form.id}`, form)
  else await http.post('/admin/announcements', form)
  ElMessage.success('已保存')
  dlg.value = false
  load()
}
async function del(row) {
  await http.delete(`/admin/announcements/${row.id}`)
  ElMessage.success('已删除')
  load()
}
onMounted(load)
</script>
