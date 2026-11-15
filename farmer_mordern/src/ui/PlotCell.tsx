import { getStore } from '../store/gameStore'
import { buildIndex, plotKey, plotPrice } from '../game/content'
import { isMature, progressOf, stageOf } from '../game/systems/growth'
import { formatCoins } from '../game/systems/format'
import type { PlotState } from '../game/types'
import { PlantSprite } from './PlantSprite'

const CONTENT = buildIndex()

export function firstPlayableCrop(mapId: string): string | null {
  const st = getStore().useGame.getState()
  const crops = CONTENT.cropsByMap[mapId] ?? []
  const preset = crops.find((c) => c.id && st.game.cropsUnlocked[c.id])
  return preset?.id ?? null
}

export function PlotCell({
  mapId,
  n,
  now,
  onPlotClick
}: {
  mapId: string
  n: number
  now: number
  onPlotClick?: (plot: PlotState) => void
}) {
  const id = plotKey(mapId, n)
  const { useGame } = getStore()
  const plot = useGame((s) => s.game.plots[id])
  const coins = useGame((s) => s.game.coins)
  const mapDef = CONTENT.mapById[mapId]
  if (!plot || !mapDef) return null

  const crop = plot.cropId ? (CONTENT.cropById[plot.cropId] ?? null) : null
  const mature = crop !== null && isMature(plot, now)
  const progress = progressOf(plot, now)
  const stage = stageOf(progress)
  const price = plotPrice(mapDef, n)
  const affordable = coins.gte(price)
  const presetName = plot.presetCropId ? CONTENT.cropById[plot.presetCropId]?.name : null

  const priceLabel = plot.unlocked ? '' : formatCoins(price)

  function handleClick() {
    const { dispatch } = getStore().useGame.getState()
    if (!plot) return
    if (onPlotClick) {
      onPlotClick(plot)
      return
    }
    if (!plot.unlocked) {
      dispatch({ t: 'buyPlot', plotId: id })
    } else if (mature) {
      dispatch({ t: 'harvest', plotId: id })
    } else if (!plot.cropId) {
      const cropId = plot.presetCropId ?? firstPlayableCrop(mapId)
      if (cropId) dispatch({ t: 'plant', plotId: id, cropId })
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      className={[
        'relative aspect-square w-full rounded-xl border text-center transition',
        plot.unlocked
          ? 'border-white/10 bg-white/[0.04] hover:border-emerald-300/40'
          : affordable
            ? 'border-dashed border-white/20 bg-white/[0.02] hover:border-amber-300/50'
            : 'border-dashed border-white/10 bg-black/20 text-slate-500',
        mature ? 'plot-glow animate-breathe' : ''
      ].join(' ')}
    >
      {plot.unlocked && crop && (
        <div className="absolute inset-1">
          <PlantSprite crop={crop} stage={mature ? 3 : stage} />
        </div>
      )}
      {plot.unlocked && !crop && <div className="absolute inset-0 grid place-items-center text-2xl text-white/25">+</div>}
      {plot.unlocked && mature && (
        <div className="absolute inset-x-1 bottom-1 rounded bg-emerald-400/90 px-1 py-0.5 text-[10px] font-semibold text-emerald-950">
          可收获
        </div>
      )}
      {plot.unlocked && crop && !mature && (
        <div className="absolute inset-x-1 bottom-1 h-1 overflow-hidden rounded bg-white/10">
          <div className="h-full bg-emerald-300/70" style={{ width: `${Math.round(progress * 100)}%` }} />
        </div>
      )}
      {!plot.unlocked && (
        <div className="absolute inset-0 grid place-items-center text-[11px] leading-tight">
          <span className={affordable ? 'text-amber-200/90' : ''}>{priceLabel}</span>
        </div>
      )}
      {plot.unlocked && !crop && !mature && presetName && (
        <div className="absolute inset-x-0 top-1 truncate px-1 text-[10px] text-white/45">{presetName}</div>
      )}
    </button>
  )
}
