import { useRef, useState } from 'react'
import { getStore } from '../store/gameStore'
import { downloadText, readFileAsText, saveFileName } from './io'

/** 长按 3 秒重置（带进度环视觉） */
function HoldReset({ onDone }: { onDone: () => void }) {
  const [progress, setProgress] = useState(0)
  const timer = useRef<number | null>(null)
  function start() {
    const t0 = Date.now()
    timer.current = window.setInterval(() => {
      const p = Math.min(1, (Date.now() - t0) / 3000)
      setProgress(p)
      if (p >= 1) {
        stop()
        onDone()
      }
    }, 50)
  }
  function stop() {
    if (timer.current !== null) window.clearInterval(timer.current)
    timer.current = null
    setProgress(0)
  }
  return (
    <button
      type="button"
      onPointerDown={start}
      onPointerUp={stop}
      onPointerLeave={stop}
      className="relative w-full overflow-hidden rounded-lg border border-rose-400/40 px-3 py-2 text-sm text-rose-200/90"
    >
      <span
        className="absolute inset-y-0 left-0 bg-rose-500/25 transition-[width]"
        style={{ width: `${Math.round(progress * 100)}%` }}
      />
      <span className="relative">{progress > 0 ? '继续按住…' : '长按 3 秒重置存档'}</span>
    </button>
  )
}

export function SettingsPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const api = getStore()
  const { useGame } = api
  const muted = useGame((s) => s.ui.muted)
  const volume = useGame((s) => s.ui.volume)
  const loadError = useGame((s) => s.ui.loadError)
  const [importMsg, setImportMsg] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-[min(92vw,420px)] space-y-4 rounded-2xl border border-white/15 bg-slate-900/95 p-6 text-sm shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <div className="text-base font-semibold text-white/90">设置</div>
          <button type="button" onClick={onClose} className="text-white/40 hover:text-white/80">
            ✕
          </button>
        </div>

        <label className="flex items-center justify-between">
          <span className="text-white/75">音效</span>
          <input
            type="checkbox"
            checked={!muted}
            onChange={(e) => useGame.getState().setMuted(!e.target.checked)}
            className="h-4 w-4 accent-emerald-400"
          />
        </label>
        <label className="block">
          <div className="mb-1 text-white/60">音量</div>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={volume}
            onChange={(e) => useGame.getState().setVolume(Number(e.target.value))}
            className="w-full accent-emerald-400"
            disabled={muted}
          />
        </label>

        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => downloadText(saveFileName(new Date()), useGame.getState().exportSave())}
            className="rounded-lg border border-white/15 px-3 py-2 text-white/80 hover:border-emerald-300/50"
          >
            导出存档
          </button>
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            className="rounded-lg border border-white/15 px-3 py-2 text-white/80 hover:border-emerald-300/50"
          >
            导入存档
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".json,application/json"
            className="hidden"
            onChange={async (e) => {
              const f = e.target.files?.[0]
              e.target.value = ''
              if (!f) return
              try {
                const text = await readFileAsText(f)
                const r = useGame.getState().importSave(text)
                setImportMsg(r.ok ? '导入成功' : `导入被拒绝：${r.reason}（当前存档未受影响）`)
              } catch {
                setImportMsg('导入被拒绝：文件读取失败（当前存档未受影响）')
              }
            }}
          />
        </div>
        {importMsg && <div className="text-xs text-emerald-200/80">{importMsg}</div>}

        {loadError && (
          <button
            type="button"
            onClick={() => downloadText('prism-farm-save-raw.txt', api.readRaw() ?? '')}
            className="w-full rounded-lg border border-amber-300/40 px-3 py-2 text-amber-100/90 hover:bg-amber-400/10"
          >
            导出原始存档文本（自救用）
          </button>
        )}

        <HoldReset
          onDone={() => {
            useGame.getState().hardReset()
            onClose()
          }}
        />
        <div className="text-[11px] leading-relaxed text-white/35">
          Prism Farm 完全单机：无网络请求、无账号。存档在本浏览器 localStorage，导出的 JSON 文件可在任意设备导入恢复。
        </div>
      </div>
    </div>
  )
}
