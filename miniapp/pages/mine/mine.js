// 我的 tab — 个人中心: 实名状态/黑名单/数据概览/功能菜单
// 说明: 预约凭证在「扫码」tab, 通行记录/实名信息为子页
const api = require('../../utils/api')
const { syncTabBar } = require('../../utils/tabbar')

const MENUS = [
  { key: 'realname', text: '实名信息', icon: 'contacts' },
  { key: 'exresv', text: '展项体验预约', icon: 'ticket' },
  { key: 'pass', text: '通行记录', icon: 'clipboard' },
  { key: 'notice', text: '入馆须知', icon: 'notice' },
  // 在线客服由开放能力按钮处理 (open-type=contact), 不走 onMenuTap
  { key: 'service', text: '在线客服', icon: 'headset', service: true },
  { key: 'about', text: '关于场馆', icon: 'gear' },
]

Page({
  data: {
    nickname: '游客',
    userId: '',
    profile: {},
    stats: { resv: 0, checked: 0, noshow: 0, pass: 0, exResv: 0, exPaid: 0, exUsed: 0 },
    menus: MENUS,
  },

  onShow() {
    syncTabBar(this, 3)
    this.loadProfile()
    this.loadStats()
  },

  loadProfile() {
    api.get('/wx/profile').then(p => {
      this.setData({
        nickname: p.nickname || '游客',
        userId: p.user_id ? String(p.user_id) : '',
        profile: p,
      })
    }).catch(() => {
      // 未登录或接口不可用时保留默认游客态
    })
  },

  loadStats() {
    api.get('/wx/reservations').then(list => {
      const all = list || []
      this.setData({
        'stats.resv': all.length,
        'stats.checked': all.filter(r => r.status === 'checked_in').length,
        'stats.noshow': all.filter(r => r.status === 'no_show').length,
      })
    }).catch(() => { /* 静默: 概览保持0 */ })
    api.get('/wx/pass-records').then(list => {
      this.setData({ 'stats.pass': (list || []).length })
    }).catch(() => { /* 静默 */ })
    // 展项体验预约概览 (独立于入馆预约)
    api.get('/wx/exhibit-reservations').then(list => {
      const all = list || []
      this.setData({
        'stats.exResv': all.filter(r => r.status !== 'cancelled').length,
        'stats.exPaid': all.filter(r => r.pay_status === 'paid' && r.status === 'booked').length,
        'stats.exUsed': all.filter(r => r.status === 'used').length,
      })
    }).catch(() => { /* 静默 */ })
  },

  onMenuTap(e) {
    const key = e.currentTarget.dataset.key
    if (key === 'realname') return wx.navigateTo({ url: '/pages/realname/realname' })
    if (key === 'exresv') return wx.navigateTo({ url: '/pages/scan/scan?type=exhibit' })
    if (key === 'pass') return wx.navigateTo({ url: '/pages/records/records' })
    if (key === 'notice') return this.showNotice()
    if (key === 'about') return this.showAbout()
  },

  goRealname() { wx.navigateTo({ url: '/pages/realname/realname' }) },
  goReservations() { wx.switchTab({ url: '/pages/scan/scan' }) },
  goExReservations() { wx.navigateTo({ url: '/pages/scan/scan?type=exhibit' }) },
  goPassRecords() { wx.navigateTo({ url: '/pages/records/records' }) },

  // 入馆须知直接用场馆配置里的 notice, 不另建页面
  showNotice() {
    api.get('/venue').then(v => {
      wx.showModal({
        title: '入馆须知',
        content: (v && v.notice) || '暂无入馆须知',
        showCancel: false,
        confirmText: '知道了',
      })
    }).catch(() => wx.showToast({ title: '加载失败', icon: 'none' }))
  },

  showAbout() {
    api.get('/venue').then(v => {
      wx.showModal({
        title: v.name || '菏泽市科技博物馆',
        content: `${v.address || ''}\n${v.open_time || ''}\n${v.traffic_guide || ''}`,
        showCancel: false,
        confirmText: '知道了',
      })
    }).catch(() => wx.showToast({ title: '加载失败', icon: 'none' }))
  },
})