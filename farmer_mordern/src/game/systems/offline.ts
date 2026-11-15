import { Decimal } from '../types'
import type { CropDef, OfflineReport, RunState } from '../types'
import type { ContentIndex } from '../content'
import { OFFLINE_CAPS_MS, upgradeKey } from '../content'
import { effectiveGrowMs } from './growth'
import { cloneState, harvestGain, parsePlotId } from './engine'

export function offlineCapMs(s: RunState): number {
  const lvl = s.upgrades[upgradeKey('offlineLamp', 'global')] ?? 0
  const cap = OFFLINE_CAPS_MS[Math.min(Math.max(lvl, 0), OFFLINE_CAPS_MS.length - 1)]
  return cap ?? OFFLINE_CAPS_MS[0] ?? 8 * 3600_000
}

interface MapStat {
  cycles: number
  gained: Decimal
}

/**
 * 窗口结算的唯一实现（§4.5/§6）：在线 autoTick 与离线 settleOffline 都走这里，
 * 一致性由构造保证——同一段时长无论切多少个窗口，逐位相等。
 * 语义：收获发生在地块"到熟时刻"（不早于窗口起点）；自动收获图每块至多进入收获链；
 * 自动补种在收获点立即按预设作物续种（扣 seedCost），种不起则停在"已收未种"。
 */
function settleWindow(s: RunState, c: ContentIndex, from: number, to: number): { state: RunState; perMap: Record<string, MapStat> } {
  const state = cloneState(s)
  const perMap: Record<string, MapStat> = {}
  if (!(to > from)) return { state, perMap }
  for (const id of Object.keys(state.plots)) {
    const p = state.plots[id]
    const ref = parsePlotId(id)
    if (!p || !ref || !p.unlocked) continue
    const map = c.mapById[ref.mapId]
    if (!map || state.maps[map.id]?.unlocked !== true) continue
    if ((state.upgrades[upgradeKey('autoHarvest', map.id)] ?? 0) < 1) continue
    if (p.cropId === null || p.plantedAt === null || p.growMs === null || p.growMs <= 0) continue
    let crop: CropDef | undefined = c.cropById[p.cropId]
    if (!crop) continue
    const due = p.plantedAt + p.growMs
    if (due > to) continue
    const ar = (state.upgrades[upgradeKey('autoReplant', map.id)] ?? 0) > 0
    const stat: MapStat = perMap[map.id] ?? { cycles: 0, gained: new Decimal(0) }
    perMap[map.id] = stat
    let t = due > from ? due : from
    for (;;) {
      const gain = harvestGain(state, c, map.id, crop)
      state.coins = state.coins.plus(gain)
      state.totalEarned = state.totalEarned.plus(gain)
      stat.cycles += 1
      stat.gained = stat.gained.plus(gain)
      if (!ar) {
        p.cropId = null
        p.plantedAt = null
        p.growMs = null
        break
      }
      const preset: CropDef | undefined = p.presetCropId ? c.cropById[p.presetCropId] : undefined
      const nextCrop: CropDef = preset ?? crop
      const cost = new Decimal(nextCrop.seedCost)
      if (state.coins.lt(cost)) {
        p.cropId = null
        p.plantedAt = null
        p.growMs = null
        break
      }
      state.coins = state.coins.minus(cost)
      const growMs = effectiveGrowMs(nextCrop, state.upgrades[upgradeKey('speed', map.id)] ?? 0)
      const ndue = t + growMs
      if (ndue > to) {
        p.cropId = nextCrop.id
        p.presetCropId = nextCrop.id
        p.plantedAt = t
        p.growMs = growMs
        break
      }
      crop = nextCrop
      t = ndue
    }
  }
  return { state, perMap }
}

export function settleOffline(
  s: RunState,
  c: ContentIndex,
  lastSeen: number,
  now: number
): { state: RunState; report: OfflineReport } {
  const cap = offlineCapMs(s)
  let from = lastSeen
  const floor = now - cap
  if (from < floor) from = floor // 超上限只结算最近 cap 时长（审查重点3）
  const elapsed = from < now ? now - from : 0 // 负窗口（回拨）按 0（审查重点2）
  const { state, perMap } = settleWindow(s, c, from, now)
  state.lastSeenAt = now
  let total = new Decimal(0)
  for (const m of Object.values(perMap)) total = total.add(m.gained)
  return { state, report: { elapsedMs: elapsed, gained: total, perMap } }
}

/** 在线心跳的单窗口结算：与离线同一函数，杜绝双实现漂移 */
export function autoTick(s: RunState, c: ContentIndex, now: number): RunState {
  const cap = offlineCapMs(s)
  const from = s.lastSeenAt > now - cap ? s.lastSeenAt : now - cap
  if (from >= now) {
    const state = cloneState(s)
    state.lastSeenAt = now
    return state
  }
  const { state } = settleWindow(s, c, from, now)
  state.lastSeenAt = now
  return state
}
