import { describe, expect, it } from 'vitest'
import { effectiveGrowMs, isMature, progressOf, stageOf } from './growth'
import type { CropDef, PlotState } from '../types'

function plot(over: Partial<PlotState> = {}): PlotState {
  return {
    id: 'garden:0',
    unlocked: true,
    cropId: 'radish',
    presetCropId: 'radish',
    plantedAt: 1000,
    growMs: 4000,
    ...over
  }
}

const radish: CropDef = {
  id: 'radish',
  mapId: 'garden',
  name: '白萝卜',
  seedCost: '1',
  yieldCoins: '12',
  growTimeMs: 5000,
  unlockCost: null,
  sprite: { body: '#fff', accent: '#fff', leaf: '#fff', form: 'stem' }
}

describe('progressOf', () => {
  it('半程 = 0.5', () => {
    expect(progressOf(plot({ plantedAt: 0, growMs: 1000 }), 500)).toBe(0.5)
  })
  it('到点钳制为 1 且 isMature', () => {
    const p = plot({ plantedAt: 0, growMs: 1000 })
    expect(progressOf(p, 1000)).toBe(1)
    expect(progressOf(p, 9_999_999)).toBe(1)
    expect(isMature(p, 1000)).toBe(true)
    expect(isMature(p, 999)).toBe(false)
  })
  it('时钟回拨（now < plantedAt）→ 0，不抛错', () => {
    expect(progressOf(plot({ plantedAt: 5000, growMs: 1000 }), 4000)).toBe(0)
    expect(isMature(plot({ plantedAt: 5000, growMs: 1000 }), 4000)).toBe(false)
  })
  it('空地 / 未解锁 / 缺失快照 → 0', () => {
    expect(progressOf(plot({ cropId: null, plantedAt: null, growMs: null }), 9999)).toBe(0)
    expect(progressOf(plot({ unlocked: false }), 9999)).toBe(0)
    expect(progressOf(plot({ growMs: null }), 9999)).toBe(0)
  })
  it('growMs 是种植时刻快照：升 speed 级不影响本轮进度计算', () => {
    // 种下时快照 5000ms，哪怕作物现在能以 2500ms 成熟，本轮仍按快照走
    const p = plot({ plantedAt: 0, growMs: 5000 })
    expect(progressOf(p, 2500)).toBe(0.5)
  })
})

describe('effectiveGrowMs', () => {
  it('speed=0 原速；每级 +10%；10 级封顶（÷2）；越界钳制', () => {
    expect(effectiveGrowMs(radish, 0)).toBe(5000)
    expect(effectiveGrowMs(radish, 5)).toBeCloseTo(5000 / 1.5, 6)
    expect(effectiveGrowMs(radish, 10)).toBe(2500)
    expect(effectiveGrowMs(radish, 99)).toBe(2500)
    expect(effectiveGrowMs(radish, -3)).toBe(5000)
  })
})

describe('stageOf', () => {
  it('阈值 0.25 / 0.6 / 0.95', () => {
    expect(stageOf(0)).toBe(0)
    expect(stageOf(0.24)).toBe(0)
    expect(stageOf(0.25)).toBe(1)
    expect(stageOf(0.59)).toBe(1)
    expect(stageOf(0.6)).toBe(2)
    expect(stageOf(0.94)).toBe(2)
    expect(stageOf(0.95)).toBe(3)
    expect(stageOf(1)).toBe(3)
  })
})
