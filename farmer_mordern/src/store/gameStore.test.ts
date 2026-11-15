import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import Decimal from 'break_infinity.js'
import { SAVE_KEY, createGameStore, type StorageLike } from './gameStore'
import { buildIndex, plotKey } from '../game/content'
import { initialState } from '../game/systems/engine'
import { exportJson } from '../game/systems/save'
import type { RunState } from '../game/types'

const idx = buildIndex()

function fakeBackend(initial: Record<string, string> = {}) {
  const m = new Map<string, string>(Object.entries(initial))
  const b: StorageLike & { map: Map<string, string>; setCalls: number } = {
    map: m,
    setCalls: 0,
    getItem: (k) => (m.has(k) ? (m.get(k) as string) : null),
    setItem: (k, v) => {
      b.setCalls++
      m.set(k, v)
    },
    removeItem: (k) => {
      m.delete(k)
    }
  }
  return b
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(20_000)
})
afterEach(() => {
  vi.useRealTimers()
})

describe('gameStore 启动', () => {
  it('空档 → 初始局并落盘一次', () => {
    const b = fakeBackend()
    const { useGame, flags } = createGameStore(b)
    expect(useGame.getState().game.coins.eq(15)).toBe(true)
    expect(useGame.getState().ui.loadError).toBeNull()
    expect(flags.writes).toBe(1)
    expect(b.map.has(SAVE_KEY)).toBe(true)
  })
  it('合法档 + 离线时长 → 报告非空且入账；同档重启不重复计', () => {
    const planted: RunState = { ...initialState(idx, 0), coins: new Decimal(100) }
    const p = planted.plots[plotKey('garden', 0)]!
    p.cropId = 'radish'
    p.presetCropId = 'radish'
    p.plantedAt = 0
    p.growMs = 5000
    p.unlocked = true
    planted.upgrades['autoHarvest:garden'] = 1
    planted.upgrades['autoReplant:garden'] = 1
    const raw = exportJson(planted)
    const b = fakeBackend({ [SAVE_KEY]: raw })
    const first = createGameStore(b)
    const st1 = first.useGame.getState()
    expect(st1.ui.report).not.toBeNull()
    expect(st1.game.coins.gt(100)).toBe(true)
    const coinsAfter = st1.game.coins.toString()

    const second = createGameStore(b) // 同一存储再启动（lastSeenAt 已刷新为 20000）
    expect(second.useGame.getState().game.coins.toString()).toBe(coinsAfter)
    expect(second.useGame.getState().ui.report).toBeNull() // 无新增收益不弹报告
  })
  it('坏 JSON → 只读模式：loadError 置位、内存可玩、原文不被覆盖', () => {
    const broken = '{"coins": 15,,,oops'
    const b = fakeBackend({ [SAVE_KEY]: broken })
    const { useGame, flags } = createGameStore(b)
    expect(useGame.getState().ui.loadError).toContain('只读')
    const ok = useGame.getState().dispatch({ t: 'plant', plotId: plotKey('garden', 0), cropId: 'radish' })
    expect(ok).toBe(true)
    expect(useGame.getState().game.plots[plotKey('garden', 0)]?.cropId).toBe('radish')
    expect(flags.writes).toBe(0)
    expect(b.getItem(SAVE_KEY)).toBe(broken)
  })
  it('默认静音', () => {
    const { useGame } = createGameStore(fakeBackend())
    expect(useGame.getState().ui.muted).toBe(true)
  })
})

describe('gameStore 心跳与节流', () => {
  it('12 次连续变更 → 写盘 ≤2 次；1 秒后 pending 落盘', () => {
    const b = fakeBackend()
    const { useGame, flags } = createGameStore(b)
    const w0 = flags.writes
    for (let i = 0; i < 6; i++) {
      vi.setSystemTime(20_000 + i)
      useGame.getState().dispatch({ t: 'plant', plotId: plotKey('garden', 0), cropId: 'radish' })
      useGame.getState().dispatch({ t: 'clearCrop', plotId: plotKey('garden', 0) })
    }
    expect(flags.writes - w0).toBeLessThanOrEqual(2)
    vi.setSystemTime(21_500)
    vi.advanceTimersByTime(2000)
    expect(flags.writes - w0).toBeLessThanOrEqual(2)
    expect(b.setCalls).toBeGreaterThan(0)
  })
  it('tick 驱动自动化：成熟作物被自动收掉', () => {
    const b = fakeBackend()
    const { useGame } = createGameStore(b)
    const st = useGame.getState()
    st.dispatch({ t: 'buyPlot', plotId: plotKey('garden', 2) }) // 没钱，仅走一遍拒绝路径
    st.dispatch({ t: 'plant', plotId: plotKey('garden', 0), cropId: 'radish' })
    useGame.setState((s) => {
      s.game.upgrades['autoHarvest:garden'] = 1
      return s
    })
    useGame.getState().tick(26_000) // 20000 种下（5000ms 快照）→ 25000 熟 → 窗口内自动收
    expect(useGame.getState().game.coins.eq(15 - 1 + 12)).toBe(true)
    expect(useGame.getState().game.lastSeenAt).toBe(26_000)
  })
})

describe('导入/导出与重置', () => {
  it('importSave：合法文本替换状态并解锁写盘；坏文本拒绝且现档不动', () => {
    const b = fakeBackend({ [SAVE_KEY]: 'garbage{{{' })
    const { useGame, flags } = createGameStore(b)
    expect(flags.readOnly).toBe(true)
    const good = exportJson(initialState(idx, 9))
    const r = useGame.getState().importSave(good)
    expect(r.ok).toBe(true)
    expect(flags.readOnly).toBe(false)
    expect(useGame.getState().game.startedAt).toBe(9)
    const bad = useGame.getState().importSave('{"schemaVersion":99}')
    expect(bad.ok).toBe(false)
  })
  it('hardReset 清档并开新局', () => {
    const b = fakeBackend({ [SAVE_KEY]: 'x' })
    const { useGame } = createGameStore(b)
    useGame.getState().hardReset()
    expect(b.map.has(SAVE_KEY)).toBe(false)
    expect(useGame.getState().game.coins.eq(15)).toBe(true)
  })
})
