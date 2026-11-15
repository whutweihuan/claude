import Decimal from 'break_infinity.js'
import { getStore } from '../store/gameStore'
import { buildIndex, upgradeCost, upgradeKey } from '../game/content'
import { UPGRADE_DEFS } from '../game/content/upgrades'
import { canMigrate } from '../game/systems/engine'
import { formatCoins, formatPercent } from '../game/systems/format'
import { PlotDetail } from './PlotDetail'
import { playSound } from './sound'
import type { UpgradeDef } from '../game/types'

const CONTENT = buildIndex()

function UpgradeRow({ def, mapId }: { def: UpgradeDef; mapId: string }) {
  const { useGame } = getStore()
  const upgrades = useGame((s) => s.game.upgrades)
  const coins = useGame((s) => s.game.coins)
  const scope = def.scope === 'global' ? 'global' : mapId
  const mapDef = def.scope === 'global' ? null : (CONTENT.mapById[mapId] ?? null)
  const level = upgrades[upgradeKey(def.id, scope)] ?? 0
  const maxed = level >= def.maxLevel
  const cost = maxed ? null : upgradeCost(def, mapDef, level)
  const prereqMissing = def.kind === 'autoReplant' && (upgrades[upgradeKey('autoHarvest', mapId)] ?? 0) < 1
  const affordable = cost !== null && coins.gte(cost) && !prereqMissing
  const effectText =
    def.kind === 'soil'
      ? `收获 +${formatPercent(def.effectPerLevel)}/级`
      : def.kind === 'speed'
        ? `生长 +${formatPercent(def.effectPerLevel)}/级`
        : def.kind === 'offlineLamp'
          ? '离线结算上限 +1 档'
          : '本图启用'
  return (
    <button
      type="button"
      disabled={!affordable}
      onClick={() => {
          if (useGame.getState().dispatch({ t: 'buyUpgrade', defId: def.id, scope })) playSound('buy')
        }}
      className={[
        'flex w-full items-center justify-between rounded-lg border px-2.5 py-1.5 text-left text-xs',
        maxed
          ? 'border-white/5 text-white/30'
          : affordable
            ? 'border-white/15 bg-white/[0.04] hover:border-amber-300/50'
            : 'border-white/5 text-white/35'
      ].join(' ')}
      title={prereqMissing ? '需要先购买「自动收获」' : undefined}
    >
      <span>
        <span className="text-white/85">{def.name}</span>
        {def.maxLevel > 1 && <span className="ml-1 text-white/40">Lv{level}</span>}
        <span className="ml-2 text-white/40">{effectText}</span>
      </span>
      <span className="font-mono text-amber-200/80">{maxed ? 'MAX' : cost ? formatCoins(cost) : ''}</span>
    </button>
  )
}

export function ShopPanel({
  mapId,
  selectedPlotId,
  now,
  onMigrated
}: {
  mapId: string
  selectedPlotId: string | null
  now: number
  onMigrated: (nextMapId: string) => void
}) {
  const { useGame } = getStore()
  const game = useGame((s) => s.game)
  const mapDef = CONTENT.mapById[mapId]
  if (!mapDef) return null
  const next = CONTENT.maps[mapDef.order]
  const gate = next ? canMigrate(game, CONTENT, next.id) : null
  const crops = CONTENT.cropsByMap[mapId] ?? []

  return (
    <aside className="flex w-80 shrink-0 flex-col gap-3 overflow-y-auto pr-1">
      {selectedPlotId && <PlotDetail plotId={selectedPlotId} now={now} />}
      <section className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
        <div className="mb-2 text-xs font-semibold tracking-wider text-white/60">作物解锁 · {mapDef.name}</div>
        <div className="flex flex-col gap-1.5">
          {crops
            .filter((c) => c.unlockCost !== null && !game.cropsUnlocked[c.id])
            .map((c) => {
              const cost = new Decimal(c.unlockCost ?? '0')
              const afford = game.coins.gte(cost)
              return (
                <button
                  key={c.id}
                  type="button"
                  disabled={!afford}
                  onClick={() => {
                  if (useGame.getState().dispatch({ t: 'unlockCrop', cropId: c.id })) playSound('unlock')
                }}
                  className={[
                    'flex items-center justify-between rounded-lg border px-2.5 py-1.5 text-xs',
                    afford ? 'border-white/15 hover:border-emerald-300/50' : 'border-white/5 text-white/30'
                  ].join(' ')}
                >
                  <span className="text-white/85">{c.name}</span>
                  <span className="font-mono text-amber-200/80">{formatCoins(cost)}</span>
                </button>
              )
            })}
          {crops.every((c) => c.unlockCost === null || game.cropsUnlocked[c.id]) && (
            <div className="text-xs text-white/35">本图作物已全部解锁 ✦</div>
          )}
        </div>
      </section>
      <section className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
        <div className="mb-2 text-xs font-semibold tracking-wider text-white/60">升级与自动化</div>
        <div className="flex flex-col gap-1.5">
          {UPGRADE_DEFS.map((def) => (
            <UpgradeRow key={def.id} def={def} mapId={mapId} />
          ))}
        </div>
      </section>
      {next && (
        <button
          type="button"
          disabled={!gate?.ok}
          onClick={() => {
            if (gate?.ok && useGame.getState().dispatch({ t: 'migrate', mapId: next.id })) {
              playSound('migrate')
              onMigrated(next.id)
            }
          }}
          className={[
            'rounded-xl border px-3 py-2.5 text-sm font-medium',
            gate?.ok
              ? 'border-amber-300/60 bg-amber-400/10 text-amber-100 hover:bg-amber-400/20'
              : 'border-white/10 text-white/30'
          ].join(' ')}
        >
          迁徙 → {next.name}
          <span className="ml-2 font-mono text-xs text-amber-200/70">{formatCoins(new Decimal(mapDef.migrationCost ?? '0'))}</span>
          {!gate?.ok && <div className="mt-0.5 text-[10px] font-normal text-white/40">{gate?.missing === 'plots' ? '先开垦完本图全部地块' : '继续攒钱'}</div>}
        </button>
      )}
    </aside>
  )
}
