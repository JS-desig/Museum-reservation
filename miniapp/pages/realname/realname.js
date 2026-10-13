// 实名认证页: 未绑定可编辑提交, 已绑定脱敏回显; 前端实时校验(身份证校验位/手机号)
const api = require('../../utils/api')

// GB11643 身份证校验位
function checkIdCard(no) {
  if (!/^\d{17}[\dXx]$/.test(no)) return false
  const W = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
  const CODES = '10X98765432'
  let sum = 0
  for (let i = 0; i < 17; i++) sum += Number(no[i]) * W[i]
  return CODES[sum % 11] === no[17].toUpperCase()
}

Page({
  data: {
    verified: false,
    real_name: '', id_card_no: '', phone: '',
    real_name_masked: '', id_card_masked: '', phone_masked: '',
    errors: { name: '', card: '', phone: '' },
    submitting: false,
  },

  onShow() { this.loadProfile() },

  loadProfile() {
    api.get('/wx/profile').then(p => {
      if (p.is_verified) {
        this.setData({
          verified: true,
          real_name_masked: this.maskName(p.real_name || ''),
          id_card_masked: p.id_card_masked || '',
          phone_masked: p.phone_masked || '',
        })
      }
    }).catch(() => { /* 未登录: 保留未实名表单态 */ })
  },

  // 姓名脱敏: 首字保留 + *
  maskName(name) {
    if (!name) return ''
    return name[0] + '*'.repeat(Math.max(name.length - 1, 1))
  },

  onName(e) { this.setData({ real_name: e.detail.value, 'errors.name': '' }) },
  onCard(e) { this.setData({ id_card_no: e.detail.value, 'errors.card': '' }) },
  onPhone(e) { this.setData({ phone: e.detail.value, 'errors.phone': '' }) },

  validate() {
    const { real_name, id_card_no, phone } = this.data
    const errors = { name: '', card: '', phone: '' }
    if (!real_name.trim()) errors.name = '请输入真实姓名'
    if (!id_card_no) errors.card = '请输入身份证号'
    else if (!checkIdCard(id_card_no)) errors.card = '身份证号校验位错误'
    if (!phone) errors.phone = '请输入手机号'
    else if (!/^\d{11}$/.test(phone)) errors.phone = '手机号格式错误'
    this.setData({ errors })
    return !errors.name && !errors.card && !errors.phone
  },

  submit() {
    if (this.data.submitting) return
    if (!this.validate()) return
    const { real_name, id_card_no, phone } = this.data
    this.setData({ submitting: true })
    api.post('/wx/realname', { real_name: real_name.trim(), id_card_no, phone })
      .then(() => {
        wx.showToast({ title: '实名成功' })
        setTimeout(() => {
          const pages = getCurrentPages()
          // 实名成功回填上一页(如预约填单/我的页): 触发其 onShow 刷新
          if (pages.length > 1) wx.navigateBack()
          else wx.switchTab({ url: '/pages/mine/mine' })
        }, 1200)
      })
      .catch(err => wx.showToast({ title: (err && err.message) || '实名失败', icon: 'none' }))
      .finally(() => this.setData({ submitting: false }))
  },

  onRebind() {
    wx.showModal({
      title: '重新绑定',
      content: '确认重新填写实名信息? 提交后将覆盖当前绑定。',
      success: res => {
        if (!res.confirm) return
        this.setData({
          verified: false,
          real_name: '', id_card_no: '', phone: '',
          errors: { name: '', card: '', phone: '' },
        })
      },
    })
  },
})