import { Decimal } from '../types'
import type { ApplyResult, CropDef, GameEvent, MapDef, RunState } from '../types'
import { buildIndex, plotKey, plotPrice, upgradeCost, upgradeKey } from '../content'
import type { ContentIndex } from '../content'
import { effectiveGrowMs, isMature } from './growth'

export { plotPrice }

/** 金额记账统一原则（§4.5）：任何种植（含未来的自动补种）一律扣 seedCost，任何收获一律加 yieldCoins。 */

export interface PlotRef {
  mapId: string
  n: number
}

export function parsePlotId(id: string): PlotRef | null {
  const i = id.lastIndexOf(':')
  if (i <= 0) return null
  const n = Number(id.slice(i + 1))
  if (!Number.isInteger(n) || n < 0) return null
  return { mapId: id.slice(0, i), n }
}

export function soilMult(s: RunState, _c: ContentIndex, mapId: string): number {
  return 1 + 0.25 * (s.upgrades[upgradeKey('soil', mapId)] ?? 0)
}

/**
 * 收获金额 = yield × (100 + 25×soil级) ÷ 100。
 * 全程 Decimal 整数基点运算，避免 1.5 之类的浮点乘数引入 ULP 漂移
 * （在线/离线一致性测试要求两条路径逐位相等）。
 */
export function harvestGain(s: RunState, _c: ContentIndex, mapId: string, crop: CropDef): Decimal {
  const lvl = s.upgrades[upgradeKey('soil', mapId)] ?? 0
  return new Decimal(crop.yieldCoins).mul(100 + 25 * lvl).div(100)
}

function speedLevel(s: RunState, mapId: string): number {
  return s.upgrades[upgradeKey('speed', mapId)] ?? 0
}

/** @internal 供 offline.ts 复用同一状态拷贝语义 */
export function cloneState(s: RunState): RunState {
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
  const gain = harvestGain(s, c, ref.mapId, crop)
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
      return doBuyUpgrade(s, c, ev.defId, ev.scope)
    case 'migrate':
      return doMigrate(s, c, ev.mapId)
  }
}

function doBuyUpgrade(s: RunState, c: ContentIndex, defId: string, scope: string): ApplyResult {
  const def = c.upgradeById[defId]
  if (!def) return reject(s, 'invalid')
  const effScope = def.scope === 'global' ? 'global' : scope
  let mapDef: MapDef | null = null
  if (def.scope === 'map') {
    mapDef = c.mapById[effScope] ?? null
    if (!mapDef) return reject(s, 'invalid')
    if (!s.maps[mapDef.id]?.unlocked) return reject(s, 'locked')
  }
  const key = upgradeKey(def.id, effScope)
  const level = s.upgrades[key] ?? 0
  if (level >= def.maxLevel) return reject(s, 'maxLevel')
  if (def.kind === 'autoReplant' && (s.upgrades[upgradeKey('autoHarvest', effScope)] ?? 0) < 1) {
    return reject(s, 'prereq')
  }
  const cost = upgradeCost(def, mapDef, level)
  if (s.coins.lt(cost)) return reject(s, 'noCoins')
  const next = cloneState(s)
  next.coins = next.coins.minus(cost)
  next.upgrades[key] = level + 1
  return { ok: true, state: next }
}

/** 目标图 = 当前已解锁最高图的下一张；前图全开垦；支付前图迁徙费（§4.2） */
export function canMigrate(s: RunState, c: ContentIndex, mapId: string): { ok: boolean; missing: 'plots' | 'coins' | 'prereq' } {
  const target = c.mapById[mapId]
  if (!target) return { ok: false, missing: 'prereq' }
  if (s.maps[mapId]?.unlocked) return { ok: false, missing: 'prereq' }
  const prev = c.maps[target.order - 2]
  if (!prev || !s.maps[prev.id]?.unlocked) return { ok: false, missing: 'prereq' }
  const allOpen = Array.from({ length: prev.plotCount }, (_, n) => s.plots[plotKey(prev.id, n)]?.unlocked === true).every(Boolean)
  if (!allOpen) return { ok: false, missing: 'plots' }
  if (prev.migrationCost === null || s.coins.lt(prev.migrationCost)) return { ok: false, missing: 'coins' }
  return { ok: true, missing: 'coins' }
}

function doMigrate(s: RunState, c: ContentIndex, mapId: string): ApplyResult {
  const target = c.mapById[mapId]
  if (!target) return reject(s, 'invalid')
  if (s.maps[mapId]?.unlocked) return reject(s, 'alreadyOwned')
  const prev = c.maps[target.order - 2]
  if (!prev) return reject(s, 'invalid')
  if (!s.maps[prev.id]?.unlocked) return reject(s, 'invalid') // 不允许跳图
  for (let n = 0; n < prev.plotCount; n++) {
    if (!s.plots[plotKey(prev.id, n)]?.unlocked) return reject(s, 'notSequenced')
  }
  if (prev.migrationCost === null) return reject(s, 'invalid')
  const cost = new Decimal(prev.migrationCost)
  if (s.coins.lt(cost)) return reject(s, 'noCoins')
  const next = cloneState(s)
  next.coins = next.coins.minus(cost)
  const ms = next.maps[mapId]
  if (ms) ms.unlocked = true
  for (let n = 0; n < target.freePlots; n++) {
    const p = next.plots[plotKey(mapId, n)]
    if (p) p.unlocked = true
  }
  autoUnlockCrops(next, c, mapId)
  return { ok: true, state: next }
}

export { buildIndex }
