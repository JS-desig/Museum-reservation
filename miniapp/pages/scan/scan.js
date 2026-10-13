// 扫码 tab — 我的预约 / 扫码凭证
// 数据源: GET /wx/reservations (入馆预约) 或 /wx/exhibit-reservations (特殊展项体验, type=exhibit 进入)
const api = require('../../utils/api')
const { syncTabBar } = require('../../utils/tabbar')
const { buildQrCells } = require('../../utils/qr')

const ENTRY_FILTERS = [
  { key: 'all', text: '全部' },
  { key: 'booked', text: '待使用' },
  { key: 'checked_in', text: '已使用' },
  { key: 'cancelled', text: '已取消' },
]
const EX_FILTERS = [
  { key: 'all', text: '全部' },
  { key: 'booked', text: '待体验' },
  { key: 'used', text: '已体验' },
  { key: 'cancelled', text: '已取消' },
]

const STATUS_TEXT = {
  booked: '待使用',
  checked_in: '已使用',
  cancelled: '已取消',
  no_show: '已爽约',
  used: '已体验',
}

// 一个预约码是 625 个格子, 全部卡片都渲染会拖垮列表,
// 因此只展开当前选中的那一条
function matchFilter(r, key) {
  if (key === 'all') return true
  // 爽约并入「已取消」这一类
  if (key === 'cancelled') return r.status === 'cancelled' || r.status === 'no_show'
  return r.status === key
}

Page({
  data: {
    venueName: '菏泽市科技博物馆',
    venueImg: '/images/venue.png',
    type: 'entry',      // entry=入馆预约 exhibit=展项体验
    filters: ENTRY_FILTERS,
    tab: 'all',
    all: [],
    list: [],
    activeId: null,
    qrCells: [],
    loading: true,
  },

  onLoad(options) {
    if (options && options.type === 'exhibit') {
      this.setData({ type: 'exhibit', filters: EX_FILTERS })
      wx.setNavigationBarTitle({ title: '展项体验预约' })
    }
    api.get('/venue').then(v => {
      if (v && v.name) this.setData({ venueName: v.name })
    }).catch(() => { /* 静默: 保留兜底名称 */ })
  },

  onShow() {
    syncTabBar(this, 2)
    this.load()
  },

  onPullDownRefresh() {
    this.load(() => wx.stopPullDownRefresh())
  },

  load(done) {
    const fetch = this.data.type === 'exhibit'
      ? api.get('/wx/exhibit-reservations')
      : api.get('/wx/reservations')
    fetch.then(all => {
      const rows = (all || []).map(r => Object.assign({}, r, {
        statusText: STATUS_TEXT[r.status] || '已过期',
        // 展项预约卡片副标题: 展项名 + 人数 + 金额
        headType: this.data.type === 'exhibit'
          ? `${r.exhibit_title} · ${r.person_count}人 · ¥${(r.amount_cent / 100).toFixed(1).replace(/\.0$/, '')}`
          : `预约 ${r.visitor_count} 人 · ${r.session_name || ''}`,
        voucherUrl: `/pages/result/result?code=${r.resv_code}${this.data.type === 'exhibit' ? '&type=exhibit' : ''}`,
      }))
      this.setData({ all: rows, loading: false })
      this.applyFilter()
    }).catch(() => {
      this.setData({ all: [], list: [], loading: false })
    }).finally(() => { if (done) done() })
  },

  applyFilter() {
    const list = this.data.all.filter(r => matchFilter(r, this.data.tab))
    // 保持展开项有效: 不在新列表里就落到第一条
    const keep = list.some(r => r.id === this.data.activeId)
    const activeId = keep ? this.data.activeId : (list[0] ? list[0].id : null)
    this.setData({ list, activeId })
    this.rebuildQr()
  },

  rebuildQr() {
    const cur = this.data.list.find(r => r.id === this.data.activeId)
    // 包一层带序号的对象: 格子值只有 0/1/2, 直接拿值当 wx:key 会重复
    this.setData({
      qrCells: cur ? buildQrCells(cur.resv_code).map((v, i) => ({ i, v })) : [],
    })
  },

  switchTab(e) {
    this.setData({ tab: e.currentTarget.dataset.key })
    this.applyFilter()
  },

  // 点卡片切换展开的凭证
  toggle(e) {
    const id = e.currentTarget.dataset.id
    this.setData({ activeId: this.data.activeId === id ? null : id })
    this.rebuildQr()
  },

  cancel(e) {
    const id = e.currentTarget.dataset.id
    const isExhibit = this.data.type === 'exhibit'
    wx.showModal({
      title: '取消预约',
      content: isExhibit ? '确认取消该展项体验? 已支付费用将原路退回' : '确认取消该预约? 取消后名额将释放',
      success: res => {
        if (!res.confirm) return
        const req = isExhibit
          ? api.del(`/wx/exhibit-reservations/${id}`)
          : api.del(`/wx/reservations/${id}`)
        req.then(() => { wx.showToast({ title: '已取消' }); this.load() })
          .catch(err => wx.showToast({ title: (err && err.message) || '取消失败', icon: 'none' }))
      },
    })
  },

  // 卡片跳详情凭证页
  goDetail(e) {
    const code = e.currentTarget.dataset.code
    wx.navigateTo({ url: `/pages/result/result?code=${code}${this.data.type === 'exhibit' ? '&type=exhibit' : ''}` })
  },

  // 空态引导: 跳预约 tab (入馆) 或展项列表 (展项)
  goBooking() {
    if (this.data.type === 'exhibit')
      return wx.navigateTo({ url: '/pages/exhibits/exhibits' })
    wx.switchTab({ url: '/pages/tickets/tickets' })
  },

  onShareAppMessage() {
    const cur = this.data.list.find(r => r.id === this.data.activeId)
    return {
      title: cur ? `我的${this.data.type === 'exhibit' ? '展项体验' : '入馆'}凭证 ${cur.resv_code}` : '菏泽市科技博物馆',
      path: '/pages/index/index',
    }
  },
})
