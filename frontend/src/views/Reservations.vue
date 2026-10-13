<template>
  <el-card>
    <div class="toolbar">
      <el-date-picker v-model="query.date_str" type="date" value-format="YYYY-MM-DD" placeholder="参观日期" clearable style="width:150px" />
      <el-select v-model="query.status" placeholder="状态" clearable style="width:130px">
        <el-option v-for="(label, val) in statusMap" :key="val" :label="label" :value="val" />
      </el-select>
      <el-input v-model="query.keyword" placeholder="预约码 / 姓名 / 证件" style="width:230px" clearable @keyup.enter="load" @clear="load">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-button type="primary" @click="load">查询</el-button>
      <span class="spacer"></span>
      <el-button plain @click="manualDlg = true">手动核销 / 取消</el-button>
    </div>

    <el-table :data="rows" border stripe v-loading="loading">
      <el-table-column prop="resv_code" label="预约码" width="150" />
      <el-table-column prop="user_phone" label="手机号" width="130" />
      <el-table-column prop="visit_date" label="参观日期" width="110" />
      <el-table-column prop="session_name" label="时段" width="90" />
      <el-table-column label="游客" min-width="360">
        <template #default="{ row }">
          <el-tag v-for="v in row.visitors" :key="v.id_card" size="small" effect="plain"
                  :type="v.checked_in ? 'success' : 'info'" class="visitor-tag">
            {{ v.checked_in ? '✓ ' : '' }}{{ v.name }}·{{ v.id_card.slice(-4) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="visitor_count" label="人数" width="70" align="center" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)">{{ statusMap[row.status] || row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="checked_in_at" label="核销时间" width="170" />
      <el-table-column prop="checked_out_at" label="出馆时间" width="170" />
    </el-table>

    <div class="table-footer">
      <el-pagination background layout="total, sizes, prev, pager, next"
                     :page-sizes="[20, 50, 100]"
                     :total="total" :page-size="query.size" v-model:current-page="query.page"
                     @current-change="load" @size-change="onSizeChange" />
    </div>

    <!-- 手动核销/取消 -->
    <el-dialog v-model="manualDlg" title="手动核销/取消异常预约" width="420px">
      <el-form label-width="90px">
        <el-form-item label="预约码">
          <el-input v-model="manual.code" placeholder="12位预约码" />
        </el-form-item>
        <el-form-item label="操作">
          <el-radio-group v-model="manual.action">
            <el-radio value="check_in">手动核销入馆</el-radio>
            <el-radio value="cancel">取消预约</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="manualDlg = false">取消</el-button>
        <el-button type="primary" @click="doManual">确定</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'

const statusMap = {
  booked: '已预约', checked_in: '已核销', cancelled: '已取消',
  expired: '已过期', no_show: '爽约',
}
const statusType = s => ({ booked: 'primary', checked_in: 'success', cancelled: 'info', expired: 'warning', no_show: 'danger' }[s] || 'info')

const query = reactive({ page: 1, size: 20, date_str: '', status: '', keyword: '' })
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const manualDlg = ref(false)
const manual = reactive({ code: '', action: 'check_in' })

async function load() {
  loading.value = true
  try {
    const { data } = await http.get('/admin/stats/reservations', { params: query })
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function doManual() {
  await http.post('/admin/reservations/manual', manual)
  ElMessage.success('操作成功')
  manualDlg.value = false
  load()
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
.visitor-tag { margin-right: 6px; margin-bottom: 4px; font-family: monospace; }
</style>
