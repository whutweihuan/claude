import { useEffect, useState } from 'react'
import { getStore, startHeartbeat } from './store/gameStore'
import { PlotGrid } from './ui/PlotGrid'
import { formatCoins } from './game/systems/format'

export default function App() {
  const { useGame } = getStore()
  const coins = useGame((s) => s.game.coins)
  const nowTick = useGame((s) => s.ui.nowTick)
  const activeMaps = useGame((s) => s.game.maps)
  const [mapId, setMapId] = useState('garden')
  useEffect(() => startHeartbeat(getStore()), [])

  const unlockedIds = Object.entries(activeMaps)
    .filter(([, m]) => m.unlocked)
    .map(([id]) => id)
  const activeMap = unlockedIds.includes(mapId) ? mapId : (unlockedIds[0] ?? 'garden')

  return (
    <div className="flex h-full flex-col gap-3 p-4">
      <header className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/5 px-5 py-3 backdrop-blur">
        <div className="text-lg font-semibold tracking-widest text-emerald-200/90">Prism Farm · 棱镜农场</div>
        <div className="font-mono text-xl tabular-nums text-amber-200">{formatCoins(coins)}</div>
      </header>
      <nav className="flex gap-2">
        {unlockedIds.map((id) => (
          <button
            key={id}
            type="button"
            onClick={() => setMapId(id)}
            className={[
              'rounded-full border px-4 py-1 text-sm',
              id === activeMap ? 'border-emerald-300/60 bg-emerald-400/10 text-emerald-100' : 'border-white/10 text-white/50'
            ].join(' ')}
          >
            {id}
          </button>
        ))}
      </nav>
      <main className="flex-1 overflow-auto">
        <PlotGrid mapId={activeMap} now={nowTick} />
      </main>
    </div>
  )
}
