import type { CropDef } from '../game/types'

const STAGE_SCALE = [0.3, 0.55, 0.8, 1] as const

function Sprout({ leaf }: { leaf: string }) {
  return (
    <g>
      <path d="M32 64 L32 52" stroke={leaf} strokeWidth="2.5" strokeLinecap="round" />
      <ellipse cx="27" cy="50" rx="6" ry="3.2" fill={leaf} transform="rotate(-24 27 50)" />
      <ellipse cx="37" cy="50" rx="6" ry="3.2" fill={leaf} transform="rotate(24 37 50)" />
    </g>
  )
}

function Form({ crop }: { crop: CropDef }) {
  const { body, accent, leaf, form } = crop.sprite
  switch (form) {
    case 'stem':
      return (
        <g>
          <path d="M32 64 L32 24" stroke={leaf} strokeWidth="3" strokeLinecap="round" />
          <ellipse cx="32" cy="22" rx="9" ry="12" fill={body} />
          <path d="M32 46 Q20 42 16 32" stroke={leaf} strokeWidth="2.5" fill="none" strokeLinecap="round" />
          <circle cx="32" cy="16" r="3" fill={accent} />
        </g>
      )
    case 'bush':
      return (
        <g>
          <circle cx="22" cy="52" r="11" fill={body} />
          <circle cx="42" cy="52" r="11" fill={body} />
          <circle cx="32" cy="40" r="13" fill={body} />
          <circle cx="27" cy="38" r="3" fill={accent} />
          <circle cx="40" cy="48" r="3" fill={accent} />
          <circle cx="33" cy="52" r="2.5" fill={accent} />
        </g>
      )
    case 'flower':
      return (
        <g>
          <path d="M32 64 L32 34" stroke={leaf} strokeWidth="3" strokeLinecap="round" />
          <path d="M32 52 Q22 50 18 42" stroke={leaf} strokeWidth="2.5" fill="none" strokeLinecap="round" />
          {[0, 60, 120, 180, 240, 300].map((deg) => (
            <ellipse
              key={deg}
              cx="32"
              cy="20"
              rx="5.5"
              ry="9"
              fill={body}
              transform={`rotate(${deg} 32 28)`}
              opacity="0.92"
            />
          ))}
          <circle cx="32" cy="28" r="6" fill={accent} />
        </g>
      )
    case 'tree':
      return (
        <g>
          <rect x="30" y="38" width="4.5" height="26" rx="2" fill="#6b4f3a" />
          <circle cx="32" cy="26" r="17" fill={body} />
          <circle cx="24" cy="22" r="3.2" fill={accent} />
          <circle cx="38" cy="26" r="3.2" fill={accent} />
          <circle cx="31" cy="34" r="3.2" fill={accent} />
          <path d="M32 40 Q24 38 20 32" stroke="#5d7d3a" strokeWidth="2" fill="none" />
        </g>
      )
    case 'vine':
      return (
        <g>
          <path d="M12 58 C 20 38, 44 38, 52 58" stroke={leaf} strokeWidth="3" fill="none" strokeLinecap="round" />
          <ellipse cx="22" cy="46" rx="6" ry="7.5" fill={body} />
          <ellipse cx="34" cy="42" rx="7" ry="8.5" fill={body} />
          <ellipse cx="45" cy="48" rx="5.5" ry="7" fill={body} />
          <circle cx="34" cy="42" r="2.4" fill={accent} />
          <circle cx="22" cy="46" r="2" fill={accent} />
        </g>
      )
    case 'grain':
      return (
        <g>
          {[22, 32, 42].map((x, i) => (
            <g key={x}>
              <path d={`M${x} 64 L${x + (i - 1) * 3} ${20 + i * 4}`} stroke={leaf} strokeWidth="2.4" fill="none" strokeLinecap="round" />
              {[0, 1, 2, 3].map((j) => (
                <ellipse
                  key={j}
                  cx={x + (i - 1) * (0.8 * j)}
                  cy={26 + j * 7 + i * 3}
                  rx="3.4"
                  ry="4.6"
                  fill={body}
                  opacity={j === 3 && i === 1 ? 0.55 : 0.95}
                />
              ))}
            </g>
          ))}
          <circle cx="32" cy="24" r="2.6" fill={accent} />
        </g>
      )
    case 'fantasy':
      return (
        <g>
          <path d="M32 64 L32 40" stroke={leaf} strokeWidth="3" strokeLinecap="round" />
          <polygon points="32,8 44,26 32,44 20,26" fill={body} opacity="0.9" />
          <polygon points="32,16 38,26 32,36 26,26" fill={accent} opacity="0.95" />
          <circle cx="20" cy="14" r="1.8" fill={accent} />
          <circle cx="45" cy="18" r="1.4" fill={accent} />
          <circle cx="42" cy="8" r="1" fill={body} />
        </g>
      )
  }
}

/**
 * 参数化作物精灵（§7.2）：form × stage × 配色三元组生成，
 * 新作物零美术成本；stage 3 配合地块辉光表示"可收获"。
 */
export function PlantSprite({ crop, stage }: { crop: CropDef; stage: 0 | 1 | 2 | 3 }) {
  const s = STAGE_SCALE[stage] ?? 1
  return (
    <svg viewBox="0 0 64 72" className="h-full w-full" aria-label={crop.name}>
      <ellipse cx="32" cy="66" rx="22" ry="5" fill="#241b16" />
      {stage <= 0 ? (
        <Sprout leaf={crop.sprite.leaf} />
      ) : (
        <g transform={`translate(32 64) scale(${s}) translate(-32 -64)`}>
          <Form crop={crop} />
        </g>
      )}
    </svg>
  )
}
