import Decimal from 'break_infinity.js'
import { getStore } from '../store/gameStore'
import { buildIndex } from '../game/content'
import { formatCoins, formatDuration } from '../game/systems/format'
import type { CropDef } from '../game/types'

const CONTENT = buildIndex()

/** 地块详情的选种面板：显示回本周期（§4.4 语义：seed/(yield−seed)×grow） */
export function CropPicker({
  mapId,
  mode,
  onPick
}: {
  mapId: string
  mode: 'plant' | 'preset'
  onPick: (cropId: string) => void
}) {
  const { useGame } = getStore()
  const cropsUnlocked = useGame((s) => s.game.cropsUnlocked)
  const coins = useGame((s) => s.game.coins)
  const crops = (CONTENT.cropsByMap[mapId] ?? []).filter((c) => cropsUnlocked[c.id])
  return (
    <div className="grid grid-cols-2 gap-2">
      {crops.map((c: CropDef) => {
        const seed = new Decimal(c.seedCost)
        const net = new Decimal(c.yieldCoins).minus(seed)
        const paybackMs = net.gt(0) ? (seed.div(net).toNumber() || 0) * c.growTimeMs : c.growTimeMs
        const affordable = mode === 'preset' || coins.gte(seed)
        return (
          <button
            key={c.id}
            type="button"
            disabled={!affordable}
            onClick={() => onPick(c.id)}
            className={[
              'rounded-lg border px-2 py-1.5 text-left text-xs',
              affordable ? 'border-white/15 bg-white/[0.04] hover:border-emerald-300/50' : 'border-white/5 text-white/25'
            ].join(' ')}
          >
            <div className="font-medium text-white/90">{c.name}</div>
            <div className="text-white/45">
              {mode === 'plant' ? `种价 ${formatCoins(seed)} · ` : ''}
              收 {formatCoins(new Decimal(c.yieldCoins))} / {formatDuration(c.growTimeMs)}
            </div>
            <div className="text-white/35">回本 {formatDuration(paybackMs)}</div>
          </button>
        )
      })}
      {crops.length === 0 && <div className="col-span-2 text-xs text-white/40">该图暂无可种作物</div>}
    </div>
  )
}
