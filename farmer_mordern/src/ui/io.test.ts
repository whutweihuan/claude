import { describe, expect, it } from 'vitest'
import { saveFileName } from './io'

describe('saveFileName', () => {
  it('prism-farm-save-YYYY-MM-DD.json', () => {
    expect(saveFileName(new Date(2026, 10, 15))).toBe('prism-farm-save-2026-11-15.json')
  })
  it('月/日补零', () => {
    expect(saveFileName(new Date(2026, 0, 3))).toBe('prism-farm-save-2026-01-03.json')
  })
})
