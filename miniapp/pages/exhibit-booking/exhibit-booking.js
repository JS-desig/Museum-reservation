// 特殊展项预约页 — 付费体验: 选日期时段+人数 → 模拟支付
// 前置: 须已有同日同时段入馆预约(服务端强校验)
const api = require('../../utils/api')

function genNonce() {
  return 'ex' + Date.now().toString(36) + Math.random().toString(36).slice(2, 10)
}

const WEEK = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
const pad = n => String(n).padStart(2, '0')
const ymd = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`

Page({
  data: {
    exhibitId: 0,
    title: '',
    priceCent: 0,
    priceYuan: '0',
    dates: [],          // [{value, md, week, today}]
    dateIndex: 0,
    sessions: [],       // [{session_id, name, time, remaining, disabled}]
    sessionIndex: -1,
    personCount: 1,
    maxPerson: 5,
    totalYuan: '0',
    submitting: false,
    entryChecked: false,  // 当日同时段是否有入馆预约
  },

  onLoad(options) {
    const priceCent = Number(options.price_cent) || 0
    this.setData({
      exhibitId: Number(options.exhibit_id) || 0,
      title: decodeURIComponent(options.title || ''),
      priceCent,
      priceYuan: (priceCent / 100).toFixed(1).replace(/\.0$/, ''),
      dates: this.buildDates(),
    })
    this.loadSessions()
  },

  onShow() { this.checkEntry() },

  // 今天起 7 天
  buildDates() {
    const out = []
    for (let i = 0; i < 7; i++) {
      const d = new Date(Date.now() + i * 86400000)
      out.push({
        value: ymd(d),
        md: `${pad(d.getMonth() + 1)}-${pad(d.getDate())}`,
        week: WEEK[d.getDay()],
        today: i === 0,
      })
    }
    return out
  },

  // 前置条件自检: 当日同时段是否有入馆预约
  checkEntry() {
    const { dates, dateIndex, exhibitId } = this.data
    if (!exhibitId || !dates.length) return
    api.get('/wx/reservations').then(list => {
      const date = dates[dateIndex].value
      const session = this.data.sessions[this.data.sessionIndex]
      const ok = (list || []).some(r =>
        r.visit_date === date && r.status !== 'cancelled'
        && (!session || r.session_id === session.session_id))
      this.setData({ entryChecked: ok })
    }).catch(() => this.setData({ entryChecked: false }))
  },

  loadSessions() {
    const { dates, dateIndex, exhibitId } = this.data
    const date = dates[dateIndex].value
    api.get('/wx/exhibit-reservations/special', { visit_date: date })
      .then(list => {
        const ex = (list || []).find(x => x.id === exhibitId)
        if (!ex) {
          this.setData({ sessions: [], sessionIndex: -1 })
          return wx.showToast({ title: '展项不存在或已下架', icon: 'none' })
        }
        // 用场馆时段名补充展示 (special 接口只回 session_id)
        api.get('/wx/slots', { visit_date: date }).then(slotData => {
          const slots = slotData.slots || []
          const sessions = (ex.sessions || [])
            // 非特殊日期夜场不可约: /wx/slots 已过滤, 这里同步剔除(匹配不到时段名的一并隐藏)
            .filter(s => slots.some(x => x.id === s.session_id))
            .map(s => {
            const slot = slots.find(x => x.id === s.session_id) || {}
            return {
              session_id: s.session_id,
              name: slot.name || `时段${s.session_id}`,
              time: slot.start_time ? `${slot.start_time}-${slot.end_time}` : '',
              remaining: s.remaining,
              disabled: s.remaining <= 0,
            }
          })
          const firstOpen = sessions.findIndex(s => !s.disabled)
          this.setData({ sessions, sessionIndex: firstOpen >= 0 ? firstOpen : -1 })
          this.updateTotal()
        })
      }).catch(err => wx.showToast({ title: (err && err.message) || '加载失败', icon: 'none' }))
  },

  selectDate(e) {
    this.setData({ dateIndex: e.currentTarget.dataset.index, sessionIndex: -1, sessions: [] })
    this.loadSessions()
    this.checkEntry()
  },

  selectSession(e) {
    const i = e.currentTarget.dataset.index
    if (this.data.sessions[i].disabled)
      return wx.showToast({ title: '该时段体验名额已满', icon: 'none' })
    this.setData({ sessionIndex: i })
    this.updateTotal()
    this.checkEntry()
  },

  onPersonChange(e) {
    const delta = Number(e.currentTarget.dataset.delta)
    const next = this.data.personCount + delta
    if (next < 1 || next > this.data.maxPerson) return
    this.setData({ personCount: next })
    this.updateTotal()
  },

  updateTotal() {
    const total = this.data.priceCent * this.data.personCount
    this.setData({ totalYuan: (total / 100).toFixed(1).replace(/\.0$/, '') })
  },

  submit() {
    const { exhibitId, dates, dateIndex, sessions, sessionIndex, personCount, submitting, title } = this.data
    if (submitting) return
    if (sessionIndex < 0)
      return wx.showToast({ title: '请选择体验时段', icon: 'none' })
    const date = dates[dateIndex].value
    const session = sessions[sessionIndex]
    wx.showModal({
      title: '确认预约',
      content: `${title}\n${date} ${session.time}\n${personCount}人 · 合计 ¥${this.data.totalYuan}\n\n需先持有当日入馆预约`,
      success: res => {
        if (!res.confirm) return
        this.setData({ submitting: true })
        api.post('/wx/exhibit-reservations', {
          exhibit_id: exhibitId, visit_date: date,
          session_id: session.session_id, person_count: personCount,
          nonce: genNonce(),
        }).then(data => {
          // 模拟支付闭环
          return api.post(`/wx/exhibit-reservations/${data.id}/pay`).then(() => data)
        }).then(data => {
          wx.showToast({ title: '预约成功', icon: 'success' })
          setTimeout(() => wx.redirectTo({ url: `/pages/result/result?code=${data.resv_code}&type=exhibit` }), 900)
        }).catch(err => {
          wx.showToast({ title: (err && err.message) || '预约失败', icon: 'none' })
          // 入馆预约缺失等前置失败: 刷新状态提示
          if (err && err.message && err.message.indexOf('入馆') >= 0) this.checkEntry()
        }).finally(() => this.setData({ submitting: false }))
      },
    })
  },
})
