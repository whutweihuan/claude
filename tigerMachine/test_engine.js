const assert = require('assert');
const E = require('./engine.js');

let passed = 0, failed = 0;
function test(name, fn) {
  try { fn(); passed++; console.log('PASS', name); }
  catch (err) { failed++; console.error('FAIL', name); console.error(err.message); }
}
function summary() {
  console.log(`\npassed: ${passed}, failed: ${failed}`);
  if (failed > 0) process.exit(1);
}

test('SYMBOLS：9 个图案，赔率固定', () => {
  assert.strictEqual(E.SYMBOLS.length, 9);
  assert.deepStrictEqual(E.SYMBOLS.map(s => s.odds), [4, 6, 8, 12, 15, 20, 30, 40, 50]);
});

test('RING：24 格、6 个 LUCK、id 合法', () => {
  assert.strictEqual(E.RING.length, 24);
  const ids = new Set(E.SYMBOLS.map(s => s.id));
  assert.strictEqual(E.RING.filter(x => x === 'luck').length, 6);
  for (const x of E.RING) assert.ok(x === 'luck' || ids.has(x), x);
});

test('初始状态：1000 币、押分为 0', () => {
  const g = E.createGame();
  const s = g.getState();
  assert.strictEqual(s.coins, 1000);
  assert.strictEqual(s.totalBet, 0);
  for (const sym of E.SYMBOLS) assert.strictEqual(s.bets[sym.id], 0);
});

test('押分、减注、清零', () => {
  const g = E.createGame();
  assert.deepStrictEqual(g.bet('s_banana', 5), { ok: true });
  assert.strictEqual(g.getState().totalBet, 5);
  g.bet('s_banana', -10);
  assert.strictEqual(g.getState().bets.s_banana, 0);
  g.bet('bar', 10);
  g.clearBets();
  assert.strictEqual(g.getState().totalBet, 0);
});

test('单门最多 99', () => {
  const g = E.createGame();
  g.bet('bar', 99);
  assert.deepStrictEqual(g.bet('bar', 1), { ok: false, error: 'MAX_BET' });
  assert.strictEqual(g.getState().bets.bar, 99);
});

test('押分不能超过金币', () => {
  const g = E.createGame({ coins: 20 });
  assert.deepStrictEqual(g.bet('bar', 30), { ok: false, error: 'INSUFFICIENT_COINS' });
  assert.strictEqual(g.getState().bets.bar, 0);
});

test('投币与全押', () => {
  const g = E.createGame({ coins: 30 });
  g.insertCoin(100);
  assert.strictEqual(g.getState().coins, 130);
  const r = g.betAll(10);
  assert.strictEqual(r.ok, true);
  assert.strictEqual(r.added, 90);
  assert.strictEqual(g.getState().totalBet, 90);
});

test('全押金币不足时只加到能负担为止', () => {
  const g = E.createGame({ coins: 25 });
  const r = g.betAll(10);
  assert.strictEqual(r.added, 25);
  assert.strictEqual(g.getState().totalBet, 25);
});

test('全押跳过已满 99 的门，不提前停止', () => {
  const g = E.createGame({ coins: 1000 });
  g.bet('s_banana', 99);
  const r = g.betAll(1);
  assert.deepStrictEqual(r, { ok: true, added: 8 });
  assert.strictEqual(g.getState().totalBet, 107);
  assert.strictEqual(g.getState().bets.s_banana, 99);
});

test('getState 返回快照', () => {
  const g = E.createGame();
  const s = g.getState();
  g.bet('apple', 5);
  assert.strictEqual(s.bets.apple, 0);
});

function seq(values) {
  let i = 0;
  return () => {
    if (i >= values.length) throw new Error('RNG 用尽');
    return values[i++];
  };
}

test('命中图案按押分×赔率赔付', () => {
  const g = E.createGame({ rng: seq([0]) });
  g.bet('banana', 10);
  g.forceNextSymbol('banana');
  const r = g.spin();
  assert.strictEqual(r.kind, 'symbol');
  assert.strictEqual(r.symbolId, 'banana');
  assert.strictEqual(r.win, 120);
  assert.ok(E.RING[r.stopIndex] === 'banana');
  assert.strictEqual(g.getState().coins, 990);
  assert.strictEqual(g.getState().pendingWin, 120);
});

test('停在没押的图案不赔', () => {
  const g = E.createGame({ rng: seq([0]) });
  g.bet('apple', 5);
  g.forceNextSymbol('bar');
  const r = g.spin();
  assert.strictEqual(r.win, 0);
  assert.strictEqual(g.getState().pendingWin, 0);
});

test('跑空不赔，但仍扣押分', () => {
  const g = E.createGame({ rng: seq([0]) });
  g.bet('s_banana', 5);
  g.forceNextLuck();
  const r = g.spin();
  assert.strictEqual(r.kind, 'luck');
  assert.strictEqual(r.win, 0);
  assert.strictEqual(g.getState().coins, 995);
});

test('收分把 pendingWin 加回金币', () => {
  const g = E.createGame({ rng: seq([0]) });
  g.bet('banana', 10);
  g.forceNextSymbol('banana');
  g.spin();
  const c = g.collect();
  assert.strictEqual(c.collected, 120);
  assert.strictEqual(g.getState().coins, 1110);
  assert.strictEqual(g.getState().pendingWin, 0);
});

test('有未收奖金时禁止再开局/改注', () => {
  const g = E.createGame({ rng: seq([0]) });
  g.bet('banana', 10);
  g.forceNextSymbol('banana');
  g.spin();
  assert.throws(() => g.spin(), /ROUND_ACTIVE/);
  assert.deepStrictEqual(g.bet('apple', 1), { ok: false, error: 'ROUND_ACTIVE' });
});

test('小三元只赔三小，不赔其他', () => {
  const g = E.createGame({ rng: seq([0]) });
  g.bet('s_banana', 1); g.bet('s_mango', 2); g.bet('apple', 3); g.bet('bar', 1);
  g.forceNextFeature('smallThree');
  const r = g.spin();
  assert.strictEqual(r.kind, 'feature');
  assert.strictEqual(r.feature.type, 'smallThree');
  assert.strictEqual(r.win, 1 * 4 + 2 * 6 + 3 * 8);
  assert.deepStrictEqual(r.feature.symbols.map(s => s.id), ['s_banana', 's_mango', 'apple']);
});

test('大三元只赔三大', () => {
  const g = E.createGame({ rng: seq([0]) });
  g.bet('watermelon', 1); g.bet('star', 2); g.bet('seven', 3); g.bet('apple', 9);
  g.forceNextFeature('bigThree');
  const r = g.spin();
  assert.strictEqual(r.win, 1 * 20 + 2 * 30 + 3 * 40);
});

test('开火车 5 节，空车不赔', () => {
  // 0.65 -> bar，0.9 -> 空车，0.65 -> bar，0.9 -> 空车，0.65 -> bar，最后 0 给 stopIndex
  const g = E.createGame({ rng: seq([0.65, 0.9, 0.65, 0.9, 0.65, 0]) });
  g.bet('bar', 10);
  g.forceNextFeature('train');
  const r = g.spin();
  assert.strictEqual(r.feature.carriages.length, 5);
  assert.deepStrictEqual(r.feature.carriages.map(c => c.symbolId), ['bar', null, 'bar', null, 'bar']);
  assert.strictEqual(r.win, 3 * 10 * 50);
});

test('天门按总押分 × 转盘倍率', () => {
  const g = E.createGame({ rng: seq([0.99, 0]) }); // 大天门
  g.bet('bar', 5); g.bet('apple', 5);                 // 总押分 10
  g.forceNextFeature('gate');
  const r = g.spin();
  assert.strictEqual(r.feature.wheel.label, '大天门');
  assert.strictEqual(r.win, 10 * 50);
});

test('彩头重置保底计数', () => {
  const g = E.createGame({ rng: seq([0]) });
  g.bet('s_banana', 1);
  g.forceNextFeature('smallThree');
  g.spin();
  assert.strictEqual(g.getState().spinsSinceFeature, 0);
});

test('猜对翻倍，收分入账', () => {
  // 第 1 个 rng 给 spin 的停灯格，第 2 个给猜大小
  const g = E.createGame({ rng: seq([0, 4 / 13]) }); // 开 5
  g.bet('banana', 10);
  g.forceNextSymbol('banana');
  g.spin();                                     // pending 120
  const r = g.guess('small');
  assert.strictEqual(r.number, 5);
  assert.strictEqual(r.correct, true);
  assert.strictEqual(g.getState().pendingWin, 240);
  assert.strictEqual(g.collect().collected, 240);
});

test('猜错清零，开 7 通杀', () => {
  const g = E.createGame({ rng: seq([0, 6 / 13]) }); // 开 7
  g.bet('banana', 10);
  g.forceNextSymbol('banana');
  g.spin();
  const r = g.guess('big');
  assert.strictEqual(r.number, 7);
  assert.strictEqual(r.correct, false);
  assert.strictEqual(g.getState().pendingWin, 0);
});

test('第三次猜对后自动收分', () => {
  // 1 个给 spin，3 个给三次猜大小
  const g = E.createGame({ rng: seq([0, 0, 0, 0]) }); // 三次都开 1
  g.bet('banana', 10);
  g.forceNextSymbol('banana');
  g.spin();
  g.guess('small');
  g.guess('small');
  const r = g.guess('small');
  assert.strictEqual(r.autoCollected, true);
  assert.strictEqual(g.getState().pendingWin, 0);
  assert.strictEqual(g.getState().coins, 1000 - 10 + 120 * 8);
});

test('没有 pendingWin 时不能猜', () => {
  const g = E.createGame();
  assert.throws(() => g.guess('small'), /NO_PENDING_WIN/);
});

test('60 局无彩头后下一局强制彩头', () => {
  const g = E.createGame({ coins: 1000, rng: () => 0.999 }); // 一直跑空
  g.bet('s_banana', 1);
  for (let i = 0; i < 60; i++) { g.forceNextLuck(); g.spin(); }
  const r = g.spin(); // 第 61 局
  assert.strictEqual(r.kind, 'feature');
  assert.strictEqual(g.getState().spinsSinceFeature, 0);
});

test('达到 99999 触发爆机标记', () => {
  const g = E.createGame({ rng: seq([0]) });
  g.insertCoin(99999 - 1000);
  g.bet('bar', 1);
  g.forceNextSymbol('bar');
  g.spin();
  const c = g.collect();
  assert.strictEqual(c.jackpot, true);
  assert.strictEqual(g.getState().jackpotArmed, false);
});

test('非整数/零步进与非法图案被拒绝', () => {
  const g = E.createGame();
  assert.deepStrictEqual(g.bet('apple', 0), { ok: false, error: 'INVALID_DELTA' });
  assert.deepStrictEqual(g.bet('apple', 1.5), { ok: false, error: 'INVALID_DELTA' });
  assert.deepStrictEqual(g.bet('nope', 1), { ok: false, error: 'INVALID_SYMBOL' });
  assert.deepStrictEqual(g.betAll(0), { ok: false, error: 'INVALID_DELTA' });
});

test('重复收分只入账一次', () => {
  const g = E.createGame({ rng: seq([0]) });
  g.bet('banana', 10);
  g.forceNextSymbol('banana');
  g.spin();
  assert.strictEqual(g.collect().collected, 120);
  const coins = g.getState().coins;
  assert.deepStrictEqual(g.collect(), { collected: 0, jackpot: false });
  assert.strictEqual(g.getState().coins, coins);
});

test('爆机后跌破 90000 重新武装，可再次触发', () => {
  const g = E.createGame({ coins: 99999, rng: () => 0 });
  g.bet('bar', 1);
  g.forceNextSymbol('bar');
  g.spin();
  assert.strictEqual(g.collect().jackpot, true);
  assert.strictEqual(g.getState().jackpotArmed, false);

  for (let i = 0; i < 12; i++) {
    g.betAll(99);
    g.forceNextLuck();
    g.spin();
    g.collect();
  }
  assert.ok(g.getState().coins < 90000, `coins=${g.getState().coins}`);

  g.clearBets();
  g.bet('bar', 1);
  g.forceNextSymbol('bar');
  g.spin();
  assert.strictEqual(g.collect().jackpot, false);
  assert.strictEqual(g.getState().jackpotArmed, true);

  g.insertCoin(99999 - g.getState().coins);
  g.clearBets();
  g.bet('bar', 1);
  g.forceNextSymbol('bar');
  g.spin();
  assert.strictEqual(g.collect().jackpot, true);
});

test('10 万局九门均注：RTP 与彩头分布', () => {
  const g = E.createGame({ coins: 1e9, rng: E.mulberry32(20261111) });
  for (const s of E.SYMBOLS) g.bet(s.id, 1);

  let wagered = 0, won = 0;
  let features = 0, trainSpins = 0, trainCars = 0, trainEmpty = 0, gateCount = 0;
  const types = { smallThree: 0, bigThree: 0, train: 0, gate: 0 };
  const gateLabels = { 小天门: 0, 天门: 0, 大天门: 0 };

  for (let i = 0; i < 100000; i++) {
    const r = g.spin();
    wagered += 9;
    won += r.win;
    if (r.kind === 'feature') {
      features++;
      types[r.feature.type]++;
      if (r.feature.type === 'train') {
        trainSpins++;
        for (const carriage of r.feature.carriages) {
          trainCars++;
          if (carriage.empty) trainEmpty++;
        }
      }
      if (r.feature.type === 'gate') {
        gateCount++;
        gateLabels[r.feature.wheel.label]++;
      }
    }
    g.collect();
  }

  const rtp = won / wagered;
  assert.ok(rtp >= 0.93 && rtp <= 0.99, `RTP=${rtp}`);
  assert.ok(features / 100000 >= 0.015 && features / 100000 <= 0.055, `feature rate=${features / 100000}`);
  assert.strictEqual(types.smallThree + types.bigThree + types.train + types.gate, features);

  assert.ok(types.smallThree / 100000 >= 0.012 && types.smallThree / 100000 <= 0.017, `smallThree=${types.smallThree}`);
  assert.ok(types.bigThree / 100000 >= 0.004 && types.bigThree / 100000 <= 0.008, `bigThree=${types.bigThree}`);
  assert.ok(types.train / 100000 >= 0.0085 && types.train / 100000 <= 0.013, `train=${types.train}`);
  assert.ok(types.gate / 100000 >= 0.0028 && types.gate / 100000 <= 0.0066, `gate=${types.gate}`);

  assert.strictEqual(trainCars, trainSpins * 5);
  assert.ok(
    trainEmpty / trainCars >= 0.324 && trainEmpty / trainCars <= 0.364,
    `train empty=${trainEmpty / trainCars}`
  );

  assert.strictEqual(gateLabels.小天门 + gateLabels.天门 + gateLabels.大天门, gateCount);
  assert.ok(
    gateLabels.小天门 / gateCount >= 0.58 && gateLabels.小天门 / gateCount <= 0.72,
    `gate 小天门=${gateLabels.小天门 / gateCount}`
  );
  assert.ok(
    gateLabels.天门 / gateCount >= 0.23 && gateLabels.天门 / gateCount <= 0.37,
    `gate 天门=${gateLabels.天门 / gateCount}`
  );
  assert.ok(
    gateLabels.大天门 / gateCount >= 0.02 && gateLabels.大天门 / gateCount <= 0.10,
    `gate 大天门=${gateLabels.大天门 / gateCount}`
  );
});

summary();
