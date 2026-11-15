import { getStore } from '../store/gameStore'
import { buildIndex } from '../game/content'
import { formatCoins, formatDuration } from '../game/systems/format'
import { progressOf } from '../game/systems/growth'
import { harvestGain } from '../game/systems/engine'
import { CropPicker } from './CropPicker'
import { PlantSprite } from './PlantSprite'
import { spawnFloat } from './floatText'

const CONTENT = buildIndex()

/** 生长中地块：更换预设（下轮生效）/ 清茬改种（立即，进度作废）—— §7.1 */
export function PlotDetail({ plotId, now }: { plotId: string; now: number }) {
  const { useGame } = getStore()
  const plot = useGame((s) => s.game.plots[plotId])
  if (!plot) return null
  const i = plotId.lastIndexOf(':')
  const mapId = plotId.slice(0, i)
  const crop = plot.cropId ? (CONTENT.cropById[plot.cropId] ?? null) : null
  const preset = plot.presetCropId ? (CONTENT.cropById[plot.presetCropId] ?? null) : null
  const progress = progressOf(plot, now)
  const { dispatch } = useGame.getState()

  return (
    <section className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
      <div className="mb-2 flex items-center gap-3">
        {crop ? (
          <div className="h-12 w-12">
            <PlantSprite crop={crop} stage={progress > 0.95 ? 3 : progress > 0.6 ? 2 : progress > 0.25 ? 1 : 0} />
          </div>
        ) : (
          <div className="grid h-12 w-12 place-items-center rounded border border-dashed border-white/15 text-white/30">+</div>
        )}
        <div className="text-sm">
          <div className="text-white/85">{crop ? `生长中：${crop.name}` : '空地'}</div>
          {crop && plot.plantedAt !== null && plot.growMs !== null && (
            <div className="text-xs text-white/45">
              {Math.floor(progress * 100)}% · 还需 {formatDuration(plot.plantedAt + plot.growMs - now)} · 收成{' '}
              {formatCoins(harvestGain(useGame.getState().game, CONTENT, mapId, crop))}
            </div>
          )}
          {preset && <div className="text-xs text-white/45">下轮预设：{preset.name}</div>}
        </div>
      </div>
      <div className="mb-1 text-xs text-white/50">{crop ? '更换预设作物（当前轮不打断）' : '选择作物种下'}</div>
      <CropPicker
        mapId={mapId}
        mode={crop ? 'preset' : 'plant'}
        onPick={(cropId) => {
          if (crop) {
            if (dispatch({ t: 'swapPreset', plotId, cropId })) spawnFloat(window.innerWidth / 2, 120, '已更换预设', 'info')
          } else {
            dispatch({ t: 'plant', plotId, cropId })
          }
        }}
      />
      {crop && (
        <button
          type="button"
          onClick={() => dispatch({ t: 'clearCrop', plotId })}
          className="mt-2 rounded-lg border border-rose-300/30 px-3 py-1 text-xs text-rose-200/80 hover:bg-rose-400/10"
        >
          清茬改种（进度作废）
        </button>
      )}
    </section>
  )
}
