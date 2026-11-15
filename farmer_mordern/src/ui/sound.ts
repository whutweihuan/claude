import { Howl } from 'howler'
import { getStore } from '../store/gameStore'
import harvestUrl from '../assets/sounds/harvest.wav'
import buyUrl from '../assets/sounds/buy.wav'
import unlockUrl from '../assets/sounds/unlock.wav'
import migrateUrl from '../assets/sounds/migrate.wav'

export type SoundName = 'harvest' | 'buy' | 'unlock' | 'migrate'

// data URI 内联（构建期），运行时零网络；html5 保证 file:// 下解码路径最宽松
const howls: Record<SoundName, Howl> = {
  harvest: new Howl({ src: [harvestUrl], format: ['wav'], html5: true }),
  buy: new Howl({ src: [buyUrl], format: ['wav'], html5: true }),
  unlock: new Howl({ src: [unlockUrl], format: ['wav'], html5: true }),
  migrate: new Howl({ src: [migrateUrl], format: ['wav'], html5: true })
}

/** 默认静音（CLAUDE.md 红线）：muted 时直接返回，不触碰音频子系统 */
export function playSound(name: SoundName): void {
  try {
    const { muted, volume } = getStore().useGame.getState().ui
    if (muted) return
    const h = howls[name]
    h.volume(volume)
    h.play()
  } catch {
    /* 音频不可用时静默：游戏永不因声音出错 */
  }
}
