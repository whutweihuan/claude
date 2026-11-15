import { useEffect, useRef, useState } from 'react'
import { animate } from 'framer-motion'
import Decimal from 'break_infinity.js'
import { getStore } from '../store/gameStore'
import { formatCoins, formatDuration } from '../game/systems/format'

const DISPLAY_MAX = new Decimal('1e15')

/** 金币缓动滚动（§7.2）；超大数直接切换文本避免精度失真 */
export function AnimatedCoins({ value }: { value: Decimal }) {
  const [text, setText] = useState(() => formatCoins(value))
  const shown = useRef<Decimal>(value)
  useEffect(() => {
    if (value.gt(DISPLAY_MAX) || shown.current.gt(DISPLAY_MAX)) {
      setText(formatCoins(value))
      shown.current = value
      return
    }
    const controls = animate(shown.current.toNumber(), value.toNumber(), {
      duration: 0.45,
      ease: 'easeOut',
      onUpdate: (v) => setText(formatCoins(new Decimal(v)))
    })
    shown.current = value
    return () => controls.stop()
  }, [value])
  return <span className="font-mono tabular-nums">{text}</span>
}

function useIncomeRate(): string {
  const totalEarned = getStore().useGame((s) => s.game.totalEarned)
  const win = useRef<Array<{ t: number; d: Decimal }>>([{ t: Date.now(), d: totalEarned }])
  const [rate, setRate] = useState('0')
  useEffect(() => {
    const t = Date.now()
    const w = win.current
    const first = w[0]
    w.push({ t, d: totalEarned })
    while (w.length > 2 && t - (first?.t ?? t) > 10_000) w.shift()
    const head = w[0]
    const tail = w[w.length - 1]
    if (head && tail && tail.t > head.t) {
      setRate(formatCoins(tail.d.minus(head.d).div(tail.t - head.t).mul(1000)))
    }
  }, [totalEarned])
  return rate
}

export function HUD({ onOpenSettings }: { onOpenSettings: () => void }) {
  const coins = getStore().useGame((s) => s.game.coins)
  const rate = useIncomeRate()
  return (
    <header className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/5 px-5 py-3 backdrop-blur">
      <div className="text-lg font-semibold tracking-widest text-emerald-200/90">Prism Farm · 棱镜农场</div>
      <div className="flex items-center gap-5">
        <div className="text-right">
          <div className="text-xl text-amber-200">
            <AnimatedCoins value={coins} />
          </div>
          <div className="text-[11px] text-white/40">{rate}/秒 · 离线报告最长 {formatDuration(8 * 3600_000)} 起</div>
        </div>
        <button
          type="button"
          onClick={onOpenSettings}
          className="rounded-lg border border-white/15 px-3 py-1.5 text-sm text-white/70 hover:border-white/40"
        >
          设置
        </button>
      </div>
    </header>
  )
}
