// 合成 4 个短促音效 wav（44.1kHz 16bit 单声道），零外部素材依赖。
// 运行一次生成 src/assets/sounds/*.wav 并提交产物：node tools/gen-sounds.mjs
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const RATE = 44100
const outDir = join(dirname(fileURLToPath(import.meta.url)), '..', 'src', 'assets', 'sounds')
mkdirSync(outDir, { recursive: true })

function writeWav(path, samples) {
  const n = samples.length
  const buf = Buffer.alloc(44 + n * 2)
  buf.write('RIFF', 0)
  buf.writeUInt32LE(36 + n * 2, 4)
  buf.write('WAVE', 8)
  buf.write('fmt ', 12)
  buf.writeUInt32LE(16, 16)
  buf.writeUInt16LE(1, 20) // PCM
  buf.writeUInt16LE(1, 22) // mono
  buf.writeUInt32LE(RATE, 24)
  buf.writeUInt32LE(RATE * 2, 28)
  buf.writeUInt16LE(2, 32)
  buf.writeUInt16LE(16, 34)
  buf.write('data', 36)
  buf.writeUInt32LE(n * 2, 40)
  for (let i = 0; i < n; i++) {
    const clamped = Math.max(-1, Math.min(1, samples[i] ?? 0))
    buf.writeInt16LE(Math.round(clamped * 32767), 44 + i * 2)
  }
  writeFileSync(path, buf)
  console.log(`${path} ${buf.length} bytes`)
}

function osc(freq, t, type) {
  const ph = (freq * t) % 1
  if (type === 'triangle') return 4 * Math.abs(ph - 0.5) - 1
  return Math.sin(2 * Math.PI * freq * t)
}

function note(f0, f1, dur, type, amp, decay) {
  const n = Math.floor(dur * RATE)
  const out = new Float64Array(n)
  for (let i = 0; i < n; i++) {
    const t = i / RATE
    const f = f0 + (f1 - f0) * (i / n)
    out[i] = osc(f, t, type) * amp * Math.exp(-decay * t)
  }
  return out
}

function mix(...parts) {
  const n = Math.max(...parts.map((p) => p.length))
  const out = new Float64Array(n)
  for (const p of parts) for (let i = 0; i < p.length; i++) out[i] = (out[i] ?? 0) + (p[i] ?? 0)
  return out
}

function seq(...parts) {
  const total = parts.reduce((a, p) => a + p.length, 0)
  const out = new Float64Array(total)
  let off = 0
  for (const p of parts) {
    out.set(p, off)
    off += p.length
  }
  return out
}

// 上滑叮：收获的正反馈
writeWav(join(outDir, 'harvest.wav'), note(620, 1240, 0.18, 'sine', 0.5, 14))
// 闷嗒：购买/扣款
writeWav(join(outDir, 'buy.wav'), note(320, 240, 0.12, 'triangle', 0.5, 22))
// 双音：解锁
writeWav(join(outDir, 'unlock.wav'), seq(note(523, 523, 0.12, 'sine', 0.45, 9), note(784, 784, 0.2, 'sine', 0.45, 8)))
// 上行琶音：迁徙里程碑
writeWav(
  join(outDir, 'migrate.wav'),
  mix(
    seq(new Float64Array(0), note(392, 392, 0.2, 'sine', 0.35, 5), note(523, 523, 0.2, 'sine', 0.35, 5), note(659, 659, 0.2, 'sine', 0.35, 5), note(784, 784, 0.4, 'sine', 0.4, 5)),
    seq(new Float64Array(Math.floor(0.6 * RATE)), note(1568, 1568, 0.4, 'sine', 0.12, 7))
  )
)
