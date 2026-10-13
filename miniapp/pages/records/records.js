// 通行记录页: GET /wx/pass-records, 入/出馆区分, 倒序
const api = require('../../utils/api')

function fmtTime(s) {
  // 后端返回 "YYYY-MM-DD HH:MM:SS(.ffffff)"; 展示成 MM-DD HH:MM
  const m = String(s || '').match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/)
  return m ? `${m[2]}-${m[3]} ${m[4]}:${m[5]}` : String(s || '')
}

Page({
  data: { records: [], loading: true },

  onShow() { this.load() },

  onPullDownRefresh() {
    this.load(() => wx.stopPullDownRefresh())
  },

  load(done) {
    api.get('/wx/pass-records').then(list => {
      this.setData({
        records: (list || []).map(l => Object.assign({}, l, { pass_time_text: fmtTime(l.pass_time) })),
        loading: false,
      })
    }).catch(() => this.setData({ records: [], loading: false }))
      .finally(() => { if (done) done() })
  },
})