// 自定义底部菜单: 首页 / 预约 / 扫码 / 我的
// 说明: app.json 里 tabBar.custom=true, 微信不再渲染原生 tabBar, 改由本组件绘制。
// 每个 tab 页需在 onShow 里调用 this.getTabBar().setData({ selected: N }) 同步选中态。
Component({
  data: {
    selected: 0,
    list: [
      { pagePath: '/pages/index/index',     text: '首页', icon: 'home' },
      { pagePath: '/pages/tickets/tickets', text: '预约', icon: 'ticket' },
      { pagePath: '/pages/scan/scan',       text: '扫码', icon: 'scan' },
      { pagePath: '/pages/mine/mine',       text: '我的', icon: 'user' },
    ],
  },

  methods: {
    onTap(e) {
      const index = e.currentTarget.dataset.index
      if (index === this.data.selected) return
      wx.switchTab({ url: this.data.list[index].pagePath })
    },
  },
})
