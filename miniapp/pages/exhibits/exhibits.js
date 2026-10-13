// 展项列表页 — 全部展厅展项, 按展厅分组浏览; 特殊展项(付费体验)与普通展项(仅参观)区分展示
const api = require('../../utils/api')
const { posterOf } = require('../../utils/poster')

const WEEK = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
const pad = n => String(n).padStart(2, '0')
const ymd = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`

Page({
  data: {
    halls: [],        // [{ name, exhibits: [...] }]
    hallTabs: [],     // 顶部展厅筛选: [{ name, count }]
    activeHall: '全部',
    loading: true,
  },

  onLoad() { this.load() },

  onPullDownRefresh() { this.load(() => wx.stopPullDownRefresh()) },

  load(done) {
    api.get('/exhibits').then(list => {
      const exhibits = (list || []).map(e => {
        const item = Object.assign({}, e, posterOf(e))
        if (item.is_special) {
          // 价格分 → 元展示
          item.priceYuan = (item.price_cent / 100).toFixed(1).replace(/\.0$/, '')
        }
        return item
      })
      // 按展厅分组 (后端已按 hall_name, sort_order 排序)
      const hallMap = new Map()
      exhibits.forEach(e => {
        const name = e.hall_name || '其他展项'
        if (!hallMap.has(name)) hallMap.set(name, [])
        hallMap.get(name).push(e)
      })
      const halls = [...hallMap.entries()].map(([name, items]) => ({ name, exhibits: items }))
      this.setData({
        halls,
        hallTabs: [{ name: '全部', count: exhibits.length },
                   ...halls.map(h => ({ name: h.name, count: h.exhibits.length }))],
        loading: false,
      })
    }).catch(() => this.setData({ halls: [], hallTabs: [], loading: false }))
      .finally(() => { if (done) done() })
  },

  selectHall(e) {
    this.setData({ activeHall: e.currentTarget.dataset.name })
  },

  // 本地插画加载失败时回落占位符, 避免裂图
  onExhibitImgError(e) {
    const { group, index } = e.currentTarget.dataset
    this.setData({ [`halls[${group}].exhibits[${index}].imgFailed`]: true })
  },

  // 普通展项卡点击 → 详情语义: 跳入馆预约(免费参观)
  goBooking() { wx.switchTab({ url: '/pages/tickets/tickets' }) },

  // 特殊展项「体验预约」→ 展项预约页(选日期时段+支付)
  goExhibitBooking(e) {
    const { group, index } = e.currentTarget.dataset
    const ex = this.data.halls[group] && this.data.halls[group].exhibits[index]
    if (!ex) return
    wx.navigateTo({
      url: `/pages/exhibit-booking/exhibit-booking?exhibit_id=${ex.id}&title=${encodeURIComponent(ex.title)}&price_cent=${ex.price_cent}`,
    })
  },
})

