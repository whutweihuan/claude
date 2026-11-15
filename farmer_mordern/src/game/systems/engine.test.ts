import { describe, expect, it } from 'vitest'
import Decimal from 'break_infinity.js'
import { applyEvent, initialState, plotPrice, soilMult } from './engine'
import { buildIndex, plotKey } from '../content'
import type { GameEvent, RunState } from '../types'

const idx = buildIndex()

function ok(s: RunState, ev: GameEvent, now = 0): RunState {
  const r = applyEvent(s, ev, idx, now)
  if (!r.ok) throw new Error(`事件 ${ev.t} 被拒绝: ${r.reason}`)
  return r.state
}

function fresh(coins: Decimal = new Decimal(15)): RunState {
  const s = initialState(idx, 0)
  return { ...s, coins }
}

describe('initialState', () => {
  it('菜园解锁、赠地开垦、自动作物可用、初始资金 15', () => {
    const s = initialState(idx, 1000)
    expect(s.maps['garden']?.unlocked).toBe(true)
    expect(s.maps['greenhouse']?.unlocked).toBe(false)
    expect(s.plots[plotKey('garden', 0)]?.unlocked).toBe(true)
    expect(s.plots[plotKey('garden', 1)]?.unlocked).toBe(true)
    expect(s.plots[plotKey('garden', 2)]?.unlocked).toBe(false)
    expect(s.cropsUnlocked['radish']).toBe(true)
    expect(s.cropsUnlocked['pepper']).toBeFalsy()
    expect(s.coins.eq(15)).toBe(true)
    expect(s.lastSeenAt).toBe(1000)
    expect(s.foreign).toEqual({})
  })
})

describe('plant / harvest', () => {
  it('种植扣 seedCost 并写入 growMs 快照与预设', () => {
    const s = ok(fresh(), { t: 'plant', plotId: plotKey('garden', 0), cropId: 'radish' }, 7)
    expect(s.coins.eq(14)).toBe(true)
    const p = s.plots[plotKey('garden', 0)]
    expect(p?.cropId).toBe('radish')
    expect(p?.presetCropId).toBe('radish')
    expect(p?.plantedAt).toBe(7)
    expect(p?.growMs).toBe(5000)
  })
  it('余额不足 → noCoins 且 state 引用不变', () => {
    const s = fresh()
    const r = applyEvent(s, { t: 'plant', plotId: plotKey('garden', 0), cropId: 'tomato' }, idx, 0)
    expect(r.ok).toBe(false)
    expect(r.reason).toBe('noCoins')
    expect(r.state).toBe(s)
  })
  it('种在未开垦/不存在/占用的地块', () => {
    const s = fresh()
    expect(applyEvent(s, { t: 'plant', plotId: plotKey('garden', 5), cropId: 'radish' }, idx, 0).reason).toBe('locked')
    expect(applyEvent(s, { t: 'plant', plotId: 'nope:9', cropId: 'radish' }, idx, 0).reason).toBe('invalid')
    const grown = ok(s, { t: 'plant', plotId: plotKey('garden', 0), cropId: 'radish' })
    expect(applyEvent(grown, { t: 'plant', plotId: plotKey('garden', 0), cropId: 'radish' }, idx, 1).reason).toBe('invalid')
  })
  it('种未解锁作物 → locked', () => {
    const r = applyEvent(fresh(), { t: 'plant', plotId: plotKey('garden', 0), cropId: 'pumpkin' }, idx, 0)
    expect(r.reason).toBe('locked')
  })
  it('未熟不可收；成熟收获 = yield × 沃土倍率，地块清空但保留预设', () => {
    const s0 = ok(fresh(), { t: 'plant', plotId: plotKey('garden', 0), cropId: 'radish' })
    const early = applyEvent(s0, { t: 'harvest', plotId: plotKey('garden', 0) }, idx, 4999)
    expect(early.reason).toBe('invalid')
    expect(early.state).toBe(s0)
    const s1 = ok(s0, { t: 'harvest', plotId: plotKey('garden', 0) }, 5000)
    expect(s1.coins.eq(14 + 12)).toBe(true)
    expect(s1.totalEarned.eq(12)).toBe(true)
    const p = s1.plots[plotKey('garden', 0)]
    expect(p?.cropId).toBeNull()
    expect(p?.plantedAt).toBeNull()
    expect(p?.growMs).toBeNull()
    expect(p?.presetCropId).toBe('radish')
  })
  it('沃土 1 级 → 收获 ×1.25，totalEarned 只随收获增长', () => {
    const s = fresh()
    const withSoil: RunState = { ...s, upgrades: { 'soil:garden': 1 } }
    expect(soilMult(withSoil, idx, 'garden')).toBeCloseTo(1.25, 10)
    const planted = ok(withSoil, { t: 'plant', plotId: plotKey('garden', 0), cropId: 'radish' })
    expect(planted.totalEarned.eq(0)).toBe(true)
    const harvested = ok(planted, { t: 'harvest', plotId: plotKey('garden', 0) }, 5000)
    expect(harvested.coins.eq(planted.coins.plus(15))).toBe(true)
    expect(harvested.totalEarned.eq(15)).toBe(true)
  })
})

describe('buyPlot / unlockCrop', () => {
  it('地块价按 1.9^步 递增，从可购第一块起算', () => {
    const map = idx.mapById['garden']
    if (!map) throw new Error('no garden')
    expect(plotPrice(map, 2).eq(25)).toBe(true)
    expect(plotPrice(map, 3).eq(new Decimal(25).mul(1.9))).toBe(true)
  })
  it('顺序购买扣款解锁；跳号 notSequenced；越界 invalid；锁图 locked', () => {
    const poor = applyEvent(fresh(), { t: 'buyPlot', plotId: plotKey('garden', 2) }, idx, 0)
    expect(poor.reason).toBe('noCoins')
    const rich = fresh(new Decimal(1e9))
    const s1 = ok(rich, { t: 'buyPlot', plotId: plotKey('garden', 2) })
    expect(s1.plots[plotKey('garden', 2)]?.unlocked).toBe(true)
    expect(s1.coins.eq(new Decimal(1e9).minus(25))).toBe(true)
    expect(applyEvent(s1, { t: 'buyPlot', plotId: plotKey('garden', 4) }, idx, 0).reason).toBe('notSequenced')
    expect(applyEvent(s1, { t: 'buyPlot', plotId: plotKey('garden', 99) }, idx, 0).reason).toBe('invalid')
    expect(applyEvent(s1, { t: 'buyPlot', plotId: plotKey('greenhouse', 2) }, idx, 0).reason).toBe('locked')
    expect(applyEvent(s1, { t: 'buyPlot', plotId: plotKey('garden', 2) }, idx, 0).reason).toBe('alreadyOwned')
  })
  it('作物解锁一次性扣费；重复 alreadyOwned；自动作物不可购', () => {
    const s = fresh(new Decimal('1e6'))
    const s1 = ok(s, { t: 'unlockCrop', cropId: 'pepper' })
    expect(s1.coins.eq(new Decimal('1e6').minus('6e4'))).toBe(true)
    expect(s1.cropsUnlocked['pepper']).toBe(true)
    expect(applyEvent(s1, { t: 'unlockCrop', cropId: 'pepper' }, idx, 0).reason).toBe('alreadyOwned')
    expect(applyEvent(s, { t: 'unlockCrop', cropId: 'radish' }, idx, 0).reason).toBe('alreadyOwned')
    expect(applyEvent(s, { t: 'unlockCrop', cropId: 'peach' }, idx, 0).reason).toBe('locked')
  })
})

describe('swapPreset / clearCrop', () => {
  it('换预设不打断当前轮', () => {
    const s = ok(fresh(), { t: 'plant', plotId: plotKey('garden', 0), cropId: 'radish' })
    const s1 = ok(s, { t: 'swapPreset', plotId: plotKey('garden', 0), cropId: 'bokchoy' }, 100)
    const p = s1.plots[plotKey('garden', 0)]
    expect(p?.presetCropId).toBe('bokchoy')
    expect(p?.cropId).toBe('radish')
    expect(p?.plantedAt).toBe(0)
  })
  it('换预设要求作物同图且已解锁', () => {
    const s = fresh()
    expect(applyEvent(s, { t: 'swapPreset', plotId: plotKey('garden', 0), cropId: 'strawberry' }, idx, 0).reason).toBe('invalid')
    expect(applyEvent(s, { t: 'swapPreset', plotId: plotKey('garden', 0), cropId: 'pumpkin' }, idx, 0).reason).toBe('locked')
  })
  it('清茬铲掉生长中作物，不扣款不退款；空地 invalid', () => {
    const s = ok(fresh(), { t: 'plant', plotId: plotKey('garden', 0), cropId: 'radish' })
    const cleared = ok(s, { t: 'clearCrop', plotId: plotKey('garden', 0) }, 100)
    const p = cleared.plots[plotKey('garden', 0)]
    expect(p?.cropId).toBeNull()
    expect(p?.plantedAt).toBeNull()
    expect(p?.growMs).toBeNull()
    expect(p?.presetCropId).toBe('radish')
    expect(cleared.coins.eq(s.coins)).toBe(true)
    expect(applyEvent(cleared, { t: 'clearCrop', plotId: plotKey('garden', 0) }, idx, 0).reason).toBe('invalid')
  })
})
