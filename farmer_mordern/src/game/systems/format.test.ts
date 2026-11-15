import { describe, expect, it } from 'vitest'
import Decimal from 'break_infinity.js'
import { formatCoins, formatDuration, formatPercent } from './format'

describe('formatCoins', () => {
  it('千位以下原样取整', () => {
    expect(formatCoins(new Decimal(999))).toBe('999')
    expect(formatCoins(new Decimal(0))).toBe('0')
    expect(formatCoins(new Decimal(12.7))).toBe('13')
  })
  it('千分位阶梯', () => {
    expect(formatCoins(new Decimal(1234))).toBe('1.23K')
    expect(formatCoins(new Decimal(1e6))).toBe('1.00M')
    expect(formatCoins(new Decimal(2.5e9))).toBe('2.50B')
    expect(formatCoins(new Decimal(1e15))).toBe('1.00Qa')
  })
  it('阶梯边界进位不出现 1000K', () => {
    expect(formatCoins(new Decimal(999_999))).toBe('1.00M')
  })
  it('超出命名阶梯 Dc 后走科学计数', () => {
    expect(formatCoins(new Decimal('1e36'))).toBe('1.00e+36')
    expect(formatCoins(new Decimal('7.9e45'))).toBe('7.90e+45')
  })
})

describe('formatDuration', () => {
  it('小时+分钟 / 秒', () => {
    expect(formatDuration(3_600_000 + 5 * 60_000)).toBe('1小时5分')
    expect(formatDuration(999)).toBe('0秒')
    expect(formatDuration(45_000)).toBe('45秒')
    expect(formatDuration(0)).toBe('0秒')
  })
  it('长离线显示天', () => {
    expect(formatDuration(25 * 3_600_000 + 3 * 60_000)).toBe('1天1小时')
  })
  it('负值按 0 处理（时钟回拨防御）', () => {
    expect(formatDuration(-5000)).toBe('0秒')
  })
})

describe('formatPercent', () => {
  it('整数不带小数，半值保留一位', () => {
    expect(formatPercent(0.25)).toBe('25%')
    expect(formatPercent(0.125)).toBe('12.5%')
    expect(formatPercent(1)).toBe('100%')
  })
})

describe('formatCoins 小数与负数防御（审查 I1）', () => {
  it('(0,1) 区间不乱码', () => {
    expect(formatCoins(new Decimal('0.5'))).toBe('0.5')
    expect(formatCoins(new Decimal('0.25'))).toBe('0.25')
    expect(formatCoins(new Decimal('1e-6'))).toBe('0')
  })
  it('负数带符号不产生 undefined', () => {
    expect(formatCoins(new Decimal('-3'))).toBe('-3')
  })
})
