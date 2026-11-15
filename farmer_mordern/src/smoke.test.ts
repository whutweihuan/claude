import { describe, expect, it } from 'vitest'
import Decimal from 'break_infinity.js'

describe('管道冒烟', () => {
  it('vitest + break_infinity 可用且金额保持十进制字符串语义', () => {
    expect(new Decimal('1e21').mul(2).toString()).toBe('2e+21')
  })
})
