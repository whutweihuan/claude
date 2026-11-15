import { useEffect, useRef } from 'react'

interface Particle {
  x: number
  y: number
  r: number
  vy: number
  vx: number
  phase: number
  speed: number
}

/**
 * 环境粒子层（§7.2）：纯装饰、零游戏逻辑；
 * pointer-events:none + 独立 canvas，不触发地块重渲染；tab 隐藏自动暂停。
 */
export function BackgroundCanvas({ hue }: { hue: number }) {
  const ref = useRef<HTMLCanvasElement>(null)
  const hueRef = useRef(hue)
  hueRef.current = hue

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    let raf = 0
    let running = true
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    const parts: Particle[] = []

    function seed() {
      parts.length = 0
      const n = window.innerWidth < 640 ? 24 : 45
      for (let i = 0; i < n; i++) {
        parts.push({
          x: Math.random() * canvas!.clientWidth,
          y: Math.random() * canvas!.clientHeight,
          r: 0.8 + Math.random() * 2.2,
          vy: -(4 + Math.random() * 10) / 60,
          vx: (Math.random() - 0.5) * 0.3,
          phase: Math.random() * Math.PI * 2,
          speed: 0.5 + Math.random() * 1.5
        })
      }
    }

    function resize() {
      if (!canvas) return
      canvas.width = canvas.clientWidth * dpr
      canvas.height = canvas.clientHeight * dpr
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    let last = performance.now()
    function frame(t: number) {
      if (!running) return
      const dt = Math.min(0.05, (t - last) / 1000)
      last = t
      const w = canvas!.clientWidth
      const h = canvas!.clientHeight
      ctx!.clearRect(0, 0, w, h)
      for (const p of parts) {
        p.y += p.vy * dt * 60
        p.x += p.vx * dt * 60 + Math.sin(t / 1400 + p.phase) * 0.12
        p.phase += dt * p.speed
        if (p.y < -6) {
          p.y = h + 6
          p.x = Math.random() * w
        }
        const tw = 0.35 + 0.3 * Math.sin(p.phase * 2)
        ctx!.beginPath()
        ctx!.fillStyle = `hsl(${hueRef.current} 80% 72% / ${tw.toFixed(3)})`
        ctx!.arc(p.x, p.y, p.r, 0, Math.PI * 2)
        ctx!.fill()
      }
      raf = requestAnimationFrame(frame)
    }

    function onVisibility() {
      if (document.hidden) {
        running = false
        cancelAnimationFrame(raf)
      } else if (!running) {
        running = true
        last = performance.now()
        raf = requestAnimationFrame(frame)
      }
    }

    resize()
    seed()
    raf = requestAnimationFrame(frame)
    window.addEventListener('resize', resize)
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      running = false
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', resize)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [])

  return <canvas ref={ref} className="pointer-events-none fixed inset-0 -z-10 h-full w-full" aria-hidden />
}
