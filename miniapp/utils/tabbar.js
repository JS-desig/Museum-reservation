// 同步自定义 tabBar 的选中态。每个 tab 页在 onShow 里调用:
//   const { syncTabBar } = require('../../utils/tabbar')
//   onShow() { syncTabBar(this, 0) }
// 自定义 tabBar 是每个页面各自持有一个实例, 不主动同步就会停留在上一次的选中项。
function syncTabBar(page, index) {
  if (typeof page.getTabBar === 'function' && page.getTabBar()) {
    page.getTabBar().setData({ selected: index })
  }
}

module.exports = { syncTabBar }
