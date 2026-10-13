// 小程序全局请求封装: 自动携带openid, 40100自动重新登录后重试一次
const BASE_URL = 'http://192.168.110.196:8000/api'  // 开发环境; 生产环境替换为 HTTPS 域名

function rawRequest(method, path, data = {}) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: BASE_URL + path,
      method,
      data,
      header: { 'X-Wx-Openid': wx.getStorageSync('openid') || '' },
      success(res) {
        if (res.data.code === 0) resolve(res.data.data)
        else reject(res.data)
      },
      fail: reject,
    })
  })
}

function request(method, path, data = {}, retried = false) {
  const app = getApp()
  return app.ensureLogin().then(() => rawRequest(method, path, data)).catch(err => {
    // 身份失效: 重置登录态并重试一次(仅一次, 防循环)
    if (err && err.code === 40100 && !retried) {
      app.resetLogin()
      return request(method, path, data, true)
    }
    throw err
  })
}

module.exports = {
  get: (p, q) => request('GET', p + (q ? '?' + Object.entries(q).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join('&') : '')),
  post: (p, d) => request('POST', p, d),
  del: p => request('DELETE', p),
  BASE_URL,
}
