// 预约 tab — 免费预约制
// 注意: 设计稿的票种与票价(¥30/¥15)按用户要求原样保留, 但后端没有任何价格模型,
// 因此票价仅为展示, 不参与下单; 预约本身仍是免费的(见需求文档「免费不免票」)
const api = require('../../utils/api')
const { syncTabBar } = require('../../utils/tabbar')

// 场馆免费开放(需求「免费不免票」), 票种实为「人群/预约通道」分类, 不涉及价格
const TICKETS = [
  { id: 'adult', name: '个人预约', desc: '18-64岁, 每单最多5人(含主预约人)', tag: '免费' },
  { id: 'family', name: '亲子预约', desc: '儿童科学乐园专用通道, 3-12岁儿童须成人陪同', tag: '免费' },
  { id: 'discount', name: '团体预约', desc: '10人以上团体/研学团队, 建议提前3天预约', tag: '免费' },
]

const WEEK = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
const pad = n => String(n).padStart(2, '0')
const ymd = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`

Page({
  data: {
    venueName: '菏泽市科技博物馆',
    venueSlogan: '探索 · 体验 · 创造',
    venueOpen: '',
    venueClosed: false,
    venueImg: '/images/venue.png',
    dates: [],
    tickets: TICKETS,
    dateIndex: 0,
    ticketIndex: 0,
  },

  onLoad() {
    this.setData({ dates: this.buildDates() })
    this.loadVenue()
  },

  // 自定义 tabBar 的选中态需各页自行同步
  onShow() { syncTabBar(this, 1) },

  // 今天起 7 天(含今日, 需求 FR-C.6), 首日标注「今天」; 周一闭馆置灰不可选
  buildDates() {
    const out = []
    for (let i = 0; i < 7; i++) {
      const d = new Date(Date.now() + i * 86400000)
      out.push({
        value: ymd(d),
        md: `${pad(d.getMonth() + 1)}-${pad(d.getDate())}`,
        week: WEEK[d.getDay()],
        today: i === 0,
        // 周一闭馆(法定节假日除外, 这里按常规周一处理)
        closed: d.getDay() === 1,
      })
    }
    // 默认选中第一个开放日
    const firstOpen = out.findIndex(d => !d.closed)
    this.setData({ dateIndex: firstOpen >= 0 ? firstOpen : 0 })
    return out
  },

  loadVenue() {
    api.get('/venue').then(v => {
      if (v && v.name) {
        this.setData({
          venueName: v.name,
          venueOpen: v.open_time || '',
          venueClosed: v.status === 0,
        })
      }
    }).catch(() => { /* 静默: 保留兜底名称 */ })
  },

  selectDate(e) {
    const i = e.currentTarget.dataset.index
    if (this.data.dates[i].closed)
      return wx.showToast({ title: '周一闭馆, 请选择其他日期', icon: 'none' })
    this.setData({ dateIndex: i })
  },

  selectTicket(e) {
    this.setData({ ticketIndex: e.currentTarget.dataset.index })
  },

  // 设计稿此处只有「下一步」。booking 页需要 session_id, 而本页没有时段选择,
  // 所以这里补一个原生 ActionSheet 选时段 —— 不改变设计稿布局, 但把预约链路接通。
  next() {
    if (this.data.venueClosed)
      return wx.showToast({ title: '场馆今日闭馆, 暂停预约', icon: 'none' })
    const date = this.data.dates[this.data.dateIndex].value
    wx.showLoading({ title: '加载时段…', mask: true })
    api.get('/wx/slots', { visit_date: date }).then(data => {
      wx.hideLoading()
      const slots = (data.slots || []).filter(s => s.remaining > 0)
      if (!slots.length) return wx.showToast({ title: '该日期暂无可约时段', icon: 'none' })
      wx.showActionSheet({
        itemList: slots.map(s => `${s.start_time}-${s.end_time} ${s.name} (余 ${s.remaining})`),
        success: res => {
          const s = slots[res.tapIndex]
          wx.navigateTo({
            url: `/pages/booking/booking?date=${date}&session_id=${s.id}&session_name=${encodeURIComponent(s.name)}`,
          })
        },
      })
    }).catch(err => {
      wx.hideLoading()
      wx.showToast({ title: (err && err.message) || '时段加载失败', icon: 'none' })
    })
  },
})
