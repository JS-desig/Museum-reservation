<template>
  <el-card>
    <div class="toolbar">
      <span class="toolbar-title">时段模板</span>
      <span class="spacer"></span>
      <el-button type="primary" @click="openDlg()">新增时段</el-button>
    </div>

    <el-row :gutter="16">
      <el-col :xs="24" :sm="12" :lg="8" v-for="row in rows" :key="row.id">
        <div class="slot-card" :class="{ inactive: !row.is_active }">
          <div class="slot-head">
            <span class="slot-name">{{ row.name }}</span>
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用中' : '已停用' }}
            </el-tag>
          </div>
          <div class="slot-time">🕘 {{ row.start_time }} - {{ row.end_time }}</div>
          <div class="slot-cap">
            <div class="cap-num"><b>{{ row.capacity }}</b><span> 人 / 场</span></div>
            <el-progress :percentage="capacityPct(row.capacity)" :stroke-width="8"
                         :color="row.is_active ? '#2b5aa0' : '#c0c4cc'" />
            <div class="cap-hint">占每日总容量 {{ capacityPct(row.capacity) }}%</div>
          </div>
          <div class="slot-ops">
            <el-button link type="primary" @click="openDlg(row)">编辑</el-button>
          </div>
        </div>
      </el-col>
      <el-col :xs="24" v-if="!rows.length">
        <el-empty description="暂无时段模板, 点击右上角新增" />
      </el-col>
    </el-row>

    <el-dialog v-model="dlg" :title="form.id ? '编辑时段' : '新增时段'" width="440px">
      <el-form label-width="80px">
        <el-form-item label="时段名"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="开始时间"><el-time-select v-model="form.start_time" start="08:00" end="18:00" step="00:30" /></el-form-item>
        <el-form-item label="结束时间"><el-time-select v-model="form.end_time" start="08:00" end="18:00" step="00:30" /></el-form-item>
        <el-form-item label="容量"><el-input-number v-model="form.capacity" :min="50" :step="100" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.is_active" :active-value="1" :inactive-value="0" /></el-form-item>
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
const empty = { id: null, name: '', start_time: '09:00', end_time: '12:00', capacity: 2000, is_active: 1 }
const form = reactive({ ...empty })

async function load() {
  const { data } = await http.get('/admin/slots')
  rows.value = data
}
function capacityPct(cap) {
  const total = rows.value.reduce((s, r) => s + r.capacity, 0)
  return total ? Math.round(cap / total * 100) : 0
}
function openDlg(row) {
  Object.assign(form, row || empty)
  dlg.value = true
}
async function save() {
  if (form.id) await http.put(`/admin/slots/${form.id}`, form)
  else await http.post('/admin/slots', form)
  ElMessage.success('已保存')
  dlg.value = false
  load()
}
onMounted(load)
</script>

<style scoped>
.slot-card {
  background: #fff;
  border: 1px solid var(--hz-border);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: var(--hz-shadow);
  transition: transform 0.2s, box-shadow 0.2s;
}
.slot-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 20px rgba(29, 63, 114, 0.14);
}
.slot-card.inactive { opacity: 0.62; background: #fafbfc; }
.slot-head { display: flex; justify-content: space-between; align-items: center; }
.slot-name { font-size: 17px; font-weight: 700; color: var(--hz-text); }
.slot-time { color: var(--hz-text-secondary); font-size: 13px; margin: 10px 0 14px; }
.slot-cap { margin-bottom: 8px; }
.cap-num b { font-size: 24px; color: var(--hz-primary); }
.cap-num span { color: #9aa3b2; font-size: 12px; margin-left: 4px; }
.cap-hint { color: #9aa3b2; font-size: 12px; margin-top: 6px; }
.slot-ops { display: flex; justify-content: flex-end; border-top: 1px dashed var(--hz-border); padding-top: 10px; }
</style>
