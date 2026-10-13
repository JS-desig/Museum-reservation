// 展项海报匹配: 本地插画 + 媒体类型占位 (首页与展项列表页共用)
// 小程序 <image> 不支持 HTTP 远端图, 统一使用包内 images/ 资源

// 展品媒体类型 → 占位图形 (video/audio 无法用 <image> 呈现)
const PH = { video: '🎬', audio: '🎧', image: '🔬' }

// 按展项标题关键字匹配本地插画; 未命中时按媒体类型给默认图
const LOCAL_IMG = [
  { key: '科技之光', img: '/images/hall_light.png' },
  { key: '物理', img: '/images/kids_physics.png' },
  { key: '基因', img: '/images/gene.png' },
  { key: '牡丹', img: '/images/peony.png' },
  { key: '航天', img: '/images/space.png' },
]
const DEFAULT_IMG = {
  image: '/images/hall_light.png',
  video: '/images/kids_physics.png',
  audio: '/images/peony.png',
}

function localImgOf(title, mediaType) {
  const hit = LOCAL_IMG.find(m => (title || '').indexOf(m.key) >= 0)
  return hit ? hit.img : (DEFAULT_IMG[mediaType] || DEFAULT_IMG.image)
}

// 组装海报字段: img 为本地插画路径, ph 为媒体类型占位符
function posterOf(e) {
  return {
    img: localImgOf(e.title, e.media_type),
    ph: PH[e.media_type] || '🏛',
    imgFailed: false,
  }
}

module.exports = { posterOf, PH }
