(function () {
  'use strict';

  const app = document.getElementById('app');
  const canvas = document.getElementById('board');
  const ctx = canvas.getContext('2d');

  function fit() {
    const scale = Math.min(window.innerWidth / 1280, window.innerHeight / 800, 1.25);
    app.style.transform = `scale(${scale})`;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = 680 * dpr;
    canvas.height = 680 * dpr;
    canvas.style.width = '680px';
    canvas.style.height = '680px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function frame(t) {
    TigerRender.drawBoard(ctx, {
      ring: TigerEngine.RING,
      symbols: TigerEngine.SYMBOLS,
      bets: {},
      litIndex: -1,
      winIndices: [],
      feature: null,
      phase: 'idle',
      time: t,
    });
    requestAnimationFrame(frame);
  }

  window.addEventListener('resize', fit);
  window.addEventListener('error', (event) => {
    const el = document.getElementById('fatal');
    el.textContent = '脚本错误：' + event.message;
    el.classList.remove('hidden');
  });

  window.addEventListener('pointerdown', () => TigerAudio.init(), { once: true });
  window.addEventListener('keydown', (event) => {
    TigerAudio.init();
    if (event.key === 'F9') {
      event.preventDefault();
      TigerAudio.demo();
    }
  });

  fit();
  requestAnimationFrame(frame);
})();
