<template>
  <div class="gate-page">
    <div class="gate-header">
      <span>闸机核销终端 · {{ gateId }}</span>
      <div>
        <el-switch v-model="offlineMode" active-text="离线模式" inactive-text="在线"
                   style="margin-right:16px" @change="toggleOffline" />
        <el-button size="small" @click="showSyncDlg = true">离线队列 ({{ queue.length }})</el-button>
        <el-button size="small" @click="backAdmin" v-if="isAdmin">返回后台</el-button>
      </div>
    </div>

    <div class="gate-body">
      <!-- 模拟闸机屏幕 -->
      <div class="gate-screen" :class="state.cls">
        <div class="gate-icon">{{ state.icon }}</div>
        <div class="gate-title">{{ state.title }}</div>
        <div class="gate-msg">{{ state.msg }}</div>
      </div>

      <div class="gate-inputs">
        <el-tabs v-model="tab">
          <el-tab-pane label="扫码核销" name="qrcode">
            <el-input v-model="qrCode" placeholder="输入/扫描12位预约码" size="large" clearable
                      @keyup.enter="check('qrcode', qrCode)">
              <template #append><el-button type="primary" @click="check('qrcode', qrCode)">核销</el-button></template>
            </el-input>
            <el-button style="margin-top:12px;width:100%" @click="genQr">生成演示二维码</el-button>
            <canvas ref="qrCanvas" style="margin-top:12px"></canvas>
          </el-tab-pane>
          <el-tab-pane label="身份证核销" name="idcard">
            <el-input v-model="idCard" placeholder="输入/读取18位身份证号" size="large" clearable
                      @keyup.enter="check('idcard', idCard)">
              <template #append><el-button type="primary" @click="check('idcard', idCard)">核销</el-button></template>
            </el-input>
          </el-tab-pane>
        </el-tabs>

        <el-divider>通行方向</el-divider>
        <el-radio-group v-model="direction" size="large">
          <el-radio-button value="in">入馆</el-radio-button>
          <el-radio-button value="out">出馆</el-radio-button>
        </el-radio-group>

        <el-divider>最近的核销流水</el-divider>
        <div class="log-list">
          <div v-for="log in logs" :key="log.seq" class="log-item" :class="log.result">
            <span>{{ log.time }}</span>
            <span>{{ log.type === 'qrcode' ? '扫码' : '身份证' }}</span>
            <span>{{ log.credential }}</span>
            <span>{{ log.result === 'success' ? '✓ 开闸' : '✗ ' + log.reason }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 离线补传对话框 -->
    <el-dialog v-model="showSyncDlg" title="离线队列补传" width="560px">
      <el-alert v-if="queue.length === 0" title="队列为空" type="info" :closable="false" />
      <el-table v-else :data="queue" size="small">
        <el-table-column prop="device_seq" label="序号" />
        <el-table-column prop="check_type" label="方式" width="80" />
        <el-table-column prop="credential" label="凭证" />
        <el-table-column prop="direction" label="方向" width="70" />
        <el-table-column prop="pass_time" label="过闸时间" width="160" />
      </el-table>
      <template #footer>
        <el-button @click="showSyncDlg = false">关闭</el-button>
        <el-button type="primary" :disabled="queue.length === 0" @click="syncBatch">
          补传至服务器
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import QRCode from 'qrcode'
import axios from 'axios'

const gateId = 'GATE-' + String(Math.floor(Math.random() * 90) + 10)
const tab = ref('qrcode')
const qrCode = ref('')
const idCard = ref('')
const direction = ref('in')
const offlineMode = ref(false)
const queue = ref([])
const logs = ref([])
const qrCanvas = ref()
const showSyncDlg = ref(false)
const seqCounter = ref(Date.now())
const router = useRouter()
const isAdmin = !!localStorage.getItem('token')

const state = reactive({ cls: 'idle', icon: '⏳', title: '待核销', msg: '请扫码或刷身份证' })

const failMsgMap = {
  60001: '无效预约码', 60002: '重复核销', 60003: '未预约', 60004: '错峰: 非预约时段',
  60005: '黑名单用户', 60006: '预约已取消', 60007: '预约已过期',
}

function setState(cls, icon, title, msg) {
  Object.assign(state, { cls, icon, title, msg })
  // 5秒后恢复待机
  clearTimeout(setState._t)
  setState._t = setTimeout(() => setState('idle', '⏳', '待核销', '请扫码或刷身份证'), 5000)
}

function pushLog(type, credential, result, reason) {
  logs.value.unshift({
    seq: seqCounter.value++,
    time: new Date().toLocaleTimeString(),
    type, credential: credential.slice(0, 18),
    result, reason: reason || '',
  })
  if (logs.value.length > 20) logs.value.pop()
}

async function check(type, credential) {
  if (!credential) return ElMessage.warning('请输入凭证')
  const seq = `${gateId}-${Date.now()}-${Math.floor(Math.random() * 1000)}`
  const item = {
    check_type: type, credential, direction: direction.value,
    gate_id: gateId, device_seq: seq,
  }

  if (offlineMode.value) {
    queue.value.push({ ...item, pass_time: new Date().toISOString() })
    setState('warn', '📴', '离线暂存', `指令${seq.slice(-6)}已本地缓存, 联网后补传`)
    pushLog(type, credential, 'offline', '离线暂存')
    qrCode.value = ''
    idCard.value = ''
    return
  }

  try {
    const { data } = await axios.post('/api/gate/check', item)
    const d = data.data
    if (d.result === 'success') {
      setState('ok', d.duplicate ? '✓' : '🚪', d.duplicate ? '重复指令' : '核销成功 开闸放行',
        `预约${d.reservation_id} · ${d.visitor || ''} · ${d.direction === 'in' ? '入馆' : '出馆'}`)
      pushLog(type, credential, 'success')
    } else {
      setState('err', '⛔', '核销失败 拒绝通行', failMsgMap[d.fail_reason] || d.fail_reason)
      pushLog(type, credential, 'fail', failMsgMap[d.fail_reason] || d.fail_reason)
    }
  } catch (e) {
    // 网络异常 => 自动降级离线
    queue.value.push({ ...item, pass_time: new Date().toISOString() })
    setState('warn', '📴', '网络异常 已离线暂存', '联网后请在离线队列中补传')
    pushLog(type, credential, 'offline', '网络异常')
  }
  qrCode.value = ''
  idCard.value = ''
}

async function genQr() {
  // 演示: 输入框内容生成二维码
  if (!qrCode.value) return ElMessage.warning('请先在输入框输入预约码')
  await QRCode.toCanvas(qrCanvas.value, qrCode.value, { width: 160 })
}

async function syncBatch() {
  if (!queue.value.length) return
  const items = queue.value.map(q => ({ ...q }))
  try {
    const { data } = await axios.post('/api/gate/sync/batch', { gate_id: gateId, items })
    const results = data.data.results
    const okCount = results.filter(r => r.result === 'success').length
    setState('ok', '🔄', '补传完成', `共${items.length}条, 成功${okCount}条`)
    queue.value = []
    showSyncDlg.value = false
  } catch (e) {
    ElMessage.error('补传失败, 请检查网络')
  }
}

function toggleOffline(v) {
  if (!v && queue.value.length) {
    ElMessage.info(`离线队列有${queue.value.length}条待补传`)
  }
}

function backAdmin() { router.push('/') }

onMounted(() => { setState('idle', '⏳', '待核销', '请扫码或刷身份证') })
</script>

<style scoped>
.gate-page { height: 100vh; display: flex; flex-direction: column; background: #0f1b2d; }
.gate-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 24px; background: #16263e; color: #fff; font-size: 16px; font-weight: 600;
}
.gate-body { flex: 1; display: flex; gap: 24px; padding: 24px; overflow: auto; }
.gate-screen {
  width: 380px; border-radius: 16px; display: flex; flex-direction: column;
  align-items: center; justify-content: center; color: #fff; flex-shrink: 0;
  transition: all .3s;
}
.gate-screen.idle { background: linear-gradient(160deg, #2b4a75, #1d3f72); }
.gate-screen.ok { background: linear-gradient(160deg, #1e7e46, #14532d); box-shadow: 0 0 40px #22c55e; }
.gate-screen.err { background: linear-gradient(160deg, #b91c1c, #7f1d1d); box-shadow: 0 0 40px #ef4444; }
.gate-screen.warn { background: linear-gradient(160deg, #b45309, #78350f); box-shadow: 0 0 40px #f59e0b; }
.gate-icon { font-size: 72px; }
.gate-title { font-size: 26px; font-weight: 700; margin-top: 16px; text-align: center; padding: 0 16px; }
.gate-msg { font-size: 15px; margin-top: 12px; opacity: .9; text-align: center; padding: 0 16px; }
.gate-inputs { flex: 1; background: #fff; border-radius: 12px; padding: 20px; max-width: 640px; }
.log-list { max-height: 260px; overflow: auto; }
.log-item {
  display: flex; gap: 10px; padding: 6px 10px; font-size: 13px; border-radius: 6px; margin-bottom: 4px;
  background: #f4f6f9; font-family: monospace;
}
.log-item.success { background: #f0f9eb; color: #1e7e46; }
.log-item.fail { background: #fef0f0; color: #c45656; }
.log-item.offline { background: #fdf6ec; color: #b45309; }
</style>
