// 预约填单页: 实名信息 + 同行人; 前端身份证校验位校验 + 防重放nonce
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

// 一次性防重放nonce
function genNonce() {
  return 'n' + Date.now().toString(36) + Math.random().toString(36).slice(2, 10)
}

Page({
  data: {
    date: '',
    sessionId: 0,
    sessionName: '',
    // 主预约人(实名后自动带入, 不可修改; 手机号可补填)
    mainVisitor: { real_name: '', id_card_no: '', phone: '' },
    visitors: [],   // 同行人(不含主预约人)
    maxVisitors: 5,
    errors: { mainPhone: '', visitors: [] },
    submitting: false,
  },

  onLoad(options) {
    this.setData({
      date: options.date || '',
      sessionId: Number(options.session_id) || 0,
      sessionName: options.session_name ? decodeURIComponent(options.session_name) : '',
    })
  },

  // 从实名页返回时刷新主预约人(onShow比onLoad多触发)
  onShow() { this.loadProfile() },

  loadProfile() {
    api.get('/wx/profile').then(p => {
      if (p.is_blacklisted) {
        wx.showModal({
          title: '无法预约',
          content: '您已被列入黑名单' + (p.blacklist_reason ? `: ${p.blacklist_reason}` : ''),
          showCancel: false,
          success: () => wx.switchTab({ url: '/pages/index/index' }),
        })
        return
      }
      if (!p.is_verified) {
        wx.showModal({
          title: '需要实名认证',
          content: '预约需完成实名信息绑定',
          success: res => res.confirm && wx.navigateTo({ url: '/pages/realname/realname' }),
        })
        return
      }
      // 实名信息自动填充主预约人(证件号仅脱敏展示, 提交时由服务端补全校验)
      this.setData({
        mainVisitor: {
          real_name: p.real_name || '',
          id_card_no: p.id_card_masked || '',
          phone: '',
        },
      })
    })
  },

  onMainPhone(e) { this.setData({ 'mainVisitor.phone': e.detail.value, 'errors.mainPhone': '' }) },

  addVisitor() {
    if (this.data.visitors.length >= this.data.maxVisitors - 1)
      return wx.showToast({ title: `单笔最多${this.data.maxVisitors}人`, icon: 'none' })
    this.setData({
      visitors: [...this.data.visitors, { real_name: '', id_card_no: '', phone: '' }],
      'errors.visitors': [],
    })
  },

  removeVisitor(e) {
    const { index } = e.currentTarget.dataset
    this.setData({
      visitors: this.data.visitors.filter((_, i) => i !== index),
      'errors.visitors': [],
    })
  },

  onVisitorName(e) {
    const { index } = e.currentTarget.dataset
    this.setData({ [`visitors[${index}].real_name`]: e.detail.value })
  },
  onVisitorCard(e) {
    const { index } = e.currentTarget.dataset
    this.setData({ [`visitors[${index}].id_card_no`]: e.detail.value })
  },

  // 前端校验: 证件号合法 + 不重复; 失败红字定位
  validate() {
    const { mainVisitor, visitors } = this.data
    const errors = { mainPhone: '', visitors: [] }
    if (!mainVisitor.phone || !/^\d{11}$/.test(mainVisitor.phone))
      errors.mainPhone = '请填写11位手机号（实名手机号不再回显）'
    // 主预约人证件号为服务端下发的脱敏值(含*), 校验位由服务端补全后校验
    const mainNo = mainVisitor.id_card_no.toUpperCase()
    const mainMasked = mainNo.includes('*')
    const seen = new Set([mainNo])
    visitors.forEach((v, i) => {
      const no = (v.id_card_no || '').trim().toUpperCase()
      if (!v.real_name.trim() || !no)
        errors.visitors[i] = '请补全同行人实名信息'
      else if (!checkIdCard(no))
        errors.visitors[i] = `${v.real_name} 身份证号校验位错误`
      else if (seen.has(no))
        errors.visitors[i] = `${v.real_name} 身份证号与已填人员重复`
      else
        seen.add(no)
    })
    this.setData({ errors })
    // 主预约人证件号必须存在: 实名后为服务端下发的脱敏值(含*), 未实名则用户不可提交
    return !!mainNo && !!mainVisitor.real_name && !errors.mainPhone && errors.visitors.every(e => !e) && (mainMasked || checkIdCard(mainNo))
  },

  submit() {
    const { mainVisitor, visitors, date, sessionId, submitting } = this.data
    if (submitting) return
    if (!sessionId) return wx.showToast({ title: '请返回重新选择时段', icon: 'none' })
    if (!this.validate()) {
      // 校验失败给可见反馈: 优先展示已定位到具体字段的错误
      const { errors } = this.data
      const err = errors.mainPhone
        || errors.visitors.find(Boolean)
        || (!mainVisitor.real_name || !mainVisitor.id_card_no ? '主预约人信息缺失, 请完成实名后再预约' : '')
        || '请检查填写内容'
      wx.showToast({ title: err, icon: 'none' })
      return
    }
    const all = [
      { real_name: mainVisitor.real_name, id_card_no: mainVisitor.id_card_no.toUpperCase(), phone: mainVisitor.phone },
      ...visitors.map(v => ({ real_name: v.real_name.trim(), id_card_no: v.id_card_no.trim().toUpperCase(), phone: '' })),
    ]
    this.setData({ submitting: true })
    api.post('/wx/reservations', {
      visit_date: date,
      session_id: sessionId,
      visitors: all,
      nonce: genNonce(),
    }).then(data => {
      // redirectTo: 预约成功后不可返回本页重复提交
      wx.redirectTo({ url: `/pages/result/result?code=${data.resv_code}` })
    }).catch(err => wx.showToast({ title: (err && err.message) || '预约失败', icon: 'none' }))
      .finally(() => this.setData({ submitting: false }))
  },
})