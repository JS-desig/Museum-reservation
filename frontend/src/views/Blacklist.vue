<template>
  <el-card>
    <!-- 统计概览: 一眼看到拉黑规模 -->
    <div class="stats-row">
      <div class="stat-card stat-danger">
        <div class="stat-num">{{ total }}</div>
        <div class="stat-label">黑名单用户</div>
      </div>
      <div class="stat-card">
        <div class="stat-num">{{ userTotal }}</div>
        <div class="stat-label">注册用户总数</div>
      </div>
      <div class="spacer"></div>
      <el-input v-model="keyword" placeholder="搜索: 昵称 / 证件 / 手机 / 原因" style="width:260px"
                clearable @keyup.enter="onSearch" @clear="onSearch">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
    </div>

    <el-tabs v-model="tab" @tab-change="onTabChange">
      <!-- ============ 页签1: 全部用户 (拉黑操作主入口) ============ -->
      <el-tab-pane label="全部用户" name="users">
        <el-table :data="users" border stripe v-loading="usersLoading"
                  :row-class-name="rowClass">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column label="用户" min-width="160">
            <template #default="{ row }">
              <div class="user-cell">
                <span class="user-name">{{ row.nickname || '(未设置昵称)' }}</span>
                <el-tag v-if="row.is_blacklisted" type="danger" size="small" effect="dark">已拉黑</el-tag>
                <el-tag v-else-if="!row.is_verified" type="info" size="small">未实名</el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="id_card_masked" label="证件号" width="190">
            <template #default="{ row }">{{ row.id_card_masked || '—' }}</template>
          </el-table-column>
          <el-table-column prop="phone_masked" label="手机号" width="140">
            <template #default="{ row }">{{ row.phone_masked || '—' }}</template>
          </el-table-column>
          <el-table-column label="拉黑状态" width="230">
            <template #default="{ row }">
              <div v-if="row.is_blacklisted" class="reason-cell">
                <el-tag type="danger" size="small" effect="plain">黑名单</el-tag>
                <span class="reason-text" :title="row.blacklist_reason">{{ row.blacklist_reason || '未填写原因' }}</span>
              </div>
              <span v-else class="muted">正常</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button v-if="!row.is_blacklisted" link type="danger" @click="openBlackDlg(row)">
                <el-icon><CircleClose /></el-icon>&nbsp;拉黑
              </el-button>
              <template v-else>
                <el-button link type="warning" @click="openReasonDlg(row)">改原因</el-button>
                <el-popconfirm title="确认将该用户移出黑名单?" @confirm="unblack(row)">
                  <template #reference>
                    <el-button link type="success"><el-icon><CircleCheck /></el-icon>&nbsp;移出</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </template>
          </el-table-column>
          <template #empty>无匹配用户</template>
        </el-table>
        <div class="table-footer">
          <el-pagination background layout="total, prev, pager, next"
                         :total="userTotal" :page-size="userQuery.size"
                         v-model:current-page="userQuery.page" @current-change="loadUsers" />
        </div>
      </el-tab-pane>

      <!-- ============ 页签2: 黑名单列表 ============ -->
      <el-tab-pane name="blacklist">
        <template #label>
          <el-badge :value="total" :max="999" type="danger" class="tab-badge">黑名单</el-badge>
        </template>
        <el-table :data="rows" border v-loading="loading" row-class-name="danger-row">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column prop="nickname" label="昵称" min-width="140" />
          <el-table-column prop="real_name_masked" label="证件号" width="190">
            <template #default="{ row }">{{ row.real_name_masked || '—' }}</template>
          </el-table-column>
          <el-table-column prop="phone" label="手机号" width="140">
            <template #default="{ row }">{{ row.phone || '—' }}</template>
          </el-table-column>
          <el-table-column label="拉黑原因" min-width="240">
            <template #default="{ row }">
              <el-tag type="danger" size="small" effect="plain" class="reason-tag">黑名单</el-tag>
              <span v-if="row.reason">{{ row.reason }}</span>
              <span v-else class="muted">未填写</span>
            </template>
          </el-table-column>
          <el-table-column prop="blacklisted_at" label="拉黑时间" width="170">
            <template #default="{ row }">{{ fmtTime(row.blacklisted_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link type="warning" @click="openReasonDlg({ id: row.id, nickname: row.nickname, blacklist_reason: row.reason })">改原因</el-button>
              <el-popconfirm title="确认将该用户移出黑名单?" @confirm="unblack(row)">
                <template #reference>
                  <el-button link type="success">移出</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
          <template #empty>
            <el-empty description="黑名单为空" :image-size="80" />
          </template>
        </el-table>
        <div class="table-footer" v-if="total > rows.length || keyword">
          <el-pagination background layout="total, prev, pager, next"
                         :total="total" :page-size="query.size"
                         v-model:current-page="query.page" @current-change="loadBlacklist" />
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 拉黑确认弹窗 (填原因) -->
    <el-dialog v-model="blackDlg" title="加入黑名单" width="440px">
      <el-alert type="warning" :closable="false" show-icon class="dlg-alert"
                title="拉黑后该用户将被拦截: 无法预约、无法闸机核销入馆" />
      <el-form label-width="80px" style="margin-top:16px">
        <el-form-item label="用户">
          <span class="dlg-user">#{{ target.id }} {{ target.nickname }}</span>
          <span class="dlg-meta">{{ target.id_card_masked || '未实名' }} · {{ target.phone_masked || '无手机号' }}</span>
        </el-form-item>
        <el-form-item label="拉黑原因" required>
          <el-input v-model="reason" type="textarea" :rows="3" maxlength="200" show-word-limit
                    placeholder="例如: 恶意刷票 / 屡次爽约 / 现场违规" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="blackDlg = false">取消</el-button>
        <el-button type="danger" :loading="saving" :disabled="!reason.trim()" @click="doBlack">确认拉黑</el-button>
      </template>
    </el-dialog>

    <!-- 修改原因弹窗 -->
    <el-dialog v-model="reasonDlg" title="修改拉黑原因" width="440px">
      <el-form label-width="80px">
        <el-form-item label="用户">
          <span class="dlg-user">#{{ target.id }} {{ target.nickname }}</span>
        </el-form-item>
        <el-form-item label="拉黑原因" required>
          <el-input v-model="reason" type="textarea" :rows="3" maxlength="200" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reasonDlg = false">取消</el-button>
        <el-button type="primary" :loading="saving" :disabled="!reason.trim()" @click="saveReason">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'

const tab = ref('users')
const keyword = ref('')

// ---- 全部用户 ----
const users = ref([])
const userTotal = ref(0)
const userQuery = reactive({ page: 1, size: 20 })
const usersLoading = ref(false)

// ---- 黑名单列表 ----
const rows = ref([])
const total = ref(0)
const query = reactive({ page: 1, size: 20 })
const loading = ref(false)

// ---- 弹窗 ----
const blackDlg = ref(false)
const reasonDlg = ref(false)
const saving = ref(false)
const target = ref({})
const reason = ref('')

function fmtTime(s) {
  if (!s || s === 'None') return '—'
  return s.replace('T', ' ').slice(0, 19)
}

function rowClass({ row }) {
  return row.is_blacklisted ? 'danger-row' : ''
}

async function loadUsers() {
  usersLoading.value = true
  try {
    const { data } = await http.get('/admin/wx-users', {
      params: { keyword: keyword.value.trim() || undefined, page: userQuery.page, size: userQuery.size },
    })
    users.value = data.items
    userTotal.value = data.total
  } finally {
    usersLoading.value = false
  }
}

async function loadBlacklist() {
  loading.value = true
  try {
    const { data } = await http.get('/admin/blacklist', {
      params: { keyword: keyword.value.trim() || undefined, page: query.page, size: query.size },
    })
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function loadAll() { loadUsers(); loadBlacklist() }

function onSearch() {
  userQuery.page = 1
  query.page = 1
  tab.value === 'users' ? loadUsers() : loadBlacklist()
}

function onTabChange() {
  tab.value === 'users' ? loadUsers() : loadBlacklist()
}

// 拉黑
function openBlackDlg(row) {
  target.value = row
  reason.value = ''
  blackDlg.value = true
}

async function doBlack() {
  saving.value = true
  try {
    const { data } = await http.post('/admin/blacklist/add', {
      user_id: target.value.id, reason: reason.value.trim(),
    })
    blackDlg.value = false
    ElMessage({ type: 'success', message: data?.already ? `已更新拉黑原因: #${target.value.id} ${target.value.nickname}` : `已拉黑 #${target.value.id} ${target.value.nickname}` })
    loadAll()
  } finally {
    saving.value = false
  }
}

// 改原因
function openReasonDlg(row) {
  target.value = row
  reason.value = row.blacklist_reason || ''
  reasonDlg.value = true
}

async function saveReason() {
  saving.value = true
  try {
    await http.post('/admin/blacklist/add', { user_id: target.value.id, reason: reason.value.trim() })
    reasonDlg.value = false
    ElMessage.success('已更新拉黑原因')
    loadAll()
  } finally {
    saving.value = false
  }
}

// 移出
async function unblack(row) {
  await http.post('/admin/blacklist/remove', { user_id: row.id })
  ElMessage.success(`已移出 #${row.id} ${row.nickname || ''}`)
  loadAll()
}

onMounted(loadAll)
</script>

<style scoped>
.stats-row { display: flex; align-items: center; gap: 14px; margin-bottom: 16px; }
.stat-card {
  min-width: 130px; padding: 12px 20px; border-radius: 10px;
  background: var(--el-fill-color-light); border: 1px solid var(--el-border-color-lighter);
}
.stat-danger { background: var(--el-color-danger-light-9); border-color: var(--el-color-danger-light-7); }
.stat-num { font-size: 26px; font-weight: 700; color: var(--el-text-color-primary); }
.stat-danger .stat-num { color: var(--el-color-danger); }
.stat-label { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 2px; }
.spacer { flex: 1; }

.user-cell { display: flex; align-items: center; gap: 8px; }
.user-name { font-weight: 600; }
.reason-cell { display: flex; align-items: center; gap: 8px; min-width: 0; }
.reason-text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--el-color-danger); }
.reason-tag { margin-right: 8px; }
.muted { color: var(--el-text-color-placeholder); }
.table-footer { display: flex; justify-content: flex-end; margin-top: 16px; }
.tab-badge { margin-left: 6px; }
.dlg-alert { --el-alert-title-font-size: 13px; }
.dlg-user { font-weight: 600; margin-right: 10px; }
.dlg-meta { color: var(--el-text-color-secondary); font-size: 12px; }

:deep(.danger-row) { background: var(--el-color-danger-light-9) !important; }
:deep(.danger-row td) { background: transparent !important; }
:deep(.el-table .danger-row:hover > td) { background: var(--el-color-danger-light-8) !important; }
</style>
