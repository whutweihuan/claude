import { describe, expect, it } from 'vitest'
import Decimal from 'break_infinity.js'
import { autoTick, offlineCapMs, settleOffline } from './offline'
import { buildIndex, plotKey } from '../content'
import { effectiveGrowMs } from './growth'
import { initialState } from './engine'
import type { CropDef, RunState } from '../types'

const idx = buildIndex()

function crop(id: string): CropDef {
  const c = idx.cropById[id]
  if (!c) throw new Error(`no crop ${id}`)
  return c
}

interface PlotCfg {
  cropId: string | null
  preset?: string
  plantedAt?: number
  speedLvl?: number
}

/** 构造中间态：给定图与地块配置，手动（非事件）设置，用于离线/在线对照 */
function midState(coins: Decimal, gardenUpgrades: Record<string, number>, plots: Record<number, PlotCfg>): RunState {
  const s = initialState(idx, 0)
  s.coins = coins
  for (const [k, v] of Object.entries(gardenUpgrades)) s.upgrades[k] = v
  for (const [nStr, cfg] of Object.entries(plots)) {
    const p = s.plots[plotKey('garden', Number(nStr))]
    if (!p) continue
    p.unlocked = true
    if (cfg.cropId) {
      const speedLvl = cfg.speedLvl ?? gardenUpgrades['speed:garden'] ?? 0
      p.cropId = cfg.cropId
      p.presetCropId = cfg.preset ?? cfg.cropId
      p.plantedAt = cfg.plantedAt ?? 0
      p.growMs = effectiveGrowMs(crop(cfg.cropId), speedLvl)
    }
  }
  return s
}

const HOUR = 3_600_000

describe('offlineCapMs', () => {
  it('灯 0/1/2 级 = 8h/24h/72h，越界钳制', () => {
    const s = initialState(idx, 0)
    expect(offlineCapMs(s)).toBe(8 * HOUR)
    expect(offlineCapMs({ ...s, upgrades: { 'offlineLamp:global': 1 } })).toBe(24 * HOUR)
    expect(offlineCapMs({ ...s, upgrades: { 'offlineLamp:global': 2 } })).toBe(72 * HOUR)
    expect(offlineCapMs({ ...s, upgrades: { 'offlineLamp:global': 9 } })).toBe(72 * HOUR)
  })
})

describe('settleOffline 三档自动化', () => {
  it('全手动：成熟停在地里，不收不种', () => {
    const s = midState(new Decimal(100), {}, { 0: { cropId: 'radish' } })
    const { state, report } = settleOffline(s, idx, 1000, 1000 + HOUR)
    expect(state.coins.eq(100)).toBe(true)
    expect(state.plots[plotKey('garden', 0)]?.cropId).toBe('radish')
    expect(report.gained.eq(0)).toBe(true)
    expect(Object.keys(report.perMap).length).toBe(0)
  })
  it('只买自动收获：熟收 1 次后停，二次结算无新增', () => {
    const s = midState(new Decimal(100), { 'autoHarvest:garden': 1 }, { 0: { cropId: 'radish' } })
    const r1 = settleOffline(s, idx, 0, HOUR)
    expect(r1.state.plots[plotKey('garden', 0)]?.cropId).toBeNull()
    expect(r1.state.coins.eq(112)).toBe(true)
    expect(r1.report.perMap['garden']?.cycles).toBe(1)
    const r2 = settleOffline(r1.state, idx, HOUR, 2 * HOUR)
    expect(r2.state.coins.eq(112)).toBe(true)
  })
  it('收获+补种：整窗按预设作物轮转，余数落回生长进度', () => {
    const s = midState(new Decimal('1e30'), { 'autoHarvest:garden': 1, 'autoReplant:garden': 1 }, {
      0: { cropId: 'radish', preset: 'bokchoy' }
    })
    const { state } = settleOffline(s, idx, 3000, 3000 + HOUR)
    const p = state.plots[plotKey('garden', 0)]
    expect(p?.cropId).toBe('bokchoy') // 预设作物接管轮转
    if (!p?.plantedAt || !p?.growMs) throw new Error('bad plot')
    expect(p.growMs).toBe(effectiveGrowMs(crop('bokchoy'), 0))
    expect(p.plantedAt).toBeLessThanOrEqual(3000 + HOUR)
    expect(p.plantedAt + p.growMs).toBeGreaterThan(3000 + HOUR) // 最后一轮还在长
  })
  it('空地不会自种：预设只服务"收后补种"', () => {
    const s = midState(new Decimal('1e30'), { 'autoHarvest:garden': 1, 'autoReplant:garden': 1 }, {
      1: { cropId: null }
    })
    s.plots[plotKey('garden', 1)]!.presetCropId = 'bokchoy'
    const { state } = settleOffline(s, idx, 0, HOUR)
    expect(state.plots[plotKey('garden', 1)]?.cropId).toBeNull()
    expect(state.coins.eq(1e30)).toBe(true)
  })
  it('审查重点5：补种草费不起 → 停在已收未种、余额非负；手动补种后自动化恢复', () => {
    const s = midState(new Decimal(5), {}, { 0: { cropId: 'radish', preset: 'bokchoy' } })
    s.upgrades['autoHarvest:garden'] = 1
    s.upgrades['autoReplant:garden'] = 1
    const { state } = settleOffline(s, idx, 0, HOUR)
    const p = state.plots[plotKey('garden', 0)]
    expect(state.coins.eq(17)).toBe(true) // 收 12 后 17 < 30 种不起 bokchoy
    expect(p?.cropId).toBeNull()
    expect(p?.presetCropId).toBe('bokchoy')
  })
})

describe('窗口与防御', () => {
  it('elapsed=0 / 负值（时钟回拨）：不结算，lastSeenAt 刷新', () => {
    const s = midState(new Decimal(100), { 'autoHarvest:garden': 1 }, { 0: { cropId: 'radish' } })
    const same = settleOffline(s, idx, 5000, 5000)
    expect(same.state.coins.eq(100)).toBe(true)
    expect(same.state.lastSeenAt).toBe(5000)
    const back = settleOffline(s, idx, 9000, 5000)
    expect(back.state.coins.eq(100)).toBe(true)
    expect(back.report.elapsedMs).toBe(0)
  })
  it('审查重点3：3650 天离线被上限钳制，有界完成且无 NaN/Infinity', () => {
    const s = midState(new Decimal('1e30'), { 'autoHarvest:garden': 1, 'autoReplant:garden': 1 }, {
      0: { cropId: 'radish' }, 1: { cropId: 'bokchoy' }, 2: { cropId: 'sunflower' }
    })
    const now = 5_600_000
    const { state, report } = settleOffline(s, idx, now - 3650 * 24 * HOUR, now)
    expect(report.elapsedMs).toBe(8 * HOUR)
    expect(Number.isFinite(Number(state.coins.toString()))).toBe(true)
    expect(Number.isFinite(Number(state.totalEarned.toString()))).toBe(true)
    expect(report.perMap['garden']!.cycles).toBeGreaterThan(0)
  })
  it('未解锁图的锁定地块不参与结算', () => {
    const s = midState(new Decimal('1e30'), { 'autoHarvest:garden': 1, 'autoReplant:garden': 1 }, {})
    const p = s.plots[plotKey('greenhouse', 0)]!
    p.cropId = 'orchid'
    p.presetCropId = 'orchid'
    p.plantedAt = 0
    p.growMs = 1000
    const { state } = settleOffline(s, idx, 0, HOUR)
    expect(state.plots[plotKey('greenhouse', 0)]?.cropId).toBe('orchid')
    expect(state.coins.eq(1e30)).toBe(true)
  })
})

describe('在线/离线一致性（§9 核心保障）', () => {
  it('混合四地块全自动：2h 窗口 500ms 心跳步进 == 一次离线结算（逐位相等）', () => {
    const upgrades = {
      'soil:garden': 1, 'speed:garden': 2, 'autoHarvest:garden': 1, 'autoReplant:garden': 1
    }
    const make = () => midState(new Decimal('1e30'), upgrades, {
      0: { cropId: 'radish' }, 1: { cropId: 'bokchoy' }, 2: { cropId: 'sunflower' },
      3: { cropId: 'tomato' }
    })
    const lastSeen = 3000
    const to = 3000 + 2 * HOUR
    const s0 = make()
    s0.lastSeenAt = lastSeen
    const off = settleOffline(s0, idx, lastSeen, to)

    let online = make()
    online.lastSeenAt = lastSeen
    for (let t = lastSeen + 500; t <= to; t += 500) online = autoTick(online, idx, t)

    expect(online.coins.toString()).toBe(off.state.coins.toString())
    expect(online.totalEarned.toString()).toBe(off.state.totalEarned.toString())
    for (const key of Object.keys(online.plots)) {
      expect(online.plots[key]).toEqual(off.state.plots[key])
    }
    // 报告合计 = 总收益增量（比 coins 差更抗大数精度抹平）
    expect(off.report.gained.toString()).toBe(off.state.totalEarned.minus(s0.totalEarned).toString())
    expect(off.report.perMap['garden']!.cycles).toBeGreaterThan(500)
  })
})
