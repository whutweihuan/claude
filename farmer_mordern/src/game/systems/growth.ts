import type { CropDef, PlotState } from '../types'

/** 生长进度（§6）：真值源是墙钟差值 ÷ 种植时刻的 growMs 快照；钳制 0..1。 */
export function progressOf(plot: PlotState, now: number): number {
  if (!plot.unlocked || plot.cropId === null || plot.plantedAt === null || plot.growMs === null) return 0
  if (plot.growMs <= 0) return 1
  const ratio = (now - plot.plantedAt) / plot.growMs
  if (!(ratio > 0)) return 0 // 含时钟回拨（NaN/负值）
  return ratio > 1 ? 1 : ratio
}

export function isMature(plot: PlotState, now: number): boolean {
  return progressOf(plot, now) >= 1
}

/** 有效生长时长 = 基础时长 ÷ (1 + 10%×speed级)，等级钳制 0..10（§4.3） */
export function effectiveGrowMs(crop: CropDef, speedLevel: number): number {
  const lvl = Math.min(Math.max(speedLevel, 0), 10)
  return crop.growTimeMs / (1 + 0.1 * lvl)
}

/** SVG 形态阶段：0 幼苗 → 3 近熟（§7.2） */
export function stageOf(progress: number): 0 | 1 | 2 | 3 {
  if (progress >= 0.95) return 3
  if (progress >= 0.6) return 2
  if (progress >= 0.25) return 1
  return 0
}
