import { useEffect, useState } from 'react'
import { getStore, startHeartbeat } from './store/gameStore'
import { PlotGrid } from './ui/PlotGrid'
import { HUD } from './ui/HUD'
import { MapRail } from './ui/MapRail'
import { ShopPanel } from './ui/ShopPanel'
import { OfflineReportModal } from './ui/OfflineReport'
import { SettingsPanel } from './ui/SettingsPanel'
import { BackgroundCanvas } from './ui/BackgroundCanvas'
import { buildIndex } from './game/content'
import type { PlotState } from './game/types'

const CONTENT = buildIndex()

export default function App() {
  const { useGame } = getStore()
  const nowTick = useGame((s) => s.ui.nowTick)
  const maps = useGame((s) => s.game.maps)
  const loadError = useGame((s) => s.ui.loadError)
  const [mapId, setMapId] = useState('garden')
  const [selectedPlot, setSelectedPlot] = useState<string | null>(null)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [shopOpen, setShopOpen] = useState(false)
  useEffect(() => startHeartbeat(getStore()), [])

  const unlockedIds = Object.entries(maps)
    .filter(([, m]) => m.unlocked)
    .map(([id]) => id)
  const activeMap = unlockedIds.includes(mapId) ? mapId : (unlockedIds[0] ?? 'garden')

  function handlePlotClick(plot: PlotState) {
    setSelectedPlot(plot.id)
  }

  const hue = CONTENT.mapById[activeMap]?.hue ?? 95

  return (
    <div className="flex h-full flex-col gap-3 p-4">
      <BackgroundCanvas hue={hue} />
      <HUD onOpenSettings={() => setSettingsOpen(true)} />
      {loadError && (
        <div className="rounded-xl border border-rose-400/40 bg-rose-500/10 px-4 py-2 text-sm text-rose-100">
          {loadError}
        </div>
      )}
      <div className="flex min-h-0 flex-1 flex-col gap-3 lg:flex-row">
        <MapRail
          active={activeMap}
          onPick={(id) => {
            setMapId(id)
            setSelectedPlot(null)
          }}
        />
        <main className="min-w-0 flex-1 overflow-auto">
          <PlotGrid mapId={activeMap} now={nowTick} onPlotClick={handlePlotClick} />
        </main>
        <ShopPanel
          mapId={activeMap}
          selectedPlotId={selectedPlot}
          now={nowTick}
          onMigrated={(next) => {
            setMapId(next)
            setShopOpen(false)
          }}
          mobileOpen={shopOpen}
          onCloseMobile={() => setShopOpen(false)}
        />
        <button
          type="button"
          onClick={() => setShopOpen((v) => !v)}
          className="fixed bottom-3 right-3 z-50 rounded-full border border-amber-300/50 bg-amber-400/15 px-4 py-2.5 text-sm text-amber-100 shadow-lg backdrop-blur lg:hidden"
        >
          {shopOpen ? '收起商店' : '商店 · 详情'}
        </button>
      </div>
      <OfflineReportModal />
      <SettingsPanel open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  )
}
