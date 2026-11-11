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

summary();
