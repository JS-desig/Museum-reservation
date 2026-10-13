<template>
  <div>
    <!-- 实时客流统计卡 -->
    <el-row :gutter="16">
      <el-col :xs="12" :sm="12" :md="6" v-for="card in topCards" :key="card.label">
        <div class="stat-card" :style="{ '--accent': card.color }">
          <div class="stat-icon">{{ card.icon }}</div>
          <div class="stat-body">
            <div class="stat-label">{{ card.label }}</div>
            <div class="stat-value" :style="{ color: card.color }">{{ card.value }}</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 预警条 -->
    <transition name="fade">
      <el-alert v-if="data.realtime?.warning" type="warning" show-icon :closable="false"
                class="warn-bar"
                :title="`客流接近峰值: 在馆 ${data.realtime.in_venue} / 最大承载 ${data.realtime.daily_max}`" />
    </transition>

    <!-- 图表区 -->
    <el-row :gutter="16" style="margin-top:16px">
      <el-col :xs="24" :md="16">
        <el-card>
          <template #header>
            <div class="card-head"><span class="card-head-bar"></span>近7日预约 / 核销趋势</div>
          </template>
          <div ref="trendRef" style="height:340px"></div>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="8">
        <el-card>
          <template #header>
            <div class="card-head"><span class="card-head-bar"></span>承载量水位</div>
          </template>
          <div ref="gaugeRef" style="height:340px"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 周期汇总 + 时段分布 -->
    <el-row :gutter="16" style="margin-top:16px">
      <el-col :xs="24" :md="8" v-for="period in ['week', 'month']" :key="period">
        <el-card>
          <template #header>
            <div class="card-head">
              <span class="card-head-bar"></span>{{ period === 'week' ? '本周' : '本月' }}汇总
            </div>
          </template>
          <div class="period-grid">
            <div class="period-item">
              <div class="period-num">{{ data[period]?.total ?? '-' }}</div>
              <div class="period-label">预约总数</div>
            </div>
            <div class="period-item">
              <div class="period-num" style="color:var(--hz-success)">{{ data[period]?.checked ?? '-' }}</div>
              <div class="period-label">核销人数</div>
            </div>
            <div class="period-item">
              <div class="period-num" style="color:var(--hz-primary-light)">{{ pct(data[period]?.rate) }}</div>
              <div class="period-label">核销率</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="8">
        <el-card>
          <template #header>
            <div class="card-head"><span class="card-head-bar"></span>今日时段分布</div>
          </template>
          <div ref="slotRef" style="height:200px"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 数据导出 -->
    <el-card style="margin-top:16px">
      <template #header>
        <div class="card-head"><span class="card-head-bar"></span>数据导出与运营操作</div>
      </template>
      <div class="export-row">
        <el-date-picker v-model="exportDate" type="date" value-format="YYYY-MM-DD"
                        placeholder="选择日期(可空=全部)" style="width:200px" clearable />
        <el-button type="primary" plain @click="doExport('reservations')">导出预约明细</el-button>
        <el-button type="primary" plain @click="doExport('access')">导出通行日志</el-button>
        <span class="spacer"></span>
        <el-button type="warning" @click="markNoshow">标记昨日爽约</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage, ElNotification } from 'element-plus'
import * as echarts from 'echarts'
import http from '../api/http'

const data = ref({})
const trendRef = ref()
const slotRef = ref()
const gaugeRef = ref()
const exportDate = ref('')
let trendChart, slotChart, gaugeChart, timer
let lastWarning = false

const topCards = computed(() => {
  const r = data.value.realtime || {}
  const t = data.value.today || {}
  return [
    { label: '实时在馆人数', value: r.in_venue ?? '-', color: r.warning ? '#e6a23c' : '#2b5aa0', icon: '👥' },
    { label: '今日预约人数', value: t.visitor_count ?? '-', color: '#2c3345', icon: '🎫' },
    { label: '今日核销人数', value: t.checked_count ?? '-', color: '#22a05a', icon: '✅' },
    { label: '今日爽约数', value: t.no_show ?? '-', color: '#e05252', icon: '⏰' },
  ]
})

function pct(v) { return v == null ? '-' : (v * 100).toFixed(1) + '%' }

function renderTrend() {
  const rows = data.value.trend_7d || []
  trendChart.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['预约人数', '核销人数'], top: 0, right: 0 },
    grid: { left: 8, right: 8, top: 36, bottom: 0, containLabel: true },
    xAxis: { type: 'category', data: rows.map(r => r.date.slice(5)), axisTick: { show: false } },
    yAxis: { type: 'value', splitLine: { lineStyle: { type: 'dashed', color: '#e6eaf0' } } },
    series: [
      { name: '预约人数', type: 'bar', barWidth: 14, itemStyle: { borderRadius: [4, 4, 0, 0], color: '#4f8be0' },
        data: rows.map(r => r.booked) },
      { name: '核销人数', type: 'bar', barWidth: 14, itemStyle: { borderRadius: [4, 4, 0, 0], color: '#43c17a' },
        data: rows.map(r => r.checked) },
    ],
  })
}

function renderSlot() {
  const rows = data.value.slot_distribution || []
  const palette = ['#4f8be0', '#43c17a', '#f0a542', '#9b8cf0', '#f07a7a']
  slotChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}<br/>占比 {d}%' },
    legend: { bottom: 0, icon: 'circle', itemHeight: 10, textStyle: { fontSize: 11 } },
    series: [{
      type: 'pie', radius: ['38%', '58%'], center: ['50%', '46%'],
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { formatter: '{b} {c}人', fontSize: 11 },
      data: rows.map((r, i) => ({ name: r.session, value: r.count, itemStyle: { color: palette[i % palette.length] } })),
    }],
  })
}

function renderGauge() {
  const r = data.value.realtime || {}
  const usage = Math.min(100, Math.round((r.usage_ratio || 0) * 100))
  gaugeChart.setOption({
    series: [{
      type: 'gauge', startAngle: 210, endAngle: -30, min: 0, max: 100,
      progress: { show: true, width: 16, roundCap: true },
      axisLine: { lineStyle: { width: 16, roundCap: true, color: [[1, '#eef1f6']] } },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      pointer: { show: false },
      detail: {
        valueAnimation: true, offsetCenter: [0, '-5%'],
        formatter: '{value}%', fontSize: 34, fontWeight: 700,
        color: usage >= 90 ? '#e05252' : usage >= 70 ? '#e6a23c' : '#22a05a',
      },
      title: { offsetCenter: [0, '28%'], fontSize: 13, color: '#6b7280' },
      data: [{
        value: usage,
        name: `在馆 ${r.in_venue ?? '-'} / 承载 ${r.daily_max ?? '-'}`,
      }],
    }],
  })
}

async function load() {
  const { data: d } = await http.get('/admin/stats/dashboard')
  data.value = d
  renderTrend()
  renderSlot()
  renderGauge()
  // 峰值预警弹窗: 状态从安全->预警时触发一次(需求3.4峰值预警弹窗变色)
  const warning = d.realtime?.warning
  if (warning && !lastWarning) {
    ElNotification({
      title: '客流峰值预警',
      message: `在馆人数 ${d.realtime.in_venue} 已达最大承载 ${d.realtime.daily_max} 的 ${((d.realtime.warn_ratio || 0.9) * 100).toFixed(0)}%, 请关注现场秩序`,
      type: 'warning', duration: 10000,
    })
  }
  lastWarning = !!warning
}

function doExport(kind) {
  const token = localStorage.getItem('token')
  const q = exportDate.value ? `?date_str=${exportDate.value}` : ''
  // 触发浏览器下载(CSV带BOM)
  fetch(`/api/admin/stats/export/${kind}${q}`, { headers: { Authorization: `Bearer ${token}` } })
    .then(r => { if (!r.ok) throw new Error('导出失败'); return r.blob() })
    .then(blob => {
      const url = URL.createObjectURL(blob)
      const el = document.createElement('a')
      el.href = url
      el.download = `${kind}_${exportDate.value || 'all'}.csv`
      el.click()
      URL.revokeObjectURL(url)
      ElMessage.success('导出成功')
    })
    .catch(e => ElMessage.error(e.message))
}

async function markNoshow() {
  const { data } = await http.post('/admin/stats/mark-noshow', {})
  ElMessage.success(`已标记爽约 ${data.marked} 单(${data.date})`)
  load()
}

onMounted(() => {
  trendChart = echarts.init(trendRef.value)
  slotChart = echarts.init(slotRef.value)
  gaugeChart = echarts.init(gaugeRef.value)
  load()
  timer = setInterval(load, 15000)  // 15秒自动刷新
})
onUnmounted(() => { clearInterval(timer); trendChart?.dispose(); slotChart?.dispose(); gaugeChart?.dispose() })
</script>

<style scoped>
.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  background: #fff;
  border-radius: var(--hz-card-radius);
  padding: 20px 22px;
  box-shadow: var(--hz-shadow);
  border-top: 3px solid var(--accent);
  transition: transform 0.2s, box-shadow 0.2s;
}
.stat-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 20px rgba(29, 63, 114, 0.14);
}
.stat-icon {
  width: 52px; height: 52px;
  display: flex; align-items: center; justify-content: center;
  font-size: 26px;
  background: color-mix(in srgb, var(--accent) 12%, #fff);
  border-radius: 14px;
}
.stat-label { color: var(--hz-text-secondary); font-size: 13px; }
.stat-value { font-size: 30px; font-weight: 700; margin-top: 4px; line-height: 1.1; }

.warn-bar { margin-top: 16px; border-radius: 10px; }

.card-head { display: flex; align-items: center; gap: 8px; }
.card-head-bar {
  width: 4px; height: 16px;
  border-radius: 2px;
  background: var(--hz-primary);
}

.period-grid { display: flex; text-align: center; padding: 22px 0; }
.period-item { flex: 1; }
.period-item + .period-item { border-left: 1px dashed var(--hz-border); }
.period-num { font-size: 34px; font-weight: 700; }
.period-label { color: var(--hz-text-secondary); font-size: 13px; margin-top: 6px; }

.export-row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.export-row .spacer { flex: 1; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.4s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
