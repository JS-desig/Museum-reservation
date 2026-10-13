// 登录页: 完成登录后进入首页
const api = require('../../utils/api')

Page({
  data: { logging: false },

  onLoad() {
    this.ensureLogin()
  },

  onShow() {
    // 从首页强制跳转过来时若已有登录态则直接回首页
    if (wx.getStorageSync('openid')) wx.switchTab({ url: '/pages/index/index' })
  },

  ensureLogin() {
    if (this.data.logging) return
    this.setData({ logging: true })
    getApp().ensureLogin()
      .then(() => wx.switchTab({ url: '/pages/index/index' }))
      .catch(() => wx.showToast({ title: '登录失败, 请点击重试', icon: 'none' }))
      .finally(() => this.setData({ logging: false }))
  },

  goHome() {
    wx.switchTab({ url: '/pages/index/index' })
  },
})
