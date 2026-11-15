import { afterEach, describe, expect, it } from 'vitest'
import { CURRENT_SCHEMA_VERSION, MIGRATIONS, SaveError, migrateSave } from './migrate'

describe('migrateSave 迁移链', () => {
  afterEach(() => {
    delete MIGRATIONS[0]
  })

  it('v0 → v1 走注册的迁移函数', () => {
    MIGRATIONS[0] = (raw) => ({ ...raw, coins: raw['coins'] ?? '0' })
    const out = migrateSave({ schemaVersion: 0 })
    expect(out['schemaVersion']).toBe(CURRENT_SCHEMA_VERSION)
    expect(out['coins']).toBe('0')
  })

  it('缺中间环节 → SaveError，不静默跳级', () => {
    // CURRENT=1 且没有注册 0→1
    expect(() => migrateSave({ schemaVersion: 0 })).toThrow(SaveError)
  })

  it('高于当前版本 → SaveError("版本更新")（审查重点4）', () => {
    expect(() => migrateSave({ schemaVersion: 99 })).toThrow(/版本更新/)
  })

  it('缺 schemaVersion / 非法版本 → SaveError', () => {
    expect(() => migrateSave({})).toThrow(SaveError)
    expect(() => migrateSave({ schemaVersion: 'one' })).toThrow(SaveError)
    expect(() => migrateSave({ schemaVersion: 1.5 })).toThrow(SaveError)
  })
})
