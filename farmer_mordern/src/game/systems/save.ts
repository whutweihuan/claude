import Decimal from 'break_infinity.js'
import type { ContentIndex } from '../content'
import type { MapState, PlotState, RunState } from '../types'
import { CURRENT_SCHEMA_VERSION, SaveError, migrateSave } from './migrate'

export interface SaveData {
  schemaVersion: number
  coins: string
  totalEarned: string
  plots: Record<string, PlotState>
  maps: Record<string, MapState>
  cropsUnlocked: Record<string, boolean>
  upgrades: Record<string, number>
  lastSeenAt: number
  startedAt: number
  foreign: Record<string, unknown>
}

export type LoadOutcome =
  | { kind: 'empty' }
  | { kind: 'ok'; state: RunState }
  | { kind: 'unreadable' }
  | { kind: 'invalid'; reason: string }

const DEC_RE = /^\d+(\.\d+)?(e\+\d+)?$/i

export function toSaveData(s: RunState, now: number): SaveData {
  return {
    schemaVersion: CURRENT_SCHEMA_VERSION,
    coins: s.coins.toString(),
    totalEarned: s.totalEarned.toString(),
    plots: s.plots,
    maps: s.maps,
    cropsUnlocked: s.cropsUnlocked,
    upgrades: s.upgrades,
    lastSeenAt: now,
    startedAt: s.startedAt,
    foreign: s.foreign
  }
}

export function exportJson(s: RunState): string {
  return JSON.stringify(toSaveData(s, s.lastSeenAt))
}

function invalid(reason: string): LoadOutcome {
  return { kind: 'invalid', reason }
}

function asDecimalString(v: unknown, field: string): Decimal | string {
  if (typeof v !== 'string' || !DEC_RE.test(v)) return `${field} 必须是十进制金额字符串`
  let d: Decimal
  try {
    d = new Decimal(v)
  } catch {
    return `${field} 无法解析为 Decimal`
  }
  if (!Number.isFinite(Number(d.toString())) || d.lt(0)) return `${field} 非有限或非负`
  return d
}

function isFiniteNonNeg(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v) && v >= 0
}

interface EntryResult {
  plot: PlotState | null
  stash?: unknown
}

function parsePlotEntry(key: string, v: unknown, c: ContentIndex): EntryResult {
  const i = key.lastIndexOf(':')
  if (i <= 0) return { plot: null, stash: v }
  const mapId = key.slice(0, i)
  const n = Number(key.slice(i + 1))
  const map = c.mapById[mapId]
  if (!map || !Number.isInteger(n) || n < 0 || n >= map.plotCount) return { plot: null, stash: v }
  if (typeof v !== 'object' || v === null) return { plot: null, stash: v }
  const e = v as Record<string, unknown>
  if (typeof e['unlocked'] !== 'boolean') return { plot: null, stash: v }
  const cropKnown = (x: unknown): boolean => x === null || (typeof x === 'string' && x in c.cropById)
  const plantedOk = e['plantedAt'] === null || isFiniteNonNeg(e['plantedAt'])
  const growOk = e['growMs'] === null || (typeof e['growMs'] === 'number' && Number.isFinite(e['growMs']) && e['growMs'] > 0)
  if (!plantedOk || !growOk || (typeof e['plantedAt'] === 'number' && typeof e['growMs'] !== 'number')) {
    return { plot: null, stash: v }
  }
  const base: PlotState = {
    id: key,
    unlocked: e['unlocked'],
    cropId: null,
    presetCropId: null,
    plantedAt: null,
    growMs: null
  }
  if (!cropKnown(e['cropId']) || !cropKnown(e['presetCropId'])) {
    // 未知作物：地块转空地继续玩，生长数据弃用，原始数据进 foreign 保留（§5 前向兼容）
    return { plot: base, stash: v }
  }
  return {
    plot: {
      ...base,
      cropId: (e['cropId'] as string | null) ?? null,
      presetCropId: (e['presetCropId'] as string | null) ?? null,
      plantedAt: (e['plantedAt'] as number | null) ?? null,
      growMs: (e['growMs'] as number | null) ?? null
    }
  }
}

export function parseSave(raw: string | null, c: ContentIndex): LoadOutcome {
  if (raw === null || raw.trim() === '') return { kind: 'empty' }
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    return { kind: 'unreadable' }
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    return invalid('存档不是 JSON 对象')
  }
  let migrated: Record<string, unknown>
  try {
    migrated = migrateSave(parsed as Record<string, unknown>)
  } catch (e) {
    if (e instanceof SaveError) return invalid(e.message)
    return invalid('迁移失败')
  }
  const coins = asDecimalString(migrated['coins'], 'coins')
  if (typeof coins === 'string') return invalid(coins)
  const totalEarned = asDecimalString(migrated['totalEarned'], 'totalEarned')
  if (typeof totalEarned === 'string') return invalid(totalEarned)
  if (!isFiniteNonNeg(migrated['lastSeenAt']) || !isFiniteNonNeg(migrated['startedAt'])) {
    return invalid('时间字段非法')
  }
  const foreign: Record<string, unknown> =
    typeof migrated['foreign'] === 'object' && migrated['foreign'] !== null && !Array.isArray(migrated['foreign'])
      ? { ...(migrated['foreign'] as Record<string, unknown>) }
      : {}
  // 未识别的顶层字段一律进 foreign（前向兼容）
  const knownTop = new Set([
    'schemaVersion', 'coins', 'totalEarned', 'plots', 'maps',
    'cropsUnlocked', 'upgrades', 'lastSeenAt', 'startedAt', 'foreign'
  ])
  for (const k of Object.keys(migrated)) {
    if (!knownTop.has(k) && !(k in foreign)) foreign[k] = migrated[k]
  }

  const plots: RunState['plots'] = {}
  const rawPlots = migrated['plots']
  if (typeof rawPlots === 'object' && rawPlots !== null && !Array.isArray(rawPlots)) {
    const stash: Record<string, unknown> = {}
    for (const [key, v] of Object.entries(rawPlots as Record<string, unknown>)) {
      const { plot, stash: bad } = parsePlotEntry(key, v, c)
      if (bad !== undefined) stash[key] = bad
      if (plot) plots[key] = plot
    }
    if (Object.keys(stash).length > 0) {
      const prev = (foreign['plots'] as Record<string, unknown> | undefined) ?? {}
      foreign['plots'] = { ...prev, ...stash }
    }
  }

  const maps: RunState['maps'] = {}
  for (const m of c.maps) maps[m.id] = { unlocked: false }
  const rawMaps = migrated['maps']
  if (typeof rawMaps === 'object' && rawMaps !== null && !Array.isArray(rawMaps)) {
    const stash: Record<string, unknown> = {}
    for (const [id, v] of Object.entries(rawMaps as Record<string, unknown>)) {
      if (id in maps && typeof v === 'object' && v !== null && typeof (v as MapState).unlocked === 'boolean') {
        maps[id] = { unlocked: (v as MapState).unlocked }
      } else stash[id] = v
    }
    if (Object.keys(stash).length > 0) foreign['maps'] = stash
  }

  const cropsUnlocked: RunState['cropsUnlocked'] = {}
  const rawCrops = migrated['cropsUnlocked']
  if (typeof rawCrops === 'object' && rawCrops !== null && !Array.isArray(rawCrops)) {
    const stash: Record<string, unknown> = {}
    for (const [id, v] of Object.entries(rawCrops as Record<string, unknown>)) {
      if (id in c.cropById && typeof v === 'boolean') {
        if (v) cropsUnlocked[id] = true
      } else stash[id] = v
    }
    if (Object.keys(stash).length > 0) foreign['cropsUnlocked'] = stash
  }

  const upgrades: RunState['upgrades'] = {}
  const rawUpg = migrated['upgrades']
  if (typeof rawUpg === 'object' && rawUpg !== null && !Array.isArray(rawUpg)) {
    for (const [k, v] of Object.entries(rawUpg as Record<string, unknown>)) {
      if (typeof k === 'string' && k.includes(':') && Number.isInteger(v) && (v as number) >= 0) {
        upgrades[k] = v as number
      }
    }
  }

  return {
    kind: 'ok',
    state: {
      schemaVersion: CURRENT_SCHEMA_VERSION,
      coins,
      totalEarned,
      plots,
      maps,
      cropsUnlocked,
      upgrades,
      lastSeenAt: migrated['lastSeenAt'] as number,
      startedAt: migrated['startedAt'] as number,
      foreign
    }
  }
}

/** 文件导入入口：与 localStorage 加载共用同一 parseSave（审查重点4） */
export function importJson(text: string, c: ContentIndex): LoadOutcome {
  return parseSave(text, c)
}
