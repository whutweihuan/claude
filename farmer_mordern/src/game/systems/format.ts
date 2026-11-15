import Decimal from 'break_infinity.js'

const UNITS = ['', 'K', 'M', 'B', 'T', 'Qa', 'Qi', 'Sx', 'Sp', 'Oc', 'No', 'Dc'] as const

/** 金额统一显示入口（§8.3）：<1000 取整；K..Dc 阶梯；≥1e36 科学计数 */
export function formatCoins(d: Decimal): string {
  if (d.eq(0)) return '0'
  const tier = Math.floor(d.log10() / 3)
  if (tier >= UNITS.length) {
    return `${d.mantissa.toFixed(2)}e+${d.e}`
  }
  let mantissa = d.div(new Decimal(10).pow(tier * 3)).toNumber()
  let t = tier
  if (mantissa >= 999.995) {
    mantissa /= 1000
    t += 1
    if (t >= UNITS.length) return `${d.mantissa.toFixed(2)}e+${d.e}`
  }
  return t === 0 ? String(Math.round(mantissa)) : `${mantissa.toFixed(2)}${UNITS[t]}`
}

/** 时长显示：秒 / 分 / 小时+分 / 天+小时；负值（时钟回拨）按 0 */
export function formatDuration(ms: number): string {
  const totalSec = Math.max(0, Math.floor(ms / 1000))
  if (totalSec < 60) return `${totalSec}秒`
  const totalMin = Math.floor(totalSec / 60)
  if (totalMin < 60) return `${totalMin}分`
  const hours = Math.floor(totalMin / 60)
  if (hours < 24) return `${hours}小时${totalMin % 60}分`
  return `${Math.floor(hours / 24)}天${hours % 24}小时`
}

export function formatPercent(x: number): string {
  const v = Math.round(x * 1000) / 10
  return `${v}%`
}
