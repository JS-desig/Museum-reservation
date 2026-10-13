// 预约码展示页: 二维码 + 复制 + 状态水印 + 取消预约
// type=exhibit 时为「特殊展项体验凭证」(数据源 /wx/exhibit-reservations)
const api = require('../../utils/api')
const { buildQrCells } = require('../../utils/qr')

const STATUS_TEXT = {
  booked: '待使用',
  checked_in: '已核销',
  cancelled: '已取消',
  no_show: '已爽约',
  expired: '已过期',
  used: '已体验',
}

const PAY_TEXT = { unpaid: '待支付', paid: '已支付', refunded: '已退款' }

Page({
  data: { code: '', type: 'entry', resv: null, qrCells: [], statusText: '', payText: '', loading: true },

  onLoad(options) {
    this.setData({ code: options.code || '', type: options.type === 'exhibit' ? 'exhibit' : 'entry' })
  },

  onShow() { this.loadResv() },

  loadResv() {
    const fetch = this.data.type === 'exhibit'
      ? api.get('/wx/exhibit-reservations')
      : api.get('/wx/reservations')
    fetch.then(list => {
      const resv = (list || []).find(r => r.resv_code === this.data.code) || null
      this.setData({
        resv,
        loading: false,
        statusText: resv ? (STATUS_TEXT[resv.status] || '已过期') : '',
        payText: resv && resv.pay_status ? (PAY_TEXT[resv.pay_status] || '') : '',
        qrCells: resv ? buildQrCells(resv.resv_code).map((v, i) => ({ i, v })) : [],
      })
    }).catch(() => this.setData({ resv: null, loading: false }))
  },

  copyCode() {
    if (!this.data.resv) return
    wx.setClipboardData({ data: this.data.resv.resv_code })
  },

  cancel() {
    const isExhibit = this.data.type === 'exhibit'
    wx.showModal({
      title: '取消预约',
      content: isExhibit
        ? '确认取消该展项体验预约? 已支付费用将原路退回'
        : '确认取消该预约? 取消后名额与当日预约次数额度将释放',
      success: res => {
        if (!res.confirm) return
        const req = isExhibit
          ? api.del(`/wx/exhibit-reservations/${this.data.resv.id}`)
          : api.del(`/wx/reservations/${this.data.resv.id}`)
        req.then(() => { wx.showToast({ title: '已取消' }); this.loadResv() })
          .catch(err => wx.showToast({ title: (err && err.message) || '取消失败', icon: 'none' }))
      },
    })
  },

  goHome() { wx.switchTab({ url: '/pages/index/index' }) },
})
