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
    renderTimer: null,
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

  function renderFrame(t) {
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

    if (ui.phase === 'train' && ui.train) {
      TigerRender.drawTrain(ctx, ui.train.progress, ui.train.carriages, ui.train.reveal);
    }
    if (ui.phase === 'gate' && ui.gate) {
      TigerRender.drawGateWheel(ctx, ui.gate.wheel, ui.gate.spin, ui.gate.open, ui.gate.done);
    }

    drawParticles(t);
  }

  function draw(t) {
    renderFrame(t);
    requestAnimationFrame(draw);
  }

  function startRenderFallback() {
    if (ui.renderTimer) return;
    ui.renderTimer = setInterval(() => renderFrame(performance.now()), 60);
  }

  function stopRenderFallback() {
    if (!ui.renderTimer) return;
    clearInterval(ui.renderTimer);
    ui.renderTimer = null;
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

  function animateValue(duration, onUpdate) {
    return new Promise((resolve) => {
      const t0 = performance.now();
      let settled = false;
      let lastP = 0;
      let safety = null;

      function finish() {
        if (settled) return;
        settled = true;
        if (safety) clearTimeout(safety);
        onUpdate(1);
        resolve();
      }

      safety = setTimeout(finish, duration + 150);
      function step(now) {
        if (settled) return;
        const raw = (now - t0) / duration;
        const p = Math.max(lastP, Math.min(1, Math.max(0, raw)));
        lastP = p;
        onUpdate(p);
        if (p < 1) requestAnimationFrame(step);
        else finish();
      }
      onUpdate(0);
      requestAnimationFrame(step);
    });
  }

  async function animateTriple(feature, big) {
    const label = big ? '大三元' : '小三元';
    showBanner(label, big);
    showStatus(`${label}！`);
    TigerAudio.fanfare();
    TigerAudio.speak(label);
    ui.winIndices = [];

    for (const item of feature.symbols) {
      ui.winIndices = ui.winIndices.concat(item.indices);
      const pos = lampPosition(item.indices[0]);
      spawnParticles(pos.x, pos.y, big ? 28 : 16);
      TigerAudio.tick(0.85);
      if (item.win > 0) {
        showStatus(`${item.name} ${item.odds}× · +${fmt(item.win)}`);
      } else {
        showStatus(`${item.name} 亮灯，没有押中`);
      }
      renderFrame(performance.now());
      await sleep(FAST ? 90 : 250);
    }

    if (big) {
      app.classList.add('is-shaking');
      setTimeout(() => app.classList.remove('is-shaking'), FAST ? 260 : 520);
      spawnParticles(340, 340, 90);
    }

    if (feature.win > 0) TigerAudio.win();
    showStatus(`${label} · 总奖金 ${fmt(feature.win)}`);
    await sleep(FAST ? 500 : 1200);
    ui.winIndices = [];
    hideBanner();
    renderFrame(performance.now());
  }

  async function animateTrain(feature) {
    showBanner('开火车啦', true);
    showStatus('开火车啦…');
    TigerAudio.whistle();
    setTimeout(() => TigerAudio.speak('开火车啦'), 120);

    ui.phase = 'train';
    ui.train = { progress: 0, reveal: 0, carriages: feature.carriages };
    ui.winIndices = [];

    await animateValue(FAST ? 250 : 700, (p) => {
      ui.train.progress = p;
      renderFrame(performance.now());
    });
    if (DEBUG) els.probe.textContent = `train progress=${ui.train.progress}`;

    for (let i = 0; i < feature.carriages.length; i++) {
      const carriage = feature.carriages[i];
      ui.train.reveal = i + 1;
      if (DEBUG) els.probe.textContent = `train progress=${ui.train.progress} reveal=${ui.train.reveal}`;
      if (carriage.win > 0) {
        ui.winIndices = [carriage.stopIndex];
        const pos = lampPosition(carriage.stopIndex);
        spawnParticles(pos.x, pos.y, 22);
        TigerAudio.win();
        const sym = symbolById[carriage.symbolId];
        showStatus(`第 ${i + 1} 节 · ${sym.name} +${fmt(carriage.win)}`);
      } else {
        ui.winIndices = [];
        TigerAudio.tick(0.2);
        showStatus(`第 ${i + 1} 节 · 空车`);
      }
      renderFrame(performance.now());
      await sleep(FAST ? 160 : 450);
    }

    ui.winIndices = [];
    showStatus(`开火车 · 总奖金 ${fmt(feature.win)}`);
    if (feature.win > 0) {
      TigerAudio.win();
      spawnParticles(340, 592, 50);
    }
    renderFrame(performance.now());
    await sleep(FAST ? 500 : 1200);
    ui.phase = 'idle';
    ui.train = null;
    ui.winIndices = [];
    hideBanner();
    renderFrame(performance.now());
  }

  async function animateGate(feature) {
    showBanner('天门', true);
    showStatus('天门转动中…');
    TigerAudio.fanfare();
    TigerAudio.speak('天门');

    ui.phase = 'gate';
    ui.gate = { wheel: feature.wheel, open: 0, spin: 0, done: false };
    ui.winIndices = [];

    await animateValue(FAST ? 180 : 500, (p) => {
      ui.gate.open = p;
      renderFrame(performance.now());
    });

    await animateValue(FAST ? 500 : 1500, (p) => {
      ui.gate.spin = 1 - Math.pow(1 - p, 3);
      renderFrame(performance.now());
    });

    ui.gate.done = true;
    showStatus(`${feature.wheel.label} ${feature.wheel.multiplier}× · 总奖金 ${fmt(feature.win)}`);
    TigerAudio.win();
    spawnParticles(340, 340, 70);
    renderFrame(performance.now());
    await sleep(FAST ? 600 : 1400);

    ui.phase = 'idle';
    ui.gate = null;
    hideBanner();
    renderFrame(performance.now());
  }

  async function playFeature(feature) {
    startRenderFallback();
    try {
      if (feature.type === 'smallThree' || feature.type === 'bigThree') {
        return await animateTriple(feature, feature.type === 'bigThree');
      }
      if (feature.type === 'train') return await animateTrain(feature);
      if (feature.type === 'gate') return await animateGate(feature);
    } finally {
      stopRenderFallback();
      ui.phase = 'idle';
      ui.train = null;
      ui.gate = null;
    }
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
