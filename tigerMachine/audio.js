(function (root) {
  'use strict';

  let ctx = null;
  let master = null;
  let muted = false;

  function ensure() {
    if (!ctx) {
      const AC = root.AudioContext || root.webkitAudioContext;
      if (!AC) return null;
      ctx = new AC();
      master = ctx.createGain();
      master.gain.value = 0.22;
      master.connect(ctx.destination);
    }
    if (ctx.state === 'suspended') {
      ctx.resume().catch(() => {});
    }
    return ctx;
  }

  function beep(freq, duration, type, offset, gain) {
    if (muted) return;
    const ac = ensure();
    if (!ac) return;
    const t0 = ac.currentTime + (offset || 0);
    const osc = ac.createOscillator();
    const g = ac.createGain();
    osc.type = type || 'square';
    osc.frequency.setValueAtTime(freq, t0);
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(gain == null ? 0.4 : gain, t0 + 0.012);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + duration);
    osc.connect(g);
    g.connect(master);
    osc.start(t0);
    osc.stop(t0 + duration + 0.03);
  }

  function init() {
    ensure();
  }

  function setMuted(value) {
    muted = !!value;
    if (muted && root.speechSynthesis) root.speechSynthesis.cancel();
  }

  function isMuted() {
    return muted;
  }

  function click() {
    beep(520, 0.045, 'square', 0, 0.22);
  }

  function coin() {
    beep(1180, 0.065, 'square', 0, 0.34);
    beep(1760, 0.11, 'sine', 0.07, 0.28);
  }

  function tick(progress) {
    const p = Math.max(0, Math.min(1, progress || 0));
    beep(180 + p * 720, 0.025, 'square', 0, 0.16);
  }

  function win() {
    [523.25, 659.25, 783.99].forEach((freq, i) => {
      beep(freq, 0.18, 'triangle', i * 0.085, 0.35);
    });
  }

  function lose() {
    beep(330, 0.16, 'sawtooth', 0, 0.28);
    beep(220, 0.20, 'sawtooth', 0.13, 0.26);
  }

  function whistle() {
    if (muted) return;
    const ac = ensure();
    if (!ac) return;
    const t0 = ac.currentTime;
    const osc = ac.createOscillator();
    const g = ac.createGain();
    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(320, t0);
    osc.frequency.exponentialRampToValueAtTime(980, t0 + 0.28);
    osc.frequency.exponentialRampToValueAtTime(520, t0 + 0.65);
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(0.30, t0 + 0.03);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.72);
    osc.connect(g);
    g.connect(master);
    osc.start(t0);
    osc.stop(t0 + 0.75);
  }

  function fanfare() {
    const first = [523.25, 659.25, 783.99];
    const second = [659.25, 783.99, 1046.5];
    first.forEach((freq) => beep(freq, 0.30, 'triangle', 0, 0.22));
    second.forEach((freq) => beep(freq, 0.45, 'triangle', 0.30, 0.20));
  }

  function speak(text) {
    if (muted) return;
    if (!root.speechSynthesis || typeof root.SpeechSynthesisUtterance !== 'function') return;
    try {
      root.speechSynthesis.cancel();
      const utter = new root.SpeechSynthesisUtterance(String(text));
      utter.lang = 'zh-CN';
      utter.rate = 1.1;
      utter.volume = 0.9;
      root.speechSynthesis.speak(utter);
    } catch (err) {
      // 语音不可用时静默降级
    }
  }

  function demo() {
    init();
    coin();
    setTimeout(win, 280);
    setTimeout(lose, 800);
    setTimeout(whistle, 1150);
    setTimeout(fanfare, 1700);
    speak('开火车啦');
  }

  root.TigerAudio = {
    init,
    setMuted,
    isMuted,
    click,
    coin,
    tick,
    win,
    lose,
    whistle,
    fanfare,
    speak,
    demo,
  };
})(typeof window !== 'undefined' ? window : globalThis);
