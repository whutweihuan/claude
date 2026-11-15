import { Decimal } from '../types'
import type { CropDef, MapDef, UpgradeDef } from '../types'
import { MAPS } from './maps'
import { CROPS } from './crops'
import { UPGRADE_DEFS } from './upgrades'

export interface ContentIndex {
  maps: MapDef[]
  mapById: Record<string, MapDef>
  cropById: Record<string, CropDef>
  cropsByMap: Record<string, CropDef[]>
  upgradeById: Record<string, UpgradeDef>
}

export function buildIndex(): ContentIndex {
  const maps = [...MAPS].sort((a, b) => a.order - b.order)
  const mapById: Record<string, MapDef> = {}
  const cropById: Record<string, CropDef> = {}
  const cropsByMap: Record<string, CropDef[]> = {}
  const upgradeById: Record<string, UpgradeDef> = {}
  for (const m of maps) {
    mapById[m.id] = m
    cropsByMap[m.id] = []
  }
  for (const c of CROPS) {
    cropById[c.id] = c
    cropsByMap[c.mapId]?.push(c)
  }
  for (const u of UPGRADE_DEFS) upgradeById[u.id] = u
  return { maps, mapById, cropById, cropsByMap, upgradeById }
}

export function plotKey(mapId: string, n: number): string {
  return `${mapId}:${n}`
}

export function upgradeKey(defId: string, scope: string): string {
  return `${defId}:${scope}`
}

/** 第 n 块地（绝对下标）的价格：免费赠地之后的第一块为基准价（§11 裁定） */
export function plotPrice(mapDef: MapDef, n: number): Decimal {
  const steps = Math.max(0, n - mapDef.freePlots)
  return new Decimal(mapDef.plotBaseCost).mul(new Decimal(mapDef.plotCostGrowth).pow(steps))
}

/** 升级第 level+1 级的价格；map 作用域必须传 mapDef */
export function upgradeCost(def: UpgradeDef, mapDef: MapDef | null, level: number): Decimal {
  if (def.scope === 'global') {
    return new Decimal(def.baseCost).mul(new Decimal(def.costGrowth).pow(level))
  }
  if (!mapDef) throw new Error(`upgrade ${def.id} 是图作用域，需要 mapDef`)
  return new Decimal(mapDef.plotBaseCost).mul(def.baseCost).mul(new Decimal(def.costGrowth).pow(level))
}

/** 棱镜灯等级 → 离线结算上限（毫秒）：0/1/2 级 = 8h/24h/72h */
export const OFFLINE_CAPS_MS = [8, 24, 72].map((h) => h * 3600_000)
