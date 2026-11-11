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

summary();
