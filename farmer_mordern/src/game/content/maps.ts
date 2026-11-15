import type { MapDef } from '../types'

export const MAPS: MapDef[] = [
  {
    id: 'garden',
    order: 1,
    name: '晨光菜园',
    hue: 95,
    plotCount: 12,
    freePlots: 2,
    plotBaseCost: '25',
    plotCostGrowth: 1.9,
    migrationCost: '1e7'
  },
  {
    id: 'greenhouse',
    order: 2,
    name: '暖光花房',
    hue: 330,
    plotCount: 14,
    freePlots: 2,
    plotBaseCost: '2.5e5',
    plotCostGrowth: 1.9,
    migrationCost: '1e10'
  },
  {
    id: 'orchard',
    order: 3,
    name: '半山果园',
    hue: 35,
    plotCount: 16,
    freePlots: 3,
    plotBaseCost: '5e8',
    plotCostGrowth: 1.9,
    migrationCost: '1e13'
  },
  {
    id: 'lake',
    order: 4,
    name: '镜湖田埂',
    hue: 195,
    plotCount: 18,
    freePlots: 3,
    plotBaseCost: '1e12',
    plotCostGrowth: 1.9,
    migrationCost: '1e16'
  },
  {
    id: 'aurora',
    order: 5,
    name: '极光学园',
    hue: 265,
    plotCount: 20,
    freePlots: 4,
    plotBaseCost: '5e15',
    plotCostGrowth: 1.9,
    migrationCost: null
  }
]
