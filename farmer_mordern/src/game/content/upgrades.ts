import type { UpgradeDef } from '../types'

/**
 * map 作用域升级的 baseCost 是相对该图 plotBaseCost 的倍率；
 * global 作用域（offlineLamp）的 baseCost 为绝对价。
 * 价格收敛入口见 index.ts 的 upgradeCost()。
 */
export const UPGRADE_DEFS: UpgradeDef[] = [
  { id: 'soil', name: '沃土', kind: 'soil', maxLevel: 50, baseCost: '8', costGrowth: 1.6, scope: 'map', effectPerLevel: 0.25 },
  { id: 'speed', name: '光合 Prism', kind: 'speed', maxLevel: 10, baseCost: '15', costGrowth: 1.8, scope: 'map', effectPerLevel: 0.1 },
  { id: 'autoHarvest', name: '自动收获', kind: 'autoHarvest', maxLevel: 1, baseCost: '60', costGrowth: 1, scope: 'map', effectPerLevel: 0 },
  { id: 'autoReplant', name: '自动补种', kind: 'autoReplant', maxLevel: 1, baseCost: '200', costGrowth: 1, scope: 'map', effectPerLevel: 0 },
  { id: 'offlineLamp', name: '棱镜灯', kind: 'offlineLamp', maxLevel: 2, baseCost: '5e6', costGrowth: 500, scope: 'global', effectPerLevel: 0 }
]
