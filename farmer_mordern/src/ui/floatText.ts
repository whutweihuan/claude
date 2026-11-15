/** 收获/购买飘字：命令式挂 DOM，不进 React 树（§7.1 避免 80 格 re-render 风暴） */
export function spawnFloat(x: number, y: number, text: string, tone: 'gain' | 'cost' | 'info' = 'gain'): void {
  const el = document.createElement('div')
  el.className = `float-plus float-tone-${tone}`
  el.textContent = text
  el.style.left = `${x}px`
  el.style.top = `${y}px`
  document.body.appendChild(el)
  window.setTimeout(() => el.remove(), 950)
}
