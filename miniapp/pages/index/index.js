// 首页 — 科技馆主题首页 (墨绿/宋体)
// 本页为展示型首页: 不含日期/时段选择, 预约流程见 booking 页
const api = require('../../utils/api')
const { syncTabBar } = require('../../utils/tabbar')

// 首页主推内容 (静态, 无「展览」模型; 展品数据来自 /exhibits)
const BANNER = {
  title: '科技点亮未来',
  sub: '探索 · 体验 · 创造 — 科技馆主题季',
  date: '常年开放 · 免费不免票',
}

// 后端不可用时的兜底文案, 保证页面结构与设计稿一致
const FALLBACK_VENUE = {
  name: '菏泽市科技博物馆',
  address: '山东省菏泽市牡丹区人民路1000号',
}

// 展项海报: 本地插画匹配 (与展项列表页共用 utils/poster)
const { posterOf } = require('../../utils/poster')

Page({
  data: {
    statusBarHeight: 20,
    capsuleReserve: 0,
    venueName: FALLBACK_VENUE.name,
    venueAddr: FALLBACK_VENUE.address,
    venueOpen: '',
    venueNotice: '',
    banner: { title: BANNER.title, sub: BANNER.sub, date: BANNER.date, image: '/images/venue.png', imgFailed: false },
    exhibits: [],
    activities: [],
  },

  onLoad() {
    this.setupNavBar()
    this.loadAll()
  },

  // 自定义 tabBar 的选中态需各页自行同步
  onShow() { syncTabBar(this, 0) },

  // 自定义导航: 取状态栏高度, 并预留右上角系统胶囊宽度
  setupNavBar() {
    let statusBarHeight = 20
    let capsuleReserve = 0
    try {
      const win = wx.getWindowInfo ? wx.getWindowInfo() : wx.getSystemInfoSync()
      statusBarHeight = win.statusBarHeight || 20
      if (wx.getMenuButtonBoundingClientRect) {
        const menu = wx.getMenuButtonBoundingClientRect()
        // 胶囊左边界到屏幕右侧的距离 + 间距, 作为头部右侧留白
        if (menu && menu.left) capsuleReserve = win.windowWidth - menu.left + 8
      }
    } catch (err) {
      // 取不到系统信息时沿用默认值, 不影响页面渲染
    }
    this.setData({ statusBarHeight, capsuleReserve })
  },

  loadAll() {
    this.loadVenue()
    this.loadExhibits()
    this.loadActivities()
  },

  loadVenue() {
    api.get('/venue').then(v => {
      this.setData({
        venueName: v.name || FALLBACK_VENUE.name,
        venueAddr: v.address || FALLBACK_VENUE.address,
        venueOpen: v.open_time || '',
        venueNotice: v.notice || '',
      })
    }).catch(() => {
      // 静默降级: 保留兜底文案, 页面结构不变
    })
  },

  loadExhibits() {
    api.get('/exhibits').then(list => {
      // 「热门展项」= 特殊展项(付费可预约体验); 无特殊展项时回落普通展项前3条
      const specials = (list || []).filter(e => e.is_special)
      const picked = (specials.length ? specials : (list || [])).slice(0, 3)
        .map(e => Object.assign({}, e, posterOf(e), {
          priceYuan: e.is_special ? (e.price_cent / 100).toFixed(1).replace(/\.0$/, '') : '',
        }))
      // 主推位用本地场馆插画, 保证无后端数据时也不空置
      this.setData({
        exhibits: picked,
        'banner.image': '/images/venue.png',
      })
    }).catch(() => this.setData({ exhibits: [], 'banner.image': '/images/venue.png' }))
  },

  loadActivities() {
    api.get('/announcements').then(list => {
      const activities = (list || [])
        .filter(a => a.type === 'activity')
        .slice(0, 2)
        .map(a => Object.assign({}, a, { img: '', ph: '🧪', imgFailed: false }))
      this.setData({ activities })
    }).catch(() => this.setData({ activities: [] }))
  },

  // 图片加载失败(如 /static 资源缺失)时回落到占位, 避免裂图
  onExhibitImgError(e) {
    this.setData({ ['exhibits[' + e.currentTarget.dataset.index + '].imgFailed']: true })
  },
  onBannerImgError() {
    this.setData({ 'banner.imgFailed': true })
  },

  onPullDownRefresh() {
    this.loadAll()
    wx.stopPullDownRefresh()
  },

  // 搜索服务未上线: 明确提示而非无响应
  onSearchTap() {
    wx.showToast({ title: '搜索功能即将上线, 敬请期待', icon: 'none' })
  },

  // 预约入口: 跳「预约」tab 选日期, 再由该页转入 booking
  goBooking() {
    wx.switchTab({ url: '/pages/tickets/tickets' })
  },

  // 展项浏览: 「查看更多」/展项卡 → 展项列表页
  goExhibits() {
    wx.navigateTo({ url: '/pages/exhibits/exhibits' })
  },

  // 热门(特殊)展项「体验预约」→ 展项预约页
  goExhibitBooking(e) {
    const { index } = e.currentTarget.dataset
    const ex = this.data.exhibits[index]
    if (!ex) return
    wx.navigateTo({
      url: `/pages/exhibit-booking/exhibit-booking?exhibit_id=${ex.id}&title=${encodeURIComponent(ex.title)}&price_cent=${ex.price_cent}`,
    })
  },

  onQuickTap(e) {
    const key = e.currentTarget.dataset.key
    const tabs = {
      booking: '/pages/tickets/tickets',
      scan: '/pages/scan/scan',
      reservations: '/pages/scan/scan',
      mine: '/pages/mine/mine',
    }
    // 四个入口都是 tabBar 页面, 必须用 switchTab
    wx.switchTab({ url: tabs[key] || '/pages/index/index' })
  },
})
