import { buildIndex } from '../game/content'
import { PlotCell } from './PlotCell'

const CONTENT = buildIndex()

/** 当前图的地块网格：2 行自适应列（§7.1） */
export function PlotGrid({ mapId, now }: { mapId: string; now: number }) {
  const mapDef = CONTENT.mapById[mapId]
  if (!mapDef) return null
  const cols = mapDef.plotCount >= 16 ? 6 : 4
  return (
    <div
      className="mx-auto grid w-full max-w-[720px] gap-2"
      style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}
    >
      {Array.from({ length: mapDef.plotCount }, (_, n) => (
        <PlotCell key={`${mapId}:${n}`} mapId={mapId} n={n} now={now} />
      ))}
    </div>
  )
}
