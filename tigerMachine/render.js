(function (root) {
  'use strict';

  const CENTER = 340;
  const RADIUS = 255;
  const LAMP = 60;
  const GATE_SEGMENTS = [
    { label: '小天门', multiplier: 5, color: '#4de1ff', center: -Math.PI / 2 },
    { label: '天门', multiplier: 10, color: '#ffc857', center: Math.PI / 6 },
    { label: '大天门', multiplier: 50, color: '#ff4d3d', center: (Math.PI * 5) / 6 },
  ];
  const COLORS = {
    gold: '#ffc857',
    goldDeep: '#9c6512',
    red: '#ff4d3d',
    cyan: '#4de1ff',
    green: '#58e06a',
    cream: '#f4e3c2',
    dark: '#0b0503',
  };

  function roundRect(ctx, x, y, w, h, r) {
    const radius = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.lineTo(x + w - radius, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + radius);
    ctx.lineTo(x + w, y + h - radius);
    ctx.quadraticCurveTo(x + w, y + h, x + w - radius, y + h);
    ctx.lineTo(x + radius, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - radius);
    ctx.lineTo(x, y + radius);
    ctx.quadraticCurveTo(x, y, x + radius, y);
    ctx.closePath();
  }

  function star(ctx, cx, cy, outer, inner, points, fill, stroke) {
    ctx.beginPath();
    for (let i = 0; i < points * 2; i++) {
      const r = i % 2 === 0 ? outer : inner;
      const a = -Math.PI / 2 + (i * Math.PI) / points;
      const x = cx + Math.cos(a) * r;
      const y = cy + Math.sin(a) * r;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.fillStyle = fill;
    ctx.fill();
    if (stroke) {
      ctx.strokeStyle = stroke;
      ctx.stroke();
    }
  }

  function drawBanana(ctx, s) {
    const g = ctx.createLinearGradient(-s * 0.5, 0, s * 0.5, s * 0.2);
    g.addColorStop(0, '#fff09a');
    g.addColorStop(0.55, '#ffd84a');
    g.addColorStop(1, '#e8a91c');
    ctx.fillStyle = g;
    ctx.strokeStyle = '#90620b';
    ctx.lineWidth = Math.max(1, s * 0.045);
    ctx.beginPath();
    ctx.moveTo(-s * 0.48, -s * 0.10);
    ctx.quadraticCurveTo(-s * 0.18, s * 0.56, s * 0.50, s * 0.04);
    ctx.quadraticCurveTo(s * 0.06, s * 0.24, -s * 0.30, -s * 0.23);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = '#67480d';
    ctx.beginPath();
    ctx.arc(-s * 0.48, -s * 0.10, s * 0.055, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(s * 0.50, s * 0.04, s * 0.055, 0, Math.PI * 2);
    ctx.fill();
  }

  function drawMango(ctx, s) {
    ctx.save();
    ctx.rotate(-0.24);
    const g = ctx.createLinearGradient(-s * 0.35, -s * 0.3, s * 0.35, s * 0.3);
    g.addColorStop(0, '#ffe36a');
    g.addColorStop(0.55, '#ffb52e');
    g.addColorStop(1, '#e87418');
    ctx.fillStyle = g;
    ctx.strokeStyle = '#a9580d';
    ctx.lineWidth = Math.max(1, s * 0.045);
    ctx.beginPath();
    ctx.ellipse(0, s * 0.04, s * 0.38, s * 0.29, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = 'rgba(255,255,220,0.55)';
    ctx.beginPath();
    ctx.ellipse(-s * 0.13, -s * 0.05, s * 0.10, s * 0.06, -0.5, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = '#3b9b32';
    ctx.beginPath();
    ctx.ellipse(s * 0.12, -s * 0.30, s * 0.13, s * 0.06, -0.6, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  function drawApple(ctx, s) {
    const r = s * 0.36;
    const g = ctx.createRadialGradient(-r * 0.35, -r * 0.35, r * 0.1, 0, 0, r * 1.3);
    g.addColorStop(0, '#ff8a6a');
    g.addColorStop(0.5, '#e8291d');
    g.addColorStop(1, '#8c0c08');
    ctx.fillStyle = g;
    ctx.strokeStyle = '#6f0905';
    ctx.lineWidth = Math.max(1, s * 0.04);
    ctx.beginPath();
    ctx.arc(0, s * 0.07, r, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    ctx.strokeStyle = '#6b3b12';
    ctx.lineWidth = Math.max(1.2, s * 0.06);
    ctx.beginPath();
    ctx.moveTo(0, -r * 0.85);
    ctx.quadraticCurveTo(s * 0.05, -r * 1.25, s * 0.14, -r * 1.2);
    ctx.stroke();

    ctx.fillStyle = '#3da33a';
    ctx.beginPath();
    ctx.ellipse(s * 0.18, -r * 1.08, s * 0.12, s * 0.055, -0.45, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = 'rgba(255,255,255,0.55)';
    ctx.beginPath();
    ctx.ellipse(-r * 0.32, -r * 0.25, r * 0.16, r * 0.10, -0.6, 0, Math.PI * 2);
    ctx.fill();
  }

  function drawWatermelon(ctx, s) {
    const r = s * 0.39;
    ctx.fillStyle = '#2f8f37';
    ctx.strokeStyle = '#155b1e';
    ctx.lineWidth = Math.max(1, s * 0.04);
    ctx.beginPath();
    ctx.arc(0, 0, r, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = '#f2414a';
    ctx.beginPath();
    ctx.arc(0, s * 0.02, r * 0.79, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = '#f7b7a8';
    ctx.beginPath();
    ctx.arc(0, s * 0.02, r * 0.79, Math.PI * 1.05, Math.PI * 1.45);
    ctx.strokeStyle = 'rgba(255,255,255,0.4)';
    ctx.lineWidth = Math.max(1, s * 0.03);
    ctx.stroke();

    ctx.fillStyle = '#34110f';
    const seeds = [
      [-r * 0.35, -r * 0.10], [r * 0.05, -r * 0.30], [r * 0.38, r * 0.02],
      [-r * 0.12, r * 0.30], [r * 0.20, r * 0.34], [-r * 0.42, r * 0.22],
    ];
    for (const [x, y] of seeds) {
      ctx.beginPath();
      ctx.ellipse(x, y, s * 0.035, s * 0.055, 0.5, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  function drawStarSymbol(ctx, s) {
    star(ctx, -s * 0.14, s * 0.03, s * 0.27, s * 0.11, 5, '#ffe14d', '#9c6a10');
    star(ctx, s * 0.16, s * 0.02, s * 0.23, s * 0.09, 5, '#4de1ff', '#0d7f9c');
  }

  function drawSeven(ctx, s) {
    ctx.save();
    ctx.font = `900 ${Math.round(s * 0.54)}px "Arial Black", "Microsoft YaHei", sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = '#ff3b2f';
    ctx.shadowColor = '#ff5a2a';
    ctx.shadowBlur = s * 0.28;
    ctx.fillText('77', 0, s * 0.03);
    ctx.shadowBlur = 0;
    ctx.fillStyle = '#ffd0a8';
    ctx.font = `900 ${Math.round(s * 0.12)}px "Microsoft YaHei", sans-serif`;
    ctx.fillText('DOUBLE', 0, s * 0.36);
    ctx.restore();
  }

  function drawBar(ctx, s) {
    const g = ctx.createLinearGradient(0, -s * 0.22, 0, s * 0.22);
    g.addColorStop(0, '#fff0a8');
    g.addColorStop(0.45, '#ffc032');
    g.addColorStop(1, '#b86a0a');
    roundRect(ctx, -s * 0.43, -s * 0.20, s * 0.86, s * 0.40, s * 0.07);
    ctx.fillStyle = g;
    ctx.fill();
    ctx.strokeStyle = '#6b3c08';
    ctx.lineWidth = Math.max(1, s * 0.04);
    ctx.stroke();
    ctx.fillStyle = '#4a2205';
    ctx.font = `900 ${Math.round(s * 0.20)}px "Arial Black", "Microsoft YaHei", sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('BAR', 0, s * 0.015);
  }

  function drawLuck(ctx, s) {
    star(ctx, 0, -s * 0.05, s * 0.36, s * 0.16, 8, 'rgba(255,216,74,0.92)', '#9c6a10');
    ctx.fillStyle = '#4de1ff';
    ctx.font = `900 ${Math.round(s * 0.13)}px "Microsoft YaHei", sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('LUCK', 0, s * 0.30);
  }

  function drawFruit(ctx, symbolId, cx, cy, size, opts = {}) {
    const small = symbolId === 's_banana' || symbolId === 's_mango';
    const base = small ? symbolId.slice(2) : symbolId;
    const s = size * (small ? 0.76 : 1);

    ctx.save();
    ctx.translate(cx, cy);
    ctx.lineJoin = 'round';

    if (base === 'banana') drawBanana(ctx, s);
    else if (base === 'mango') drawMango(ctx, s);
    else if (base === 'apple') drawApple(ctx, s);
    else if (base === 'watermelon') drawWatermelon(ctx, s);
    else if (base === 'star') drawStarSymbol(ctx, s);
    else if (base === 'seven') drawSeven(ctx, s);
    else if (base === 'bar') drawBar(ctx, s);
    else if (base === 'luck') drawLuck(ctx, s);

    if (small) {
      const bx = size * 0.34;
      const by = -size * 0.34;
      ctx.beginPath();
      ctx.arc(bx, by, size * 0.17, 0, Math.PI * 2);
      ctx.fillStyle = '#d8342a';
      ctx.fill();
      ctx.strokeStyle = '#ffd9a0';
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.fillStyle = '#fff6e0';
      ctx.font = `700 ${Math.max(7, Math.round(size * 0.20))}px "Microsoft YaHei", sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('小', bx, by + 0.5);
    }

    ctx.restore();
  }

  function drawCenter(ctx, state) {
    const t = (state.time || 0) / 1000;

    ctx.save();
    ctx.translate(CENTER, CENTER);

    // 外圈光晕
    const halo = ctx.createRadialGradient(0, 0, 120, 0, 0, 190);
    halo.addColorStop(0, 'rgba(255, 170, 50, 0.12)');
    halo.addColorStop(1, 'rgba(255, 90, 20, 0)');
    ctx.fillStyle = halo;
    ctx.beginPath();
    ctx.arc(0, 0, 190, 0, Math.PI * 2);
    ctx.fill();

    // 金色外环
    ctx.beginPath();
    ctx.arc(0, 0, 166, 0, Math.PI * 2);
    ctx.lineWidth = 7;
    ctx.strokeStyle = COLORS.gold;
    ctx.shadowColor = 'rgba(255, 170, 40, 0.8)';
    ctx.shadowBlur = 18;
    ctx.stroke();
    ctx.shadowBlur = 0;

    ctx.beginPath();
    ctx.arc(0, 0, 156, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(14, 7, 3, 0.94)';
    ctx.fill();
    ctx.strokeStyle = 'rgba(255, 200, 90, 0.35)';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // 缓慢旋转的刻度
    ctx.save();
    ctx.rotate(t * 0.18);
    ctx.strokeStyle = 'rgba(255, 190, 80, 0.25)';
    ctx.lineWidth = 2;
    for (let i = 0; i < 24; i++) {
      ctx.rotate((Math.PI * 2) / 24);
      ctx.beginPath();
      ctx.moveTo(0, -148);
      ctx.lineTo(0, -138);
      ctx.stroke();
    }
    ctx.restore();

    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    ctx.fillStyle = COLORS.gold;
    ctx.font = '900 48px "Microsoft YaHei", "SimHei", sans-serif';
    ctx.shadowColor = '#ff8a00';
    ctx.shadowBlur = 18;
    ctx.fillText('天门', 0, -28);
    ctx.shadowBlur = 0;

    ctx.fillStyle = '#fff0c0';
    ctx.font = '700 30px "Courier New", monospace';
    ctx.fillText('× 50', 0, 24);

    ctx.fillStyle = 'rgba(255, 160, 60, 0.85)';
    ctx.font = '12px "Microsoft YaHei", sans-serif';
    ctx.fillText('小天门 5×   ·   天门 10×   ·   大天门 50×', 0, 74);

    ctx.fillStyle = 'rgba(255, 210, 140, 0.55)';
    ctx.font = '700 13px "Microsoft YaHei", sans-serif';
    ctx.fillText('开 火 车 啦', 0, 112);

    ctx.restore();
  }

  function drawBoard(ctx, state) {
    const width = ctx.canvas.width / (window.devicePixelRatio || 1);
    const height = ctx.canvas.height / (window.devicePixelRatio || 1);
    const w = width || 680;
    const h = height || 680;

    ctx.clearRect(0, 0, w, h);

    // 背景
    const bg = ctx.createRadialGradient(CENTER, CENTER, 80, CENTER, CENTER, 360);
    bg.addColorStop(0, '#2a130a');
    bg.addColorStop(0.55, '#140804');
    bg.addColorStop(1, '#070302');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, w, h);

    // 放射线
    ctx.save();
    ctx.translate(CENTER, CENTER);
    ctx.globalAlpha = 0.10;
    for (let i = 0; i < 16; i++) {
      ctx.rotate((Math.PI * 2) / 16);
      ctx.fillStyle = i % 2 ? '#ffb347' : '#4de1ff';
      ctx.beginPath();
      ctx.moveTo(0, 150);
      ctx.lineTo(-16, 320);
      ctx.lineTo(16, 320);
      ctx.closePath();
      ctx.fill();
    }
    ctx.restore();
    ctx.globalAlpha = 1;

    // 跑道
    ctx.beginPath();
    ctx.arc(CENTER, CENTER, RADIUS, 0, Math.PI * 2);
    ctx.lineWidth = 78;
    ctx.strokeStyle = '#160b05';
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(CENTER, CENTER, RADIUS + 40, 0, Math.PI * 2);
    ctx.lineWidth = 2;
    ctx.strokeStyle = 'rgba(255, 170, 60, 0.55)';
    ctx.stroke();

    ctx.beginPath();
    ctx.arc(CENTER, CENTER, RADIUS - 40, 0, Math.PI * 2);
    ctx.lineWidth = 2;
    ctx.strokeStyle = 'rgba(255, 170, 60, 0.35)';
    ctx.stroke();

    drawCenter(ctx, state);

    const symbolMap = {};
    for (const sym of state.symbols) symbolMap[sym.id] = sym;

    for (let i = 0; i < 24; i++) {
      const angle = -Math.PI / 2 + (i * Math.PI * 2) / 24;
      const x = CENTER + Math.cos(angle) * RADIUS;
      const y = CENTER + Math.sin(angle) * RADIUS;
      const id = state.ring[i];
      const sym = symbolMap[id];
      const lit = state.litIndex === i;
      const win = (state.winIndices || []).includes(i);
      const bet = id !== 'luck' && state.bets && state.bets[id] > 0;

      ctx.save();
      ctx.translate(x, y);

      if (lit || win) {
        ctx.shadowColor = win ? '#ffe88a' : '#ffb02e';
        ctx.shadowBlur = win ? 26 : 18;
      }
      if (lit) ctx.scale(1.12, 1.12);

      const lampGrad = ctx.createLinearGradient(0, -LAMP / 2, 0, LAMP / 2);
      lampGrad.addColorStop(0, lit ? '#5a3412' : '#21120a');
      lampGrad.addColorStop(1, lit ? '#2a1307' : '#0e0704');
      roundRect(ctx, -LAMP / 2, -LAMP / 2, LAMP, LAMP, 11);
      ctx.fillStyle = lampGrad;
      ctx.fill();

      ctx.lineWidth = lit || win ? 2.5 : 1.5;
      ctx.strokeStyle = win
        ? '#ffe88a'
        : lit
          ? '#ffb02e'
          : bet
            ? 'rgba(88, 224, 106, 0.65)'
            : 'rgba(140, 90, 40, 0.55)';
      ctx.stroke();

      if (win) {
        ctx.fillStyle = `rgba(255, 210, 90, ${0.16 + 0.12 * Math.sin((state.time || 0) / 90)})`;
        roundRect(ctx, -LAMP / 2, -LAMP / 2, LAMP, LAMP, 11);
        ctx.fill();
      }

      drawFruit(ctx, id, 0, -5, 31);

      ctx.fillStyle = id === 'luck' ? 'rgba(160, 200, 255, 0.8)' : 'rgba(255, 214, 140, 0.92)';
      ctx.font = '700 10px "Courier New", monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(id === 'luck' ? '跑空' : `${sym.odds}×`, 0, 21);

      if (bet) {
        ctx.beginPath();
        ctx.arc(21, -21, 4.5, 0, Math.PI * 2);
        ctx.fillStyle = COLORS.green;
        ctx.shadowColor = COLORS.green;
        ctx.shadowBlur = 8;
        ctx.fill();
        ctx.shadowBlur = 0;
      }

      ctx.restore();
    }
  }

  function clamp(n, min, max) {
    return Math.max(min, Math.min(max, n));
  }

  function drawEngine(ctx, x, y) {
    const g = ctx.createLinearGradient(0, y, 0, y + 34);
    g.addColorStop(0, '#ffcf6a');
    g.addColorStop(1, '#a85a12');
    roundRect(ctx, x, y + 8, 54, 24, 6);
    ctx.fillStyle = g;
    ctx.fill();
    ctx.strokeStyle = '#ffe08a';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    roundRect(ctx, x + 9, y - 2, 27, 18, 4);
    ctx.fillStyle = '#2a1206';
    ctx.fill();
    ctx.strokeStyle = '#ffcf6a';
    ctx.stroke();

    ctx.fillStyle = '#d98a24';
    ctx.fillRect(x + 38, y - 6, 8, 14);
    ctx.fillStyle = '#5a2b06';
    ctx.fillRect(x + 36, y - 8, 12, 4);

    ctx.fillStyle = '#120804';
    ctx.strokeStyle = '#ffc857';
    ctx.lineWidth = 1.5;
    for (const wx of [x + 14, x + 44]) {
      ctx.beginPath();
      ctx.arc(wx, y + 36, 7, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    }

    ctx.fillStyle = '#ffe8a8';
    ctx.font = '700 10px "Microsoft YaHei", sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('火车', x + 27, y + 20);
  }

  function drawCarriage(ctx, x, y, carriage, revealed) {
    const g = ctx.createLinearGradient(0, y, 0, y + 38);
    g.addColorStop(0, revealed ? '#3b2410' : '#1a0f08');
    g.addColorStop(1, '#100804');
    roundRect(ctx, x, y, 92, 38, 7);
    ctx.fillStyle = g;
    ctx.fill();
    ctx.strokeStyle = revealed
      ? (carriage.empty ? 'rgba(160, 120, 80, 0.65)' : '#ffc857')
      : 'rgba(120, 80, 40, 0.35)';
    ctx.lineWidth = revealed ? 2 : 1;
    ctx.stroke();

    ctx.fillStyle = '#0c0603';
    ctx.strokeStyle = revealed ? 'rgba(255, 200, 100, 0.8)' : 'rgba(120, 80, 40, 0.4)';
    ctx.lineWidth = 1.2;
    for (const wx of [x + 20, x + 72]) {
      ctx.beginPath();
      ctx.arc(wx, y + 41, 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    }

    if (!revealed) {
      ctx.fillStyle = 'rgba(180, 130, 80, 0.45)';
      ctx.font = '700 16px "Courier New", monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('?', x + 46, y + 19);
      return;
    }

    if (carriage.empty) {
      ctx.fillStyle = '#a9835d';
      ctx.font = '700 13px "Microsoft YaHei", sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('空车', x + 46, y + 19);
      return;
    }

    drawFruit(ctx, carriage.symbolId, x + 30, y + 18, 22);
    ctx.fillStyle = '#7dffa0';
    ctx.font = '700 13px "Courier New", monospace';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    ctx.fillText('+' + carriage.win, x + 52, y + 19);
  }

  function drawTrain(ctx, progress, carriages, reveal) {
    if (!carriages) return;
    const p = clamp(progress || 0, 0, 1);
    const revealed = reveal || 0;
    const slide = (1 - p) * -620;

    ctx.save();
    const bg = ctx.createLinearGradient(0, 608, 0, 680);
    bg.addColorStop(0, 'rgba(5, 2, 1, 0)');
    bg.addColorStop(0.35, 'rgba(5, 2, 1, 0.9)');
    bg.addColorStop(1, 'rgba(5, 2, 1, 0.98)');
    ctx.fillStyle = bg;
    ctx.fillRect(0, 608, 680, 72);

    ctx.strokeStyle = 'rgba(255, 190, 90, 0.5)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, 676);
    ctx.lineTo(680, 676);
    ctx.stroke();

    ctx.strokeStyle = 'rgba(255, 190, 90, 0.25)';
    ctx.lineWidth = 1.5;
    for (let x = 0; x < 680; x += 26) {
      ctx.beginPath();
      ctx.moveTo(x, 676);
      ctx.lineTo(x + 10, 670);
      ctx.stroke();
    }

    ctx.translate(slide, 0);
    drawEngine(ctx, 16, 634);
    for (let i = 0; i < carriages.length; i++) {
      drawCarriage(ctx, 92 + i * 106, 632, carriages[i], i < revealed);
    }
    ctx.restore();
  }

  function drawDoorPanel(ctx, x, y, w, h, char) {
    const g = ctx.createLinearGradient(x, y, x, y + h);
    g.addColorStop(0, '#6b3208');
    g.addColorStop(0.35, '#d68a22');
    g.addColorStop(0.55, '#ffd36a');
    g.addColorStop(1, '#5c2a06');
    roundRect(ctx, x, y, w, h, 8);
    ctx.fillStyle = g;
    ctx.fill();
    ctx.strokeStyle = '#ffe08a';
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.fillStyle = 'rgba(70, 30, 5, 0.78)';
    ctx.font = '900 76px "Microsoft YaHei", "SimHei", sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(char, x + w / 2, y + h / 2);

    ctx.fillStyle = 'rgba(80, 36, 8, 0.7)';
    for (let i = 0; i < 4; i++) {
      ctx.beginPath();
      ctx.arc(x + 12, y + 34 + i * 78, 3, 0, Math.PI * 2);
      ctx.fill();
      ctx.beginPath();
      ctx.arc(x + w - 12, y + 34 + i * 78, 3, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  function drawGateWheel(ctx, wheel, progress, open, done) {
    if (!wheel) return;
    const p = clamp(progress || 0, 0, 1);
    const o = clamp(open == null ? 0 : open, 0, 1);
    const target = GATE_SEGMENTS.find((seg) => seg.label === wheel.label) || GATE_SEGMENTS[0];

    ctx.save();
    ctx.translate(CENTER, CENTER);

    ctx.beginPath();
    ctx.arc(0, 0, 152, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(7, 3, 1, 0.95)';
    ctx.fill();

    for (const seg of GATE_SEGMENTS) {
      const start = seg.center - Math.PI / 3;
      const end = seg.center + Math.PI / 3;
      const active = done && seg.label === target.label;
      ctx.beginPath();
      ctx.arc(0, 0, 116, start, end);
      ctx.lineWidth = 36;
      ctx.strokeStyle = seg.color;
      ctx.globalAlpha = active ? 1 : 0.62;
      ctx.shadowColor = seg.color;
      ctx.shadowBlur = active ? 24 : 6;
      ctx.stroke();
      ctx.shadowBlur = 0;
      ctx.globalAlpha = 1;

      const lx = Math.cos(seg.center) * 116;
      const ly = Math.sin(seg.center) * 116;
      ctx.fillStyle = 'rgba(12, 6, 3, 0.9)';
      roundRect(ctx, lx - 33, ly - 11, 66, 22, 6);
      ctx.fill();
      ctx.fillStyle = seg.color;
      ctx.font = '700 12px "Microsoft YaHei", sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(`${seg.label} ${seg.multiplier}×`, lx, ly + 0.5);
    }

    const startAngle = -Math.PI / 2;
    const delta = ((target.center - startAngle) % (Math.PI * 2) + Math.PI * 2) % (Math.PI * 2);
    const total = Math.PI * 2 * 3 + delta;
    const angle = startAngle + p * total;
    ctx.save();
    // 指针默认画向上方（-Y），转到数学角度需要额外 +90°。
    ctx.rotate(angle + Math.PI / 2);
    ctx.strokeStyle = '#fff4c8';
    ctx.lineWidth = 4;
    ctx.shadowColor = '#ffd36a';
    ctx.shadowBlur = 14;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(0, -138);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(-7, -132);
    ctx.lineTo(0, -146);
    ctx.lineTo(7, -132);
    ctx.closePath();
    ctx.fillStyle = '#ffe08a';
    ctx.fill();
    ctx.restore();

    ctx.beginPath();
    ctx.arc(0, 0, 30, 0, Math.PI * 2);
    ctx.fillStyle = '#1a0c05';
    ctx.fill();
    ctx.strokeStyle = '#ffc857';
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.save();
    ctx.beginPath();
    ctx.arc(0, 0, 150, 0, Math.PI * 2);
    ctx.clip();
    const slide = o * 160;
    drawDoorPanel(ctx, -150 - slide, -150, 150, 300, '天');
    drawDoorPanel(ctx, slide, -150, 150, 300, '门');
    ctx.restore();

    ctx.beginPath();
    ctx.arc(0, 0, 151, 0, Math.PI * 2);
    ctx.lineWidth = 4;
    ctx.strokeStyle = '#ffc857';
    ctx.stroke();

    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    if (done) {
      ctx.fillStyle = 'rgba(8, 4, 2, 0.86)';
      roundRect(ctx, -78, -46, 156, 108, 12);
      ctx.fill();
      ctx.strokeStyle = 'rgba(255, 200, 90, 0.5)';
      ctx.lineWidth = 1;
      ctx.stroke();

      ctx.fillStyle = '#fff0c0';
      ctx.font = '900 30px "Microsoft YaHei", "SimHei", sans-serif';
      ctx.shadowColor = '#ff8a00';
      ctx.shadowBlur = 18;
      ctx.fillText(wheel.label, 0, -22);
      ctx.shadowBlur = 0;
      ctx.fillStyle = '#ffd36a';
      ctx.font = '700 22px "Courier New", monospace';
      ctx.fillText('× ' + wheel.multiplier, 0, 16);
      ctx.fillStyle = '#7dffa0';
      ctx.font = '700 16px "Courier New", monospace';
      ctx.fillText('+' + wheel.win, 0, 48);
    } else {
      ctx.fillStyle = '#ffd36a';
      ctx.font = '900 28px "Microsoft YaHei", "SimHei", sans-serif';
      ctx.shadowColor = '#ff8a00';
      ctx.shadowBlur = 14;
      ctx.fillText('天门', 0, -16);
      ctx.shadowBlur = 0;
      ctx.fillStyle = 'rgba(255, 200, 110, 0.7)';
      ctx.font = '12px "Microsoft YaHei", sans-serif';
      ctx.fillText('转动天门', 0, 18);
    }

    ctx.restore();
  }

  root.TigerRender = {
    CENTER,
    RADIUS,
    LAMP,
    drawBoard,
    drawFruit,
    drawTrain,
    drawGateWheel,
  };
})(typeof window !== 'undefined' ? window : globalThis);
