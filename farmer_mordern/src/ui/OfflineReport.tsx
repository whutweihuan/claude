import { motion } from 'framer-motion'
import { getStore } from '../store/gameStore'
import { buildIndex } from '../game/content'
import { formatCoins, formatDuration } from '../game/systems/format'

const CONTENT = buildIndex()

/** 离线收获报告：收益已入账，纯仪式感展示（§4.5） */
export function OfflineReportModal() {
  const { useGame } = getStore()
  const report = useGame((s) => s.ui.report)
  if (!report) return null
  const entries = Object.entries(report.perMap).filter(([, v]) => v.cycles > 0)
  return (
    <motion.div
      className="fixed inset-0 z-50 grid place-items-center bg-black/60 backdrop-blur-sm"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      onClick={() => useGame.getState().dismissReport()}
    >
      <motion.div
        className="w-[min(92vw,460px)] rounded-2xl border border-white/15 bg-slate-900/90 p-6 shadow-2xl"
        initial={{ scale: 0.92, y: 18 }}
        animate={{ scale: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 260, damping: 22 }}
      >
        <div className="mb-1 text-sm text-white/50">欢迎回来 · 离开了 {formatDuration(report.elapsedMs)}</div>
        <div className="mb-4 text-3xl font-bold text-amber-200">
          +{formatCoins(report.gained)}
        </div>
        {entries.length > 0 ? (
          <ul className="mb-4 space-y-1 text-sm text-white/70">
            {entries.map(([mapId, v]) => (
              <li key={mapId} className="flex justify-between">
                <span>{CONTENT.mapById[mapId]?.name ?? mapId}</span>
                <span>
                  {v.cycles} 轮收获 · <span className="font-mono text-amber-200/80">{formatCoins(v.gained)}</span>
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="mb-4 text-sm text-white/45">作物们安静地长到了成熟，等你亲手收割。</div>
        )}
        <div className="text-center text-xs text-white/35">点击任意处继续</div>
      </motion.div>
    </motion.div>
  )
}
