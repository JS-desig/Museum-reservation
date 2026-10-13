// 全局登录引导: 任何页面请求前保证已有 openid
// Demo 约定: 后端把 wx.login 的 code 直接当 openid 用, 因此 401 重试时
// 必须复用同一个 code 重建会话 —— 重新 wx.login 会产生新 code = 新用户, 老数据全部丢失
const BASE_URL = 'http://192.168.110.196:8000/api'

App({
  _loginPromise: null,

  // 优先级: 内存 > 本地缓存。只在首次(两者皆无)才调 wx.login
  _currentOpenid() {
    return this._openid || wx.getStorageSync('openid') || ''
  },

  // 单例Promise: 并发请求只触发一次登录
  ensureLogin() {
    if (!this._loginPromise) {
      const openid = this._currentOpenid()
      if (openid) {
        this._loginPromise = Promise.resolve(openid)
      } else {
        this._loginPromise = new Promise((resolve, reject) => {
          wx.login({
            success: res => {
              // 直接发登录请求(不经 utils/api, 避免与 getApp().ensureLogin 循环依赖)
              wx.request({
                url: BASE_URL + '/wx/login',
                method: 'POST',
                data: { code: res.code, nickname: '微信用户' },
                success: r => {
                  if (r.data && r.data.code === 0) {
                    this._openid = res.code
                    wx.setStorageSync('openid', res.code)
                    resolve(res.code)
                  } else {
                    this._loginPromise = null
                    reject(r.data)
                  }
                },
                fail: err => {
                  this._loginPromise = null
                  reject(err)
                },
              })
            },
            fail: err => {
              this._loginPromise = null
              reject(err)
            },
          })
        })
      }
    }
    return this._loginPromise
  },

  // 身份失效(40100): 用同一 openid 重建会话。后端不可达等场景由调用方 catch
  resetLogin() {
    this._loginPromise = null
  },
})