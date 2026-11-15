import { describe, expect, it } from 'vitest'
import Decimal from 'break_infinity.js'
import { buildIndex, plotPrice } from './index'
import type { CropDef, MapDef } from '../types'

const idx = buildIndex()
const maps: MapDef[] = [...idx.maps].sort((a, b) => a.order - b.order)

function cropsOf(mapId: string): CropDef[] {
  const crops = idx.cropsByMap[mapId]
  if (!crops) throw new Error(`map ${mapId} 没有作物`)
  return crops
}

function at<T>(arr: T[], i: number): T {
  const v = arr[i]
  if (v === undefined) throw new Error(`index ${i} 越界`)
  return v
}

describe('内容节奏断言（规格 §9 / §4.4）', () => {
  it('每种作物 yieldCoins > seedCost（单轮净利恒正）', () => {
    for (const map of maps) {
      for (const c of cropsOf(map.id)) {
        expect(new Decimal(c.yieldCoins).gt(c.seedCost), `${c.id} 净利非正`).toBe(true)
      }
    }
  })

  it('同图相邻作物收益比 ∈ [1.3, 8] 且 收益/小时 严格递增', () => {
    for (const map of maps) {
      const crops = cropsOf(map.id)
      for (let k = 1; k < crops.length; k++) {
        const prev = at(crops, k - 1)
        const cur = at(crops, k)
        const ratio = new Decimal(cur.yieldCoins).div(prev.yieldCoins).toNumber()
        expect(ratio, `${cur.id} 相邻比 ${ratio}`).toBeGreaterThanOrEqual(1.3)
        expect(ratio, `${cur.id} 相邻比 ${ratio}`).toBeLessThanOrEqual(8)
        const hrPrev = new Decimal(prev.yieldCoins).div(prev.growTimeMs)
        const hrCur = new Decimal(cur.yieldCoins).div(cur.growTimeMs)
        expect(hrCur.gt(hrPrev), `${cur.id} 时薪倒挂`).toBe(true)
      }
    }
  })

  it('每图 6~8 种作物；前 4 种自动可用，其余需付费解锁', () => {
    for (const map of maps) {
      const crops = cropsOf(map.id)
      expect(crops.length).toBeGreaterThanOrEqual(6)
      expect(crops.length).toBeLessThanOrEqual(8)
      crops.forEach((c, k) => {
        if (k < 4) expect(c.unlockCost, `${c.id} 应自动可用`).toBeNull()
        else expect(c.unlockCost, `${c.id} 应定价`).not.toBeNull()
      })
    }
  })

  it('地块总数与免费赠地数健全（赠地 ≥ 1 且留有余量可买）', () => {
    for (const m of maps) {
      expect(m.freePlots).toBeGreaterThanOrEqual(1)
      expect(m.freePlots).toBeLessThan(m.plotCount)
    }
  })

  it('地块价格曲线防空窗：第 n 块价 < 前 n+2 种作物单轮净利之和 × 50', () => {
    for (const map of maps) {
      const crops = cropsOf(map.id)
      for (let n = map.freePlots; n < map.plotCount; n++) {
        const price = plotPrice(map, n)
        let netSum = new Decimal(0)
        const window = Math.min(n + 2, crops.length)
        for (let k = 0; k < window; k++) {
          const c = at(crops, k)
          netSum = netSum.add(new Decimal(c.yieldCoins).sub(c.seedCost))
        }
        expect(price.lt(netSum.mul(50)), `${map.id} 第 ${n} 块价 ${price} 超窗`).toBe(true)
      }
    }
  })

  it('迁徙费除末图外恒存在且严格递增', () => {
    let prev: Decimal | null = null
    for (let i = 0; i < maps.length; i++) {
      const m = at(maps, i)
      if (i === maps.length - 1) {
        expect(m.migrationCost, `${m.id} 末图不应有迁徙费`).toBeNull()
      } else {
        expect(m.migrationCost, `${m.id} 缺迁徙费`).not.toBeNull()
        const cost = new Decimal(m.migrationCost ?? '0')
        if (prev) expect(cost.gt(prev), `${m.id} 迁徙费未递增`).toBe(true)
        prev = cost
      }
    }
  })

  it('跨图收益不倒挂：后图首作物 > 前图最高作物', () => {
    for (let i = 1; i < maps.length; i++) {
      const prevCrops = cropsOf(at(maps, i - 1).id)
      const curCrops = cropsOf(at(maps, i).id)
      const prevMax = at(prevCrops, prevCrops.length - 1)
      expect(new Decimal(at(curCrops, 0).yieldCoins).gt(prevMax.yieldCoins)).toBe(true)
    }
  })

  it('id 唯一、引用完整、order 连续', () => {
    const mapIds = new Set(maps.map((m) => m.id))
    expect(mapIds.size).toBe(maps.length)
    maps.forEach((m, i) => expect(m.order).toBe(i + 1))
    const cropIds = new Set<string>()
    for (const map of maps) {
      for (const c of cropsOf(map.id)) {
        expect(cropIds.has(c.id), `作物 id 重复 ${c.id}`).toBe(false)
        cropIds.add(c.id)
        expect(c.mapId).toBe(map.id)
      }
    }
    for (const def of Object.values(idx.upgradeById)) {
      expect(def.scope === 'global' ? 'global' : 'map').toBeTruthy()
    }
  })
})

describe('内容健壮性（审查建议）', () => {
  it('生长时长 ≥ 1000ms，保住离线循环上界', () => {
    for (const map of maps) {
      for (const c of cropsOf(map.id)) {
        expect(c.growTimeMs).toBeGreaterThanOrEqual(1000)
      }
    }
  })
})
