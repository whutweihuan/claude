(function () {
  'use strict';

  const params = new URLSearchParams(location.search);
  const FAST = params.get('fast') === '1';
  const DEBUG = params.get('debug') === '1';
  const DEMO = params.get('demo');

  const app = document.getElementById('app');
  const canvas = document.getElementById('board');
  const ctx = canvas.getContext('2d');

  const el = (id) => document.getElementById(id);
  const els = {
    coins: el('led-coins'),
    bet: el('led-bet'),
    win: el('led-win'),
    feature: el('led-feature'),
    betList: el('bet-list'),
    status: el('status'),
    probe: el('debug-probe'),
    start: el('btn-start'),
    coin: el('btn-coin'),
    clear: el('btn-clear'),
    all: el('btn-all'),
    auto: el('btn-auto'),
    rules: el('btn-rules'),
    mute: el('btn-mute'),
    guessPanel: el('guess-panel'),
    guessWin: el('guess-win'),
    guessNote: el('guess-note'),
    guessSmall: el('guess-small'),
    guessBig: el('guess-big'),
    guessCollect: el('guess-collect'),
    banner: el('feature-banner'),
    rulesModal: el('rules-modal'),
    closeRules: el('btn-close-rules'),
    fatal: el('fatal'),
  };

  const game = TigerEngine.createGame();
  const ui = {
    chip: 1,
    auto: false,
    animating: false,
    muted: false,
    litIndex: -1,
    winIndices: [],
    particles: [],
    autoTimer: null,
    guessBusy: false,
    spinCount: 0,
    feature: null,
    phase: 'idle',
    demoAutoCollect: false,
  };
  let state = game.getState();

  const symbolById = {};
  for (const sym of TigerEngine.SYMBOLS) symbolById[sym.id] = sym;

  const ringIndicesBySymbol = {};
  TigerEngine.RING.forEach((id, index) => {
    if (id === 'luck') return;
    if (!ringIndicesBySymbol[id]) ringIndicesBySymbol[id] = [];
    ringIndicesBySymbol[id].push(index);
  });

  function fmt(value) {
    return Math.round(value).toLocaleString('en-US');
  }

  function setLed(node, value) {
    const text = fmt(value);
    node.textContent = text;
    node.style.fontSize = text.length > 7 ? '20px' : text.length > 5 ? '23px' : '26px';
  }

  function showStatus(text) {
    els.status.textContent = text;
  }

  function showFatal(err) {
    console.error(err);
    const message = err && err.message ? err.message : String(err);
    els.fatal.textContent = '脚本错误：' + message;
    els.fatal.classList.remove('hidden');
  }

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

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

  function buildBetRows() {
    els.betList.innerHTML = '';
    const dpr = window.devicePixelRatio || 1;

    for (const sym of TigerEngine.SYMBOLS) {
      const row = document.createElement('div');
      row.className = 'bet-row';
      row.dataset.id = sym.id;

      const icon = document.createElement('canvas');
      icon.className = 'bet-icon';
      icon.width = 30 * dpr;
      icon.height = 30 * dpr;
      icon.style.width = '30px';
      icon.style.height = '30px';
      const ictx = icon.getContext('2d');
      ictx.setTransform(dpr, 0, 0, dpr, 0, 0);
      TigerRender.drawFruit(ictx, sym.id, 15, 15, 24);

      const name = document.createElement('div');
      name.className = 'bet-name';
      name.textContent = sym.name;

      const odds = document.createElement('div');
      odds.className = 'bet-odds';
      odds.textContent = sym.odds + '×';

      const minus = document.createElement('button');
      minus.className = 'bet-btn';
      minus.dataset.act = 'minus';
      minus.textContent = '−';
      minus.setAttribute('aria-label', '减少' + sym.name + '押分');

      const amount = document.createElement('div');
      amount.className = 'bet-amount';
      amount.textContent = '0';

      const plus = document.createElement('button');
      plus.className = 'bet-btn';
      plus.dataset.act = 'plus';
      plus.textContent = '+';
      plus.setAttribute('aria-label', '增加' + sym.name + '押分');

      row.append(icon, name, odds, minus, amount, plus);
      els.betList.appendChild(row);
    }
  }

  function syncUI() {
    state = game.getState();

    setLed(els.coins, state.coins);
    setLed(els.bet, state.totalBet);
    setLed(els.win, state.pendingWin);
    els.feature.textContent = `${state.spinsSinceFeature}/60`;

    for (const sym of TigerEngine.SYMBOLS) {
      const row = els.betList.querySelector(`.bet-row[data-id="${sym.id}"]`);
      if (!row) continue;
      row.querySelector('.bet-amount').textContent = state.bets[sym.id];
      row.classList.toggle('has-bet', state.bets[sym.id] > 0);
    }

    const busy = ui.animating;
    els.start.disabled = busy || state.pendingWin > 0 || !state.canSpin;
    els.coin.disabled = busy;
    els.clear.disabled = busy || state.pendingWin > 0;
    els.all.disabled = busy || state.pendingWin > 0;
    els.auto.classList.toggle('is-active', ui.auto);
    els.mute.textContent = ui.muted ? '静音' : '音效';
    els.mute.classList.toggle('is-active', ui.muted);

    const betLocked = busy || state.pendingWin > 0;
    document.querySelectorAll('.bet-btn').forEach((btn) => {
      btn.disabled = betLocked;
    });

    document.querySelectorAll('.chip').forEach((chip) => {
      chip.classList.toggle('is-active', Number(chip.dataset.chip) === ui.chip);
    });
  }

  function setChip(unit) {
    ui.chip = unit;
    TigerAudio.init();
    TigerAudio.click();
    syncUI();
  }

  function betError(code) {
    if (code === 'ROUND_ACTIVE') return '本局还没收分';
    if (code === 'MAX_BET') return '单门最多 99 分';
    if (code === 'INSUFFICIENT_COINS') return '金币不够，先投币';
    return '押分失败';
  }

  function addBet(symbolId, delta) {
    if (ui.animating) return;
    const result = game.bet(symbolId, delta);
    if (!result.ok) {
      showStatus(betError(result.error));
      return;
    }
    TigerAudio.init();
    TigerAudio.click();
    syncUI();
  }

  function insertCoin(amount = 100) {
    if (ui.animating) return;
    const result = game.insertCoin(amount);
    if (!result.ok) return;
    TigerAudio.init();
    TigerAudio.coin();
    showStatus(`投币 +${amount}`);
    syncUI();
  }

  function clearBets() {
    if (ui.animating) return;
    const result = game.clearBets();
    if (!result.ok) {
      showStatus(betError(result.error));
      return;
    }
    TigerAudio.click();
    showStatus('已清空押分');
    syncUI();
  }

  function betAll() {
    if (ui.animating) return;
    const result = game.betAll(ui.chip);
    if (!result.ok) {
      showStatus(betError(result.error));
      return;
    }
    TigerAudio.click();
    showStatus(result.added > 0 ? `全押 ${result.added} 分` : '金币不足');
    syncUI();
  }

  function lampPosition(index) {
    const angle = -Math.PI / 2 + (index * Math.PI * 2) / 24;
    return {
      x: 340 + Math.cos(angle) * 255,
      y: 340 + Math.sin(angle) * 255,
    };
  }

  function spawnParticles(x, y, count) {
    const now = performance.now();
    const colors = ['#ffc857', '#ff6a3d', '#7dffa0', '#4de1ff', '#fff0a8'];
    for (let i = 0; i < count; i++) {
      ui.particles.push({
        x,
        y,
        vx: (Math.random() - 0.5) * 520,
        vy: -Math.random() * 520 - 80,
        born: now,
        life: 800 + Math.random() * 900,
        size: 3 + Math.random() * 4,
        color: colors[Math.floor(Math.random() * colors.length)],
      });
    }
  }

  function drawParticles(now) {
    if (!ui.particles.length) return;
    const gravity = 900;
    ui.particles = ui.particles.filter((p) => now - p.born < p.life);
    for (const p of ui.particles) {
      const age = (now - p.born) / 1000;
      const alpha = Math.max(0, 1 - (now - p.born) / p.life);
      const x = p.x + p.vx * age;
      const y = p.y + p.vy * age + 0.5 * gravity * age * age;
      ctx.globalAlpha = alpha;
      ctx.fillStyle = p.color;
      ctx.fillRect(x - p.size / 2, y - p.size / 2, p.size, p.size);
    }
    ctx.globalAlpha = 1;
  }

  function draw(t) {
    TigerRender.drawBoard(ctx, {
      ring: TigerEngine.RING,
      symbols: TigerEngine.SYMBOLS,
      bets: state.bets,
      litIndex: ui.litIndex,
      winIndices: ui.winIndices,
      feature: ui.feature,
      phase: ui.phase,
      time: t,
    });
    drawParticles(t);
    requestAnimationFrame(draw);
  }

  function animateSpin(result) {
    return new Promise((resolve) => {
      const start = ui.litIndex;
      const target = result.stopIndex;
      const laps = 2;
      const offset = (target - start + 24) % 24;
      const totalSteps = laps * 24 + offset;
      const duration = FAST ? 900 : 2600;
      const t0 = performance.now();
      let lastStep = -1;
      let settled = false;

      function finish() {
        if (settled) return;
        settled = true;
        clearTimeout(safety);
        ui.litIndex = target;
        resolve();
      }

      // 后台标签页 / 无头浏览器可能不派发 rAF，用定时器兜底。
      const safety = setTimeout(finish, duration + 250);

      function stepFrame(now) {
        const p = Math.min(1, (now - t0) / duration);
        const eased = 1 - Math.pow(1 - p, 3);
        const step = Math.floor(eased * totalSteps);
        if (step !== lastStep) {
          lastStep = step;
          ui.litIndex = (start + step) % 24;
          TigerAudio.tick(p);
        }
        if (p < 1) {
          requestAnimationFrame(stepFrame);
        } else {
          finish();
        }
      }
      requestAnimationFrame(stepFrame);
    });
  }

  function showBanner(text, big) {
    els.banner.textContent = text;
    els.banner.classList.toggle('is-big', !!big);
    els.banner.classList.remove('hidden');
  }

  function hideBanner() {
    els.banner.classList.add('hidden');
    els.banner.classList.remove('is-big');
  }

  async function playFeature(feature) {
    const label = feature.type === 'train' ? '开火车啦' : feature.name;
    const big = feature.type === 'bigThree' || feature.type === 'gate';
    showBanner(label, big);

    if (feature.type === 'train') {
      TigerAudio.whistle();
      setTimeout(() => TigerAudio.speak('开火车啦'), 120);
    } else if (feature.type === 'gate') {
      TigerAudio.fanfare();
      TigerAudio.speak('天门');
    } else if (feature.type === 'bigThree') {
      TigerAudio.fanfare();
      TigerAudio.speak('大三元');
    } else {
      TigerAudio.win();
      TigerAudio.speak('小三元');
    }

    if (feature.type === 'gate') {
      showStatus(`${feature.wheel.label} ${feature.wheel.multiplier}× · 总奖金 ${fmt(feature.win)}`);
    } else if (feature.type === 'train') {
      const hits = feature.carriages.filter((carriage) => carriage.win > 0).length;
      showStatus(`开火车 ${hits} 节中奖 · 总奖金 ${fmt(feature.win)}`);
    } else {
      showStatus(`${feature.name} · 总奖金 ${fmt(feature.win)}`);
    }

    spawnParticles(340, 340, big ? 90 : 55);
    await sleep(FAST ? 600 : 1800);
    hideBanner();
  }

  async function finishRound(result) {
    if (result.kind === 'symbol') {
      if (result.win > 0) {
        const sym = symbolById[result.symbolId];
        ui.winIndices = (ringIndicesBySymbol[result.symbolId] || []).slice();
        TigerAudio.win();
        showStatus(`${sym.name} ${sym.odds}× · 赢 ${fmt(result.win)}`);
        const pos = lampPosition(result.stopIndex);
        spawnParticles(pos.x, pos.y, 40);
        await sleep(FAST ? 450 : 900);
        ui.winIndices = [];
      } else {
        TigerAudio.lose();
        showStatus('跑空，再来一局');
        await sleep(FAST ? 150 : 350);
      }
    } else if (result.kind === 'luck') {
      TigerAudio.lose();
      showStatus('跑空，再来一局');
      await sleep(FAST ? 150 : 350);
    } else if (result.kind === 'feature') {
      await playFeature(result.feature);
    }

    ui.animating = false;
    syncUI();
    if (result.win > 0) {
      showGuessOrCollect();
    } else {
      scheduleAuto();
    }
  }

  function startSpin() {
    if (ui.animating) return;
    state = game.getState();
    if (state.pendingWin > 0) return;
    if (!state.canSpin) {
      showStatus(state.totalBet <= 0 ? '先押分再开始' : '金币不足，先投币');
      return;
    }

    TigerAudio.init();
    let result;
    try {
      result = game.spin();
    } catch (err) {
      showStatus(err && err.message === 'ROUND_ACTIVE' ? '还没收分' : '开局失败');
      return;
    }

    ui.spinCount += 1;
    ui.animating = true;
    ui.winIndices = [];
    hideGuess();
    hideBanner();
    showStatus('跑灯中…');
    syncUI();

    animateSpin(result)
      .then(() => finishRound(result))
      .catch((err) => {
        ui.animating = false;
        showFatal(err);
        syncUI();
      });
  }

  function updateGuessNote(count) {
    els.guessNote.textContent = `剩余 ${Math.max(0, 3 - count)} 次 · 开 7 通杀`;
  }

  function showGuessOrCollect() {
    state = game.getState();
    if (state.pendingWin <= 0) {
      hideGuess();
      scheduleAuto();
      return;
    }
    if (ui.demoAutoCollect) {
      ui.demoAutoCollect = false;
      collectWin();
      return;
    }
    if (ui.auto) {
      collectWin();
      return;
    }

    els.guessWin.textContent = fmt(state.pendingWin);
    updateGuessNote(state.guessCount);
    els.guessPanel.classList.remove('hidden');
    ui.guessBusy = false;
    syncUI();
  }

  function hideGuess() {
    els.guessPanel.classList.add('hidden');
  }

  async function doGuess(choice) {
    if (ui.guessBusy) return;
    if (els.guessPanel.classList.contains('hidden')) return;

    ui.guessBusy = true;
    let result;
    try {
      result = game.guess(choice);
    } catch (err) {
      ui.guessBusy = false;
      showStatus('猜大小失败');
      return;
    }

    TigerAudio.init();
    els.guessWin.textContent = fmt(result.pendingWin);
    updateGuessNote(result.guessCount);
    showStatus(`开出 ${result.number} · ${result.correct ? '猜对了！' : '猜错了'}`);
    if (result.correct) TigerAudio.win();
    else TigerAudio.lose();
    syncUI();

    await sleep(FAST ? 350 : 900);
    ui.guessBusy = false;

    if (result.autoCollected) {
      hideGuess();
      showStatus(`自动收分 +${fmt(result.collected)}`);
      syncUI();
      if (result.jackpot) celebrateJackpot();
      scheduleAuto();
      return;
    }

    if (result.pendingWin <= 0) {
      hideGuess();
      syncUI();
      scheduleAuto();
      return;
    }

    syncUI();
  }

  function collectWin() {
    const result = game.collect();
    if (result.collected > 0) {
      TigerAudio.coin();
      showStatus(`收分 +${fmt(result.collected)}`);
    }
    hideGuess();
    syncUI();
    if (result.jackpot) celebrateJackpot();
    scheduleAuto();
  }

  function celebrateJackpot() {
    showBanner('爆 机 ！', true);
    TigerAudio.fanfare();
    TigerAudio.speak('爆机');
    spawnParticles(340, 340, 160);
    showStatus('爆机！金币不重置，继续玩');
    setTimeout(() => hideBanner(), FAST ? 1200 : 2600);
  }

  function scheduleAuto() {
    if (!ui.auto) return;
    if (ui.autoTimer) clearTimeout(ui.autoTimer);
    ui.autoTimer = setTimeout(() => {
      ui.autoTimer = null;
      if (!ui.auto) return;
      state = game.getState();
      if (state.pendingWin > 0) {
        collectWin();
        return;
      }
      if (!state.canSpin) {
        ui.auto = false;
        showStatus('金币不足，自动模式停止');
        syncUI();
        return;
      }
      startSpin();
    }, FAST ? 300 : 1200);
  }

  function toggleAuto() {
    ui.auto = !ui.auto;
    TigerAudio.init();
    TigerAudio.click();

    if (ui.auto) {
      showStatus('自动模式开启');
      state = game.getState();
      if (state.pendingWin > 0) {
        collectWin();
        return;
      }
      if (!ui.animating) {
        if (state.canSpin) startSpin();
        else {
          ui.auto = false;
          showStatus('先投币并押分');
        }
      }
    } else {
      if (ui.autoTimer) {
        clearTimeout(ui.autoTimer);
        ui.autoTimer = null;
      }
      showStatus('自动模式停止');
    }
    syncUI();
  }

  function toggleMute() {
    ui.muted = !ui.muted;
    TigerAudio.setMuted(ui.muted);
    if (!ui.muted) {
      TigerAudio.init();
      TigerAudio.click();
    }
    showStatus(ui.muted ? '已静音' : '音效已开启');
    syncUI();
  }

  function openRules() {
    if (ui.auto) toggleAuto();
    TigerAudio.click();
    els.rulesModal.classList.remove('hidden');
  }

  function closeRules() {
    TigerAudio.click();
    els.rulesModal.classList.add('hidden');
  }

  function runDemo(name) {
    if (name === 'jackpot') {
      game.insertCoin(99999 - game.getState().coins);
      game.betAll(1);
      game.forceNextSymbol('bar');
      ui.demoAutoCollect = true;
      syncUI();
      startSpin();
      return;
    }

    insertCoin(100000);
    betAll(1);

    if (name === 'spin') {
      startSpin();
    } else if (name === 'smallThree' || name === 'bigThree' || name === 'train' || name === 'gate') {
      game.forceNextFeature(name);
      startSpin();
    } else if (name === 'guess') {
      game.forceNextSymbol('banana');
      startSpin();
    } else if (name === 'doubleStart') {
      startSpin();
      startSpin();
      setTimeout(() => {
        els.probe.textContent = `doubleStart spins=${ui.spinCount}`;
        showStatus(`doubleStart spins=${ui.spinCount}（应为 1）`);
      }, 300);
    }
  }

  els.start.addEventListener('click', startSpin);
  els.coin.addEventListener('click', () => insertCoin(100));
  els.clear.addEventListener('click', clearBets);
  els.all.addEventListener('click', betAll);
  els.auto.addEventListener('click', toggleAuto);
  els.rules.addEventListener('click', openRules);
  els.closeRules.addEventListener('click', closeRules);
  els.mute.addEventListener('click', toggleMute);
  els.guessSmall.addEventListener('click', () => doGuess('small'));
  els.guessBig.addEventListener('click', () => doGuess('big'));
  els.guessCollect.addEventListener('click', collectWin);

  document.querySelectorAll('.chip').forEach((chip) => {
    chip.addEventListener('click', () => setChip(Number(chip.dataset.chip)));
  });

  els.betList.addEventListener('click', (event) => {
    const button = event.target.closest('button[data-act]');
    if (!button) return;
    const row = button.closest('.bet-row');
    if (!row) return;
    addBet(row.dataset.id, button.dataset.act === 'plus' ? ui.chip : -ui.chip);
  });

  window.addEventListener('pointerdown', () => TigerAudio.init(), { once: true });
  window.addEventListener('resize', fit);

  window.addEventListener('keydown', (event) => {
    TigerAudio.init();

    if (event.key === 'F9') {
      event.preventDefault();
      TigerAudio.demo();
      return;
    }

    if (!els.rulesModal.classList.contains('hidden')) {
      if (event.key === 'Escape') closeRules();
      return;
    }

    const tag = event.target && event.target.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA') return;

    if (event.code === 'Space') {
      event.preventDefault();
      startSpin();
    } else if (event.key === 'c' || event.key === 'C') {
      insertCoin(100);
    } else if (event.key === 'x' || event.key === 'X') {
      clearBets();
    } else if (event.key === 'm' || event.key === 'M') {
      toggleMute();
    }
  });

  window.addEventListener('error', (event) => {
    showFatal(event.error || event.message);
  });
  window.addEventListener('unhandledrejection', (event) => {
    showFatal(event.reason);
  });

  if (DEBUG) {
    window.__tiger = { game, ui, startSpin, syncUI, doGuess, collectWin };
  }

  buildBetRows();
  fit();
  syncUI();
  requestAnimationFrame(draw);

  if (DEMO) {
    setTimeout(() => runDemo(DEMO), 300);
  }
})();
