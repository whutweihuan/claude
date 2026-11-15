import { describe, expect, it } from 'vitest'
import Decimal from 'break_infinity.js'
import { exportJson, importJson, parseSave, toSaveData } from './save'
import { buildIndex } from '../content'
import { initialState } from './engine'
import type { RunState } from '../types'

const idx = buildIndex()

function normalize(s: RunState) {
  const { coins, totalEarned, ...rest } = s
  return { ...rest, coins: coins.toString(), totalEarned: totalEarned.toString() }
}

describe('toSaveData / parseSave round-trip', () => {
  it('初始局往返后状态相等', () => {
    const s = initialState(idx, 5)
    const out = parseSave(exportJson(s), idx)
    expect(out.kind).toBe('ok')
    if (out.kind !== 'ok') return
    expect(normalize(out.state)).toEqual(normalize(s))
  })

  it('金额在 JSON 文本里是带引号字符串（number 红线）', () => {
    const text = exportJson(initialState(idx, 5))
    expect(/"coins":"15"/.test(text)).toBe(true)
    expect(/"totalEarned":"0"/.test(text)).toBe(true)
  })

  it('科学计数金额往返精度不丢', () => {
    const s = { ...initialState(idx, 5), coins: new Decimal('1e21') }
    const out = parseSave(exportJson(s), idx)
    if (out.kind !== 'ok') throw new Error('parse failed')
    expect(out.state.coins.toString()).toBe('1e+21')
  })

  it('toSaveData 用 now 刷新 lastSeenAt', () => {
    const d = toSaveData(initialState(idx, 5), 12345)
    expect(d.lastSeenAt).toBe(12345)
  })
})

describe('parseSave 失败分支', () => {
  it('null / 空串 → empty', () => {
    expect(parseSave(null, idx).kind).toBe('empty')
    expect(parseSave('', idx).kind).toBe('empty')
  })
  it('坏 JSON → unreadable（调用方须禁写盘，审查重点1）', () => {
    const out = parseSave('{"coins": 15,,,oops', idx)
    expect(out.kind).toBe('unreadable')
  })
  it('JSON 但不是对象 → invalid', () => {
    expect(parseSave('42', idx).kind).toBe('invalid')
    expect(parseSave('null', idx).kind).toBe('invalid')
  })
  it('未来版本 → invalid 且报原因', () => {
    const out = parseSave(JSON.stringify({ schemaVersion: 99 }), idx)
    expect(out.kind).toBe('invalid')
    if (out.kind === 'invalid') expect(out.reason).toContain('版本')
  })
  it('负金额 / 非数字金额 → invalid', () => {
    const base = JSON.parse(exportJson(initialState(idx, 5))) as Record<string, unknown>
    expect(parseSave(JSON.stringify({ ...base, coins: '-3' }), idx).kind).toBe('invalid')
    expect(parseSave(JSON.stringify({ ...base, coins: 'abc' }), idx).kind).toBe('invalid')
    expect(parseSave(JSON.stringify({ ...base, coins: 15 }), idx).kind).toBe('invalid')
  })
})

describe('前向兼容：未知 id 忽略但保留', () => {
  it('未知作物地块 → ok、地块转为空地、原始数据进 foreign 且导出仍在', () => {
    const raw = JSON.parse(exportJson(initialState(idx, 5))) as {
      plots: Record<string, unknown>
    } & Record<string, unknown>
    const p0 = raw['plots'] as Record<string, { cropId: string | null; plantedAt: number | null; growMs: number | null }>
    const g0 = p0['garden:0']!
    g0.cropId = 'future-crop'
    g0.plantedAt = 1
    g0.growMs = 2
    raw['futureTopField'] = { anything: true }
    const out = parseSave(JSON.stringify(raw), idx)
    expect(out.kind).toBe('ok')
    if (out.kind !== 'ok') return
    const plot = out.state.plots['garden:0']
    expect(plot?.cropId).toBeNull()
    expect(plot?.unlocked).toBe(true)
    expect(out.state.foreign['futureTopField']).toEqual({ anything: true })
    const again = exportJson(out.state)
    expect(again).toContain('future-crop')
  })
})

describe('importJson', () => {
  it('复用 parseSave：合法文本 ok，坏文本 invalid/unreadable', () => {
    const good = exportJson(initialState(idx, 7))
    expect(importJson(good, idx).kind).toBe('ok')
    expect(importJson('{oops', idx).kind).toBe('unreadable')
    expect(importJson('{"schemaVersion":99}', idx).kind).toBe('invalid')
  })
})
