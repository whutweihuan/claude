import { getStore } from '../store/gameStore'
import { buildIndex } from '../game/content'
import { canMigrate } from '../game/systems/engine'
import { formatCoins } from '../game/systems/format'
import Decimal from 'break_infinity.js'

const CONTENT = buildIndex()

const MISSING_TEXT: Record<'plots' | 'coins' | 'prereq', string> = {
  plots: '需先开垦完上一张图的全部地块',
  coins: '金币不足以支付迁徙费',
  prereq: '前置地图尚未完成'
}

/** 地图侧栏：解锁图可切换，锁定图灰显 + 解锁条件 tooltip（§7.1） */
export function MapRail({ active, onPick }: { active: string; onPick: (mapId: string) => void }) {
  const { useGame } = getStore()
  const maps = useGame((s) => s.game.maps)
  const game = useGame((s) => s.game)
  return (
    <nav className="flex w-36 shrink-0 flex-col gap-2">
      {CONTENT.maps.map((m) => {
        const unlocked = maps[m.id]?.unlocked ?? false
        const prev = CONTENT.maps[m.order - 2]
        const gate = prev ? canMigrate(game, CONTENT, m.id) : null
        const costHint = prev?.migrationCost ? formatCoins(new Decimal(prev.migrationCost)) : null
        const tip = unlocked
          ? m.name
          : gate && prev && costHint
            ? `${m.name}：开垦完「${prev.name}」全部地块并支付 ${costHint} 迁徙费 —— ${gate.ok ? '条件已满足！' : MISSING_TEXT[gate.missing]}`
            : m.name
        return (
          <button
            key={m.id}
            type="button"
            title={tip}
            onClick={() => unlocked && onPick(m.id)}
            className={[
              'rounded-xl border px-3 py-2 text-left text-sm transition',
              unlocked
                ? m.id === active
                  ? 'bg-emerald-400/10 text-emerald-50'
                  : 'border-white/15 bg-white/[0.03] text-white/80 hover:border-white/40'
                : gate?.ok
                  ? 'cursor-pointer border-amber-300/50 bg-amber-400/5 text-amber-100/85'
                  : 'cursor-not-allowed border-white/5 bg-black/30 text-white/25'
            ].join(' ')}
            style={unlocked ? { borderColor: `hsl(${m.hue} 60% 60% / 0.55)` } : undefined}
          >
            <span className="mr-2 inline-block h-2 w-2 rounded-full" style={{ background: `hsl(${m.hue} 70% 62%)` }} />
            {m.name}
            {!unlocked && <div className="mt-0.5 text-[10px] opacity-70">{gate?.ok ? '★ 可迁徙' : '未解锁'}</div>}
          </button>
        )
      })}
    </nav>
  )
}
