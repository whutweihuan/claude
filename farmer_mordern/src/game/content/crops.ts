import type { CropDef } from '../types'

/**
 * 内容即数据（§8.2）：新增作物 = 新增条目。
 * 数值骨架：yieldCoins(k) = yBase × 5^k；seedCost ≈ yield × 0.5（首种 = 1）；
 * growTimeMs(k) = base × ratio^k；跨图首作物 > 前图末作物（不倒挂）。
 * 全部取值须过 content.test.ts 节奏断言。
 */
export const CROPS: CropDef[] = [
  // ── 晨光菜园（5s → 20min）──
  { id: 'radish', mapId: 'garden', name: '白萝卜', seedCost: '1', yieldCoins: '12', growTimeMs: 5000, unlockCost: null, sprite: { body: '#f6f2ea', accent: '#8bc34a', leaf: '#4caf50', form: 'stem' } },
  { id: 'bokchoy', mapId: 'garden', name: '小青菜', seedCost: '30', yieldCoins: '60', growTimeMs: 15000, unlockCost: null, sprite: { body: '#66bb6a', accent: '#a5d6a7', leaf: '#2e7d32', form: 'bush' } },
  { id: 'sunflower', mapId: 'garden', name: '向日葵', seedCost: '150', yieldCoins: '300', growTimeMs: 45000, unlockCost: null, sprite: { body: '#fdd835', accent: '#6d4c41', leaf: '#43a047', form: 'flower' } },
  { id: 'tomato', mapId: 'garden', name: '番茄', seedCost: '750', yieldCoins: '1500', growTimeMs: 135000, unlockCost: null, sprite: { body: '#e53935', accent: '#ff8a80', leaf: '#388e3c', form: 'bush' } },
  { id: 'pepper', mapId: 'garden', name: '辣椒', seedCost: '3750', yieldCoins: '7500', growTimeMs: 405000, unlockCost: '6e4', sprite: { body: '#d81b60', accent: '#ff7043', leaf: '#2e7d32', form: 'bush' } },
  { id: 'pumpkin', mapId: 'garden', name: '南瓜', seedCost: '18750', yieldCoins: '3.75e4', growTimeMs: 1215000, unlockCost: '3e5', sprite: { body: '#ef6c00', accent: '#ffb74d', leaf: '#558b2f', form: 'vine' } },

  // ── 暖光花房（30min → 3.8h）──
  { id: 'orchid', mapId: 'greenhouse', name: '蝴蝶兰', seedCost: '1', yieldCoins: '3e5', growTimeMs: 1800000, unlockCost: null, sprite: { body: '#f8bbd0', accent: '#ce93d8', leaf: '#66bb6a', form: 'flower' } },
  { id: 'succulent', mapId: 'greenhouse', name: '玉露多肉', seedCost: '7.5e5', yieldCoins: '1.5e6', growTimeMs: 2700000, unlockCost: null, sprite: { body: '#80cbc4', accent: '#b2dfdb', leaf: '#00695c', form: 'bush' } },
  { id: 'tulip', mapId: 'greenhouse', name: '郁金香', seedCost: '3.75e6', yieldCoins: '7.5e6', growTimeMs: 4050000, unlockCost: null, sprite: { body: '#ef5350', accent: '#ffcdd2', leaf: '#4caf50', form: 'stem' } },
  { id: 'anthurium', mapId: 'greenhouse', name: '红掌', seedCost: '1.875e7', yieldCoins: '3.75e7', growTimeMs: 6075000, unlockCost: null, sprite: { body: '#c62828', accent: '#ffab91', leaf: '#2e7d32', form: 'flower' } },
  { id: 'mimosa', mapId: 'greenhouse', name: '含羞草', seedCost: '9.375e7', yieldCoins: '1.875e8', growTimeMs: 9112500, unlockCost: '1.5e9', sprite: { body: '#f48fb1', accent: '#f8bbd0', leaf: '#81c784', form: 'bush' } },
  { id: 'grapebell', mapId: 'greenhouse', name: '风铃葡萄', seedCost: '4.6875e8', yieldCoins: '9.375e8', growTimeMs: 13668750, unlockCost: '7.5e9', sprite: { body: '#7e57c2', accent: '#b39ddb', leaf: '#66bb6a', form: 'vine' } },

  // ── 半山果园（4h → 37h）──
  { id: 'strawberry', mapId: 'orchard', name: '草莓', seedCost: '1', yieldCoins: '5e9', growTimeMs: 14400000, unlockCost: null, sprite: { body: '#e53935', accent: '#ffcdd2', leaf: '#43a047', form: 'bush' } },
  { id: 'blueberry', mapId: 'orchard', name: '蓝莓', seedCost: '1.25e10', yieldCoins: '2.5e10', growTimeMs: 20880000, unlockCost: null, sprite: { body: '#5c6bc0', accent: '#9fa8da', leaf: '#2e7d32', form: 'bush' } },
  { id: 'peach', mapId: 'orchard', name: '蜜桃', seedCost: '6.25e10', yieldCoins: '1.25e11', growTimeMs: 30276000, unlockCost: null, sprite: { body: '#ff8a65', accent: '#ffccbc', leaf: '#558b2f', form: 'tree' } },
  { id: 'cherry', mapId: 'orchard', name: '樱桃', seedCost: '3.125e11', yieldCoins: '6.25e11', growTimeMs: 43900200, unlockCost: null, sprite: { body: '#d32f2f', accent: '#ef9a9a', leaf: '#33691e', form: 'tree' } },
  { id: 'pear', mapId: 'orchard', name: '雪梨', seedCost: '1.5625e12', yieldCoins: '3.125e12', growTimeMs: 63655290, unlockCost: '2.5e13', sprite: { body: '#dce775', accent: '#f0f4c3', leaf: '#558b2f', form: 'tree' } },
  { id: 'grape', mapId: 'orchard', name: '紫提', seedCost: '7.8125e12', yieldCoins: '1.5625e13', growTimeMs: 92300171, unlockCost: '1.25e14', sprite: { body: '#6a1b9a', accent: '#ab47bc', leaf: '#43a047', form: 'vine' } },
  { id: 'kiwi', mapId: 'orchard', name: '猕猴桃', seedCost: '3.90625e13', yieldCoins: '7.8125e13', growTimeMs: 133835248, unlockCost: '6.25e14', sprite: { body: '#8d6e63', accent: '#aed581', leaf: '#33691e', form: 'vine' } },

  // ── 镜湖田埂（24h → 6d）──
  { id: 'reed', mapId: 'lake', name: '芦苇', seedCost: '1', yieldCoins: '4e14', growTimeMs: 86400000, unlockCost: null, sprite: { body: '#bcaaa4', accent: '#d7ccc8', leaf: '#7cb342', form: 'grain' } },
  { id: 'lotus', mapId: 'lake', name: '荷花', seedCost: '1e15', yieldCoins: '2e15', growTimeMs: 116640000, unlockCost: null, sprite: { body: '#f48fb1', accent: '#fce4ec', leaf: '#00897b', form: 'flower' } },
  { id: 'caltrop', mapId: 'lake', name: '菱角', seedCost: '5e15', yieldCoins: '1e16', growTimeMs: 157464000, unlockCost: null, sprite: { body: '#6d4c41', accent: '#a1887f', leaf: '#00695c', form: 'vine' } },
  { id: 'waterbamboo', mapId: 'lake', name: '水竹', seedCost: '2.5e16', yieldCoins: '5e16', growTimeMs: 212576400, unlockCost: null, sprite: { body: '#aed581', accent: '#dcedc8', leaf: '#558b2f', form: 'grain' } },
  { id: 'chestnut', mapId: 'lake', name: '荸荠', seedCost: '1.25e17', yieldCoins: '2.5e17', growTimeMs: 286978140, unlockCost: '2e18', sprite: { body: '#5d4037', accent: '#8d6e63', leaf: '#00796b', form: 'stem' } },
  { id: 'waternut', mapId: 'lake', name: '莼菜', seedCost: '6.25e17', yieldCoins: '1.25e18', growTimeMs: 387420489, unlockCost: '1e19', sprite: { body: '#4db6ac', accent: '#80cbc4', leaf: '#004d40', form: 'bush' } },
  { id: 'rice', mapId: 'lake', name: '金穗稻', seedCost: '3.125e18', yieldCoins: '6.25e18', growTimeMs: 523017660, unlockCost: '5e19', sprite: { body: '#ffd54f', accent: '#fff176', leaf: '#9e9d24', form: 'grain' } },

  // ── 极光学园（6d → 32d，终章）──
  { id: 'froststar', mapId: 'aurora', name: '星霜花', seedCost: '1', yieldCoins: '4e19', growTimeMs: 518400000, unlockCost: null, sprite: { body: '#b39ddb', accent: '#ede7f6', leaf: '#7986cb', form: 'flower' } },
  { id: 'moonvine', mapId: 'aurora', name: '月见藤', seedCost: '1e20', yieldCoins: '2e20', growTimeMs: 684288000, unlockCost: null, sprite: { body: '#9575cd', accent: '#d1c4e9', leaf: '#4db6ac', form: 'vine' } },
  { id: 'prisummush', mapId: 'aurora', name: '棱镜菇', seedCost: '5e20', yieldCoins: '1e21', growTimeMs: 903260160, unlockCost: null, sprite: { body: '#4dd0e1', accent: '#e0f7fa', leaf: '#6a1b9a', form: 'fantasy' } },
  { id: 'auroracherry', mapId: 'aurora', name: '极光樱', seedCost: '2.5e21', yieldCoins: '5e21', growTimeMs: 1192303411, unlockCost: null, sprite: { body: '#f48fb1', accent: '#b388ff', leaf: '#7c4dff', form: 'tree' } },
  { id: 'starmillet', mapId: 'aurora', name: '星轨穗', seedCost: '1.25e22', yieldCoins: '2.5e22', growTimeMs: 1573840503, unlockCost: '2e23', sprite: { body: '#8c9eff', accent: '#e8eaf6', leaf: '#536dfe', form: 'grain' } },
  { id: 'dreamfruit', mapId: 'aurora', name: '梦实', seedCost: '6.25e22', yieldCoins: '1.25e23', growTimeMs: 2077469464, unlockCost: '1e24', sprite: { body: '#ea80fc', accent: '#f8bbd0', leaf: '#651fff', form: 'fantasy' } },
  { id: 'evernightlotus', mapId: 'aurora', name: '长夜莲', seedCost: '3.125e23', yieldCoins: '6.25e23', growTimeMs: 2742259693, unlockCost: '5e24', sprite: { body: '#7c4dff', accent: '#b388ff', leaf: '#18ffff', form: 'fantasy' } }
]
