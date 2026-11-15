import { create } from 'zustand'
import { createJSONStorage, persist, type PersistOptions, type StateStorage } from 'zustand/middleware'
import { buildIndex } from '../game/content'
import { applyEvent, initialState } from '../game/systems/engine'
import { autoTick, settleOffline } from '../game/systems/offline'
import { exportJson, parseSave, toSaveData } from '../game/systems/save'
import type { GameEvent, OfflineReport, RunState } from '../game/types'

export const SAVE_KEY = 'prism-farm-save'

export interface StorageLike {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
  removeItem(key: string): void
}

export interface UiState {
  report: OfflineReport | null
  loadError: string | null
  nowTick: number
  muted: boolean
  volume: number
}

export interface GameStore {
  game: RunState
  ui: UiState
  dispatch(ev: GameEvent): boolean
  tick(now: number): void
  dismissReport(): void
  setMuted(m: boolean): void
  setVolume(v: number): void
  exportSave(): string
  importSave(text: string): { ok: boolean; reason?: string }
  newGame(): void
  hardReset(): void
}

const CONTENT = buildIndex()

/**
 * 存储里可能是两种形态：persist 写的信封 {state:{game:SaveData},version}，
 * 或用户手工恢复/旧版裸 SaveData 文本。统一剥出 SaveData 层再走 parseSave。
 */
function unwrapSave(stored: string | null): string | null {
  if (stored === null || stored.trim() === '') return stored
  try {
    const parsed: unknown = JSON.parse(stored)
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      const state = (parsed as Record<string, unknown>)['state']
      if (state && typeof state === 'object' && !Array.isArray(state)) {
        const game = (state as Record<string, unknown>)['game']
        if (game && typeof game === 'object') return JSON.stringify(game)
      }
    }
  } catch {
    /* 交给 parseSave 判 unreadable */
  }
  return stored
}

/**
 * 说明（账本裁定）：不用 immer 中间件包 game —— RunState 含 Decimal 实例，
 * immer 的 draft/freeze 会破坏 break_infinity 的可变内核；
 * 引擎本身已是纯函数 + cloneState，immer 在 store 层是纯风险无收益。
 * persist 仍承担序列化管线，写盘守卫与 1s 节流在自定义 storage 包装里实现。
 */
export function createGameStore(backend: StorageLike, clock: () => number = () => Date.now()) {
  let readOnly = false
  let loadError: string | null = null
  let writes = 0
  let hydrated: RunState | null = null as RunState | null
  let lastWrite = Number.NEGATIVE_INFINITY
  let pending: string | null = null
  let timer: ReturnType<typeof setTimeout> | null = null

  const persistStorage: StateStorage = {
    getItem: (name) => {
      const outcome = parseSave(unwrapSave(backend.getItem(name)), CONTENT)
      if (outcome.kind === 'ok') {
        hydrated = outcome.state
        return JSON.stringify({ state: { game: toSaveData(outcome.state, outcome.state.lastSeenAt) }, version: 0 })
      }
      hydrated = null
      if (outcome.kind === 'unreadable') {
        readOnly = true
        loadError = '存档无法读取，本次会话进入只读模式：不会覆盖原文件，可在设置中导出文本自救'
      } else if (outcome.kind === 'invalid') {
        readOnly = true
        loadError = `存档校验失败（${outcome.reason}），本次会话不会写盘`
      }
      return null
    },
    setItem: (name, value) => {
      if (readOnly) return
      const now = clock()
      if (now - lastWrite >= 1000) {
        if (timer !== null) {
          clearTimeout(timer)
          timer = null
        }
        pending = null
        lastWrite = now
        writes += 1
        backend.setItem(name, value)
      } else {
        pending = value
        if (timer === null) {
          timer = setTimeout(() => {
            timer = null
            if (pending === null || readOnly) return
            lastWrite = clock()
            writes += 1
            backend.setItem(name, pending)
            pending = null
          }, 1000 - (now - lastWrite))
        }
      }
    },
    removeItem: (name) => {
      backend.removeItem(name)
    }
  }

  const options: PersistOptions<GameStore, { game: ReturnType<typeof toSaveData> }> = {
    name: SAVE_KEY,
    version: 0,
    storage: createJSONStorage(() => persistStorage),
    partialize: (s) => ({ game: toSaveData(s.game, clock()) }),
    merge: (_persisted, current) => ({ ...current, game: hydrated ?? current.game })
  }

  const useGame = create<GameStore>()(
    persist((set, get) => {
      const blockedWrite = (fn: () => void) => {
        const prev = readOnly
        readOnly = true
        try {
          fn()
        } finally {
          readOnly = prev
        }
      }
      return {
        game: initialState(CONTENT, clock()),
        ui: { report: null, loadError: null, nowTick: clock(), muted: true, volume: 0.8 },
        dispatch: (ev) => {
          const r = applyEvent(get().game, ev, CONTENT, clock())
          if (r.ok) set({ game: r.state })
          return r.ok
        },
        tick: (now) => {
          const g = autoTick(get().game, CONTENT, now)
          set({ game: g, ui: { ...get().ui, nowTick: now } })
        },
        dismissReport: () => set({ ui: { ...get().ui, report: null } }),
        setMuted: (m) => set({ ui: { ...get().ui, muted: m } }),
        setVolume: (v) => set({ ui: { ...get().ui, volume: Math.min(1, Math.max(0, v)) } }),
        exportSave: () => exportJson(get().game),
        importSave: (text) => {
          const outcome = parseSave(text, CONTENT)
          if (outcome.kind !== 'ok') {
            const reason =
              outcome.kind === 'unreadable'
                ? '文件不是合法 JSON'
                : outcome.kind === 'invalid'
                  ? outcome.reason
                  : '文件为空'
            return { ok: false, reason }
          }
          // 用户显式导入 = 明确意图：解除只读，覆盖当前存档是被授权的
          readOnly = false
          loadError = null
          set({
            game: outcome.state,
            ui: { ...get().ui, loadError: null, report: null }
          })
          return { ok: true }
        },
        newGame: () => set({ game: initialState(CONTENT, clock()), ui: { ...get().ui, report: null } }),
        hardReset: () => {
          pending = null
          if (timer !== null) {
            clearTimeout(timer)
            timer = null
          }
          readOnly = false
          loadError = null
          blockedWrite(() => {
            backend.removeItem(SAVE_KEY)
            writes = 0
            set({
              game: initialState(CONTENT, clock()),
              ui: { report: null, loadError: null, nowTick: clock(), muted: true, volume: 0.8 }
            })
          })
        }
      }
    }, options)
  )

  // 启动流程：hydrate 完成后统一走 settleOffline（在线/离线同一函数）
  const st = useGame.getState()
  if (hydrated) {
    const { state, report } = settleOffline(hydrated, CONTENT, hydrated.lastSeenAt, clock())
    useGame.setState({
      game: state,
      ui: { ...st.ui, report: report.gained.gt(0) ? report : null, loadError }
    })
  } else {
    useGame.setState({ game: initialState(CONTENT, clock()), ui: { ...st.ui, loadError } })
  }

  return {
    useGame,
    readRaw: () => backend.getItem(SAVE_KEY),
    flags: {
      get readOnly() {
        return readOnly
      },
      get writes() {
        return writes
      },
      get loadError() {
        return loadError
      }
    }
  }
}

export type GameStoreApi = ReturnType<typeof createGameStore>

let singleton: GameStoreApi | null = null

function webBackend(): StorageLike {
  try {
    const ls = globalThis.localStorage
    if (ls) {
      return {
        getItem: (k) => {
          try {
            return ls.getItem(k)
          } catch {
            return null
          }
        },
        setItem: (k, v) => {
          ls.setItem(k, v)
        },
        removeItem: (k) => {
          ls.removeItem(k)
        }
      }
    }
  } catch {
    /* file:// 或隐私模式下 localStorage 不可用：退化为内存档 */
  }
  const m = new Map<string, string>()
  return {
    getItem: (k) => m.get(k) ?? null,
    setItem: (k, v) => {
      m.set(k, v)
    },
    removeItem: (k) => {
      m.delete(k)
    }
  }
}

/** 应用入口用的惰性单例（测试直接调 createGameStore 注入假后端） */
export function getStore(): GameStoreApi {
  if (!singleton) singleton = createGameStore(webBackend())
  return singleton
}

/** 10Hz 心跳；返回停止函数（§6：逻辑由墙钟驱动，心跳只负责触发结算与渲染） */
export function startHeartbeat(api: GameStoreApi, intervalMs = 100): () => void {
  const id = setInterval(() => api.useGame.getState().tick(Date.now()), intervalMs)
  return () => clearInterval(id)
}
