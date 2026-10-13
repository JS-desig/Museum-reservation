<template>
  <el-card>
    <div class="toolbar">
      <el-date-picker v-model="query.date_str" type="date" value-format="YYYY-MM-DD" placeholder="日期" clearable style="width:150px" />
      <el-select v-model="query.result" placeholder="核销结果" clearable style="width:130px">
        <el-option label="成功" value="success" />
        <el-option label="失败" value="fail" />
      </el-select>
      <el-input v-model="query.gate_id" placeholder="闸机编号" style="width:150px" clearable @keyup.enter="load" @clear="load" />
      <el-button type="primary" @click="load">查询</el-button>
    </div>

    <el-table :data="rows" border stripe v-loading="loading">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column label="方式" width="90">
        <template #default="{ row }">{{ row.check_type === 'qrcode' ? '扫码' : '身份证' }}</template>
      </el-table-column>
      <el-table-column prop="credential" label="凭证" min-width="180" />
      <el-table-column prop="reservation_id" label="预约ID" width="90" />
      <el-table-column label="方向" width="80">
        <template #default="{ row }">
          <el-tag :type="row.direction === 'in' ? 'success' : 'warning'" size="small">
            {{ row.direction === 'in' ? '入馆' : '出馆' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="结果" width="90">
        <template #default="{ row }">
          <el-tag :type="row.result === 'success' ? 'success' : 'danger'" size="small">
            {{ row.result === 'success' ? '成功' : failLabel(row.fail_reason) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="gate_id" label="闸机" width="110" />
      <el-table-column prop="device_seq" label="指令序号" min-width="160" />
      <el-table-column label="离线补传" width="90">
        <template #default="{ row }">
          <el-tag v-if="row.synced_offline" type="warning" size="small">是</el-tag>
          <el-tag v-else type="info" size="small">否</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="时间" width="170" />
    </el-table>

    <div class="table-footer">
      <el-pagination background layout="total, sizes, prev, pager, next"
                     :page-sizes="[20, 50, 100]"
                     :total="total" :page-size="query.size" v-model:current-page="query.page"
                     @current-change="load" @size-change="onSizeChange" />
    </div>
  </el-card>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import http from '../api/http'

const failReasonMap = {
  60001: '无效码', 60002: '重复核销', 60003: '未预约', 60004: '错峰',
  60005: '黑名单', 60006: '已取消', 60007: '已过期',
}
const failLabel = r => failReasonMap[r] || (typeof r === 'string' ? r : '失败')

const query = reactive({ page: 1, size: 20, result: '', gate_id: '', date_str: '' })
const rows = ref([])
const total = ref(0)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const { data } = await http.get('/admin/check-records', { params: query })
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}
onMounted(load)

function onSizeChange(size) {
  query.size = size
  query.page = 1
  load()
}
</script>

<style scoped>
.table-footer { display: flex; justify-content: flex-end; margin-top: 16px; }
</style>
