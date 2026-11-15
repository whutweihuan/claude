import { Decimal } from '../types'
import type { ApplyResult, GameEvent, RunState } from '../types'
import { buildIndex, plotKey, plotPrice, upgradeKey } from '../content'
import type { ContentIndex } from '../content'
import { effectiveGrowMs, isMature } from './growth'

export { plotPrice }

/** 金额记账统一原则（§4.5）：任何种植（含未来的自动补种）一律扣 seedCost，任何收获一律加 yieldCoins。 */

interface PlotRef {
  mapId: string
  n: number
}

function parsePlotId(id: string): PlotRef | null {
  const i = id.lastIndexOf(':')
  if (i <= 0) return null
  const n = Number(id.slice(i + 1))
  if (!Number.isInteger(n) || n < 0) return null
  return { mapId: id.slice(0, i), n }
}

export function soilMult(s: RunState, _c: ContentIndex, mapId: string): number {
  return 1 + 0.25 * (s.upgrades[upgradeKey('soil', mapId)] ?? 0)
}

function speedLevel(s: RunState, mapId: string): number {
  return s.upgrades[upgradeKey('speed', mapId)] ?? 0
}

function cloneState(s: RunState): RunState {
  const plots: RunState['plots'] = {}
  for (const [k, p] of Object.entries(s.plots)) plots[k] = { ...p }
  return {
    ...s,
    coins: new Decimal(s.coins),
    totalEarned: new Decimal(s.totalEarned),
    plots,
    maps: { ...s.maps },
    cropsUnlocked: { ...s.cropsUnlocked },
    upgrades: { ...s.upgrades },
    foreign: { ...s.foreign }
  }
}

function reject(s: RunState, reason: ApplyResult['reason']): ApplyResult {
  return { ok: false, reason, state: s }
}

/** 初始局：首图解锁并赠地，自动作物可用（§4.2） */
export function initialState(c: ContentIndex, now: number): RunState {
  const plots: RunState['plots'] = {}
  const maps: RunState['maps'] = {}
  const cropsUnlocked: RunState['cropsUnlocked'] = {}
  const first = c.maps[0]
  for (const m of c.maps) {
    maps[m.id] = { unlocked: m === first }
    for (let n = 0; n < m.plotCount; n++) {
      plots[plotKey(m.id, n)] = {
        id: plotKey(m.id, n),
        unlocked: m === first && n < m.freePlots,
        cropId: null,
        presetCropId: null,
        plantedAt: null,
        growMs: null
      }
    }
  }
  if (first) {
    for (const crop of c.cropsByMap[first.id] ?? []) {
      if (crop.unlockCost === null) cropsUnlocked[crop.id] = true
    }
  }
  return {
    schemaVersion: 1,
    coins: new Decimal(15),
    totalEarned: new Decimal(0),
    plots,
    maps,
    cropsUnlocked,
    upgrades: {},
    lastSeenAt: now,
    startedAt: now,
    foreign: {}
  }
}

/** 迁徙/解锁新图时该图自动作物置为可用 */
export function autoUnlockCrops(s: RunState, c: ContentIndex, mapId: string): void {
  for (const crop of c.cropsByMap[mapId] ?? []) {
    if (crop.unlockCost === null) s.cropsUnlocked[crop.id] = true
  }
}

function doPlant(s: RunState, c: ContentIndex, plotId: string, cropId: string, now: number): ApplyResult {
  const plot = s.plots[plotId]
  const ref = parsePlotId(plotId)
  if (!plot || !ref) return reject(s, 'invalid')
  if (!s.maps[ref.mapId]?.unlocked) return reject(s, 'locked')
  if (!plot.unlocked) return reject(s, 'locked')
  if (plot.cropId !== null) return reject(s, 'invalid')
  const crop = c.cropById[cropId]
  if (!crop || crop.mapId !== ref.mapId) return reject(s, 'invalid')
  if (!s.cropsUnlocked[cropId]) return reject(s, 'locked')
  const cost = new Decimal(crop.seedCost)
  if (s.coins.lt(cost)) return reject(s, 'noCoins')
  const next = cloneState(s)
  const p = next.plots[plotId]
  if (!p) return reject(s, 'invalid')
  next.coins = next.coins.minus(cost)
  p.cropId = cropId
  p.presetCropId = cropId
  p.plantedAt = now
  p.growMs = effectiveGrowMs(crop, speedLevel(next, ref.mapId))
  return { ok: true, state: next }
}

function doHarvest(s: RunState, c: ContentIndex, plotId: string, now: number): ApplyResult {
  const plot = s.plots[plotId]
  const ref = parsePlotId(plotId)
  if (!plot || !ref || !plot.unlocked) return reject(s, 'invalid')
  if (plot.cropId === null || !isMature(plot, now)) return reject(s, 'invalid')
  const crop = c.cropById[plot.cropId]
  if (!crop) return reject(s, 'invalid')
  const gain = new Decimal(crop.yieldCoins).mul(soilMult(s, c, ref.mapId))
  const next = cloneState(s)
  const p = next.plots[plotId]
  if (!p) return reject(s, 'invalid')
  next.coins = next.coins.plus(gain)
  next.totalEarned = next.totalEarned.plus(gain)
  p.cropId = null
  p.plantedAt = null
  p.growMs = null
  return { ok: true, state: next }
}

function doBuyPlot(s: RunState, c: ContentIndex, plotId: string): ApplyResult {
  const ref = parsePlotId(plotId)
  const plot = s.plots[plotId]
  if (!plot || !ref) return reject(s, 'invalid')
  const map = c.mapById[ref.mapId]
  if (!map) return reject(s, 'invalid')
  if (!s.maps[map.id]?.unlocked) return reject(s, 'locked')
  if (plot.unlocked) return reject(s, 'alreadyOwned')
  if (ref.n > 0 && !s.plots[plotKey(map.id, ref.n - 1)]?.unlocked) return reject(s, 'notSequenced')
  const price = plotPrice(map, ref.n)
  if (s.coins.lt(price)) return reject(s, 'noCoins')
  const next = cloneState(s)
  const p = next.plots[plotId]
  if (!p) return reject(s, 'invalid')
  next.coins = next.coins.minus(price)
  p.unlocked = true
  return { ok: true, state: next }
}

function doUnlockCrop(s: RunState, c: ContentIndex, cropId: string): ApplyResult {
  const crop = c.cropById[cropId]
  if (!crop) return reject(s, 'invalid')
  if (s.cropsUnlocked[cropId]) return reject(s, 'alreadyOwned')
  if (!s.maps[crop.mapId]?.unlocked) return reject(s, 'locked')
  if (crop.unlockCost === null) return reject(s, 'alreadyOwned')
  const cost = new Decimal(crop.unlockCost)
  if (s.coins.lt(cost)) return reject(s, 'noCoins')
  const next = cloneState(s)
  next.coins = next.coins.minus(cost)
  next.cropsUnlocked[cropId] = true
  return { ok: true, state: next }
}

function doSwapPreset(s: RunState, c: ContentIndex, plotId: string, cropId: string): ApplyResult {
  const plot = s.plots[plotId]
  const ref = parsePlotId(plotId)
  if (!plot || !ref || !plot.unlocked) return reject(s, 'invalid')
  const crop = c.cropById[cropId]
  if (!crop || crop.mapId !== ref.mapId) return reject(s, 'invalid')
  if (!s.cropsUnlocked[cropId]) return reject(s, 'locked')
  const next = cloneState(s)
  const p = next.plots[plotId]
  if (!p) return reject(s, 'invalid')
  p.presetCropId = cropId
  return { ok: true, state: next }
}

function doClearCrop(s: RunState, plotId: string): ApplyResult {
  const plot = s.plots[plotId]
  if (!plot || !plot.unlocked) return reject(s, 'invalid')
  if (plot.cropId === null) return reject(s, 'invalid')
  const next = cloneState(s)
  const p = next.plots[plotId]
  if (!p) return reject(s, 'invalid')
  p.cropId = null
  p.plantedAt = null
  p.growMs = null
  return { ok: true, state: next }
}

export function applyEvent(s: RunState, ev: GameEvent, c: ContentIndex, now: number): ApplyResult {
  switch (ev.t) {
    case 'plant':
      return doPlant(s, c, ev.plotId, ev.cropId, now)
    case 'harvest':
      return doHarvest(s, c, ev.plotId, now)
    case 'buyPlot':
      return doBuyPlot(s, c, ev.plotId)
    case 'unlockCrop':
      return doUnlockCrop(s, c, ev.cropId)
    case 'swapPreset':
      return doSwapPreset(s, c, ev.plotId, ev.cropId)
    case 'clearCrop':
      return doClearCrop(s, ev.plotId)
    case 'buyUpgrade':
    case 'migrate':
      return reject(s, 'invalid') // 任务 6 实现
  }
}

export { buildIndex }
