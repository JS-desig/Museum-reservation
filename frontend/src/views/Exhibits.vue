<template>
  <el-card>
    <div class="toolbar">
      <el-input v-model="keyword" placeholder="搜索标题 / 展厅" style="width:230px" clearable @keyup.enter="load" @clear="load">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-button type="primary" @click="load">搜索</el-button>
      <span class="spacer"></span>
      <el-button type="primary" @click="openDlg()">新增展品</el-button>
    </div>
    <el-table :data="rows" border stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="hall_name" label="展厅" width="150" />
      <el-table-column prop="title" label="展品" min-width="300" />
      <el-table-column prop="media_type" label="媒体" width="90" />
      <el-table-column prop="sort_order" label="排序" width="80" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status ? 'success' : 'info'">{{ row.status ? '上架' : '下架' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDlg(row)">编辑</el-button>
          <el-popconfirm title="确认删除?" @confirm="del(row)">
            <template #reference><el-button link type="danger">删除</el-button></template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dlg" :title="form.id ? '编辑展品' : '新增展品'" width="560px">
      <el-form label-width="80px">
        <el-form-item label="展厅"><el-input v-model="form.hall_name" /></el-form-item>
        <el-form-item label="标题"><el-input v-model="form.title" /></el-form-item>
        <el-form-item label="介绍"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="媒体类型">
          <el-select v-model="form.media_type">
            <el-option label="图片" value="image" />
            <el-option label="音频" value="audio" />
            <el-option label="视频" value="video" />
          </el-select>
        </el-form-item>
        <el-form-item label="媒体地址"><el-input v-model="form.media_url" /></el-form-item>
        <el-form-item label="排序"><el-input-number v-model="form.sort_order" /></el-form-item>
        <el-form-item label="上架"><el-switch v-model="form.status" :active-value="1" :inactive-value="0" /></el-form-item>
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
const keyword = ref('')
const dlg = ref(false)
const empty = { id: null, hall_name: '', title: '', description: '', media_type: 'image', media_url: '', sort_order: 0, status: 1 }
const form = reactive({ ...empty })

async function load() {
  const { data } = await http.get('/admin/exhibits', { params: { keyword: keyword.value } })
  rows.value = data
}
function openDlg(row) {
  Object.assign(form, row || empty)
  dlg.value = true
}
async function save() {
  if (form.id) await http.put(`/admin/exhibits/${form.id}`, form)
  else await http.post('/admin/exhibits', form)
  ElMessage.success('已保存')
  dlg.value = false
  load()
}
async function del(row) {
  await http.delete(`/admin/exhibits/${row.id}`)
  ElMessage.success('已删除')
  load()
}
onMounted(load)
</script>
