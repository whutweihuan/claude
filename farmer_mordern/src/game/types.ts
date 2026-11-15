import Decimal from 'break_infinity.js'

export { Decimal }

export interface PlotState {
  id: string
  unlocked: boolean
  cropId: string | null
  /** 自动补种与下次手种使用的作物（§4.3），收获后不清空 */
  presetCropId: string | null
  plantedAt: number | null
  /** 种植时刻的有效生长时长快照（§6），之后升级光合不影响本轮 */
  growMs: number | null
}

export interface MapState {
  unlocked: boolean
}

export interface RunState {
  schemaVersion: number
  coins: Decimal
  totalEarned: Decimal
  /** key 与 value.id 相同，plotId = `${mapId}:${n}`，n 从 0 */
  plots: Record<string, PlotState>
  maps: Record<string, MapState>
  cropsUnlocked: Record<string, boolean>
  /** key = `${upgradeDefId}:${scope}`，scope = mapId 或 'global'，value = 等级 */
  upgrades: Record<string, number>
  lastSeenAt: number
  startedAt: number
  /** 前向兼容：加载时原样保留的未知字段，toSaveData 合回（§5） */
  foreign: Record<string, unknown>
}

export interface CropDef {
  id: string
  mapId: string
  name: string
  seedCost: string
  yieldCoins: string
  growTimeMs: number
  /** null = 随图解锁自动可用（§4.2） */
  unlockCost: string | null
  sprite: {
    body: string
    accent: string
    leaf: string
    form: 'stem' | 'bush' | 'flower' | 'tree' | 'vine' | 'grain' | 'fantasy'
  }
}

export interface MapDef {
  id: string
  order: number
  name: string
  /** 主题色相 0-360 */
  hue: number
  plotCount: number
  /** 解锁地图时免费赠予的地块数（§11 裁定） */
  freePlots: number
  plotBaseCost: string
  plotCostGrowth: number
  /** 离开本图去下一图的迁徙费；最后一图为 null */
  migrationCost: string | null
}

export type UpgradeKind = 'soil' | 'speed' | 'autoHarvest' | 'autoReplant' | 'offlineLamp'

export interface UpgradeDef {
  id: UpgradeKind
  name: string
  kind: UpgradeKind
  maxLevel: number
  /** map 作用域：相对 mapDef.plotBaseCost 的倍率；global 作用域：绝对价 */
  baseCost: string
  costGrowth: number
  scope: 'map' | 'global'
  /** 每级效果：soil +25% / speed +10% / 一次性件与 lamp 忽略 */
  effectPerLevel: number
}

export type GameEvent =
  | { t: 'plant'; plotId: string; cropId: string }
  | { t: 'harvest'; plotId: string }
  | { t: 'buyPlot'; plotId: string }
  | { t: 'unlockCrop'; cropId: string }
  | { t: 'buyUpgrade'; defId: UpgradeKind; scope: string }
  | { t: 'swapPreset'; plotId: string; cropId: string }
  | { t: 'clearCrop'; plotId: string }
  | { t: 'migrate'; mapId: string }

export type RejectReason = 'noCoins' | 'notSequenced' | 'alreadyOwned' | 'locked' | 'prereq' | 'invalid' | 'maxLevel'

export interface ApplyResult {
  ok: boolean
  reason?: RejectReason
  state: RunState
}

export interface OfflineReport {
  elapsedMs: number
  gained: Decimal
  perMap: Record<string, { cycles: number; gained: Decimal }>
}
