export const CURRENT_SCHEMA_VERSION = 1

export type Migration = (raw: Record<string, unknown>) => Record<string, unknown>

/** 版本 v 的存档迁移到 v+1 的函数链；v1 首发为空，管道保持完整以便日后追加 */
export const MIGRATIONS: Record<number, Migration> = {}

export class SaveError extends Error {}

export function migrateSave(raw: Record<string, unknown>): Record<string, unknown> {
  const v = raw['schemaVersion']
  if (typeof v !== 'number' || !Number.isInteger(v) || v < 0) {
    throw new SaveError('schemaVersion 非法')
  }
  if (v > CURRENT_SCHEMA_VERSION) {
    throw new SaveError(`存档版本 ${v} 高于当前支持版本 ${CURRENT_SCHEMA_VERSION}（版本更新）`)
  }
  let cur: Record<string, unknown> = raw
  let from = v
  while (from < CURRENT_SCHEMA_VERSION) {
    const m = MIGRATIONS[from]
    if (!m) throw new SaveError(`缺迁移 ${from}→${from + 1}`)
    cur = m(cur)
    cur['schemaVersion'] = from + 1
    from += 1
  }
  return cur
}
