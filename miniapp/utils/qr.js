// 由预约码确定性生成装饰性二维码点阵(25x25): 同一预约码始终得到同一图案
// 说明: 这是演示用的视觉图案, 不是真实可扫的 QR 编码
// (算法与 pages/result 一致, 提取出来供扫码 tab 复用)
function buildQrCells(code) {
  const cells = []
  let seed = 0
  for (const ch of String(code || '')) seed = (seed * 31 + ch.charCodeAt(0)) >>> 0
  for (let i = 0; i < 625; i++) {
    const r = i / 25 | 0, c = i % 25
    const finder = (r < 7 && c < 7) || (r < 7 && c > 17) || (r > 17 && c < 7)
    const ring = r === 0 || r === 6 || c === 0 || c === 6
    if (finder) {
      cells.push(ring ? 2 : (r >= 2 && r <= 4 && c >= 2 && c <= 4 ? 2 : 0))
    } else {
      seed = (seed * 1103515245 + 12345) >>> 0
      cells.push((seed >>> 16) % 2)
    }
  }
  return cells
}

module.exports = { buildQrCells }
