# 复古老虎水果机 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 subagent-driven-development（推荐）或 executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在 `tigerMachine/` 下实现一个双击即玩的复古老虎水果机，含押分跑灯、开火车、大三元 / 小三元、天门、猜大小与爆机。

**架构：** `engine.js` 是纯逻辑（浏览器 / Node 通用），`render.js` 负责 Canvas 盘面与水果绘制，`audio.js` 用 WebAudio 合成音效和语音，`game.js` 负责 DOM、动画状态机、输入与自动模式；`index.html` + `style.css` 提供复古机箱。

**技术栈：** 原生 HTML / CSS / JavaScript（ES2018+）、Canvas 2D、WebAudio、Web Speech API；无第三方依赖。

**规格：** `tigerMachine/docs/2026-11-11-tiger-fruit-machine-design.md`

## 全局约束

- 所有新文件只放在 `tigerMachine/` 下，不散落到仓库其他目录。
- 纯本地静态页面，双击 `index.html` 或 `run_tiger.bat` 运行；不起服务器、不联网、不引入 npm 依赖。
- Node 仅用于跑 `node test_engine.js`，版本 18+。
- 中文界面；页面固定显示"纯娱乐 · 虚拟币"。
- 初始 1000 币；单门押分 0–99；投币每次 +100。
- 九个图案赔率固定：小香蕉 4、小芒果 6、苹果 8、香蕉 12、芒果 15、西瓜 20、双星 30、双七 40、BAR 50。
- 概率固定：九门合计 65.6%，LUCK / 跑空 31.4%，彩头 3%。
- 彩头绝对概率：小三元 1.2%、大三元 0.5%、开火车 0.9%、天门 0.4%。
- 猜大小最多 3 次；开 7 通杀。
- 连续 60 局无彩头，下一局强制彩头。
- 爆机阈值 99999，金币不重置。
- 提交时只暂存 `tigerMachine/` 下的目标文件；不要碰 `image_add/__pycache__`、`img_compress/__pycache__` 等既有改动。
- 每个 commit 结尾加：
  `Co-Authored-By: Claude Code <noreply@anthropic.com>`

## 审查重点（Review Focus）

| # | 输入 / 条件 | 正常人期待的行为 | 对应测试 |
| --- | --- | --- | --- |
| 1 | 单门加注超过 99、总押分超过金币、负数或非整数步进 | 拒绝操作，余额和押分不变，界面给出错误提示 | 任务 1 |
| 2 | 中奖后未收分、动画未结束时再次点开始 | 拒绝第二次开局，不重复扣分、不吞掉 pendingWin | 任务 2、任务 7 |
| 3 | 猜大小开 7、猜错、第三次猜对、点收分 | 奖金只入账一次；猜错清零；第三次后自动收分；最多 3 次 | 任务 4、任务 7 |
| 4 | 彩头时只押了部分图案 / 开火车空车 / 天门 | 小三元只赔三小，大三元只赔三大，空车 0，天门按总押分 | 任务 3 |
| 5 | 窗口缩到 1024×640 或高 DPI | 机箱等比缩放，文字不裁切，面板不溢出，LED 不换行 | 任务 5 |

---

## 任务 1：引擎常量与押分

**文件：**
- 创建：`tigerMachine/engine.js`
- 创建：`tigerMachine/test_engine.js`

**接口：**

```js
// engine.js 浏览器挂 window.TigerEngine，Node 用 module.exports
module.exports = {
  SYMBOLS, RING, FEATURES, GATE_WHEEL,
  INITIAL_COINS, MAX_BET, MAX_GUESSES, PITY_SPINS, JACKPOT,
  SYMBOL_SHARE, SYMBOL_PROB, LUCK_PROB, FEATURE_PROB,
  createGame, mulberry32,
};

function createGame({ coins = 1000, rng = Math.random } = {}) -> Game

game.bet(symbolId, delta) -> { ok: true } | { ok: false, error }
game.clearBets() -> { ok: true } | { ok: false, error }
game.betAll(unit) -> { ok: true, added: number } | { ok: false, error }
game.insertCoin(amount = 100) -> { ok: true, coins: number } | { ok: false, error }
game.getState() -> {
  coins, bets, totalBet, pendingWin, spinsSinceFeature,
  guessCount, jackpotArmed, lastResult, canSpin
}
```

- `SYMBOLS` 顺序固定，`id` 分别为 `s_banana / s_mango / apple / banana / mango / watermelon / star / seven / bar`。
- `RING` 是长度 24 的数组，包含 6 个 `'luck'`，其余为上述 `id`；分布：小香蕉 5、小芒果 3、苹果 3、香蕉 2、芒果 / 西瓜 / 双星 / 双七 / BAR 各 1。
- `SYMBOL_PROB[i] = 0.8 / SYMBOLS[i].odds`，合计 0.656；`LUCK_PROB = 1 - 0.656 - 0.03 = 0.314`；`FEATURE_PROB = 0.03`。
- `FEATURES`：`smallThree` 权重 40、`bigThree` 权重 17、`train` 权重 30、`gate` 权重 13。
- 押分错误码：`INVALID_SYMBOL`、`INVALID_DELTA`、`MAX_BET`、`INSUFFICIENT_COINS`、`ROUND_ACTIVE`。
- `ROUND_ACTIVE` = `pendingWin > 0`，此时禁止改注、清注、全押。

- [ ] **步骤 1：编写失败的测试**

在 `test_engine.js` 建立最小测试框架，并写以下用例：

```js
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
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd tigerMachine && node test_engine.js`
预期：失败，报错 `Cannot find module './engine.js'`。

- [ ] **步骤 3：实现 `engine.js` 常量与押分 API**

按上面的接口和常量实现。`createGame` 内部维护 `coins / bets / pendingWin / spinsSinceFeature / guessCount / jackpotArmed / lastResult / forced`。`getState()` 返回 `{ ...state, bets: { ...bets }, totalBet, canSpin }`。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd tigerMachine && node test_engine.js`
预期：全部 `PASS`，退出码 0。

- [ ] **步骤 5：Commit**

```bash
git add tigerMachine/engine.js tigerMachine/test_engine.js
git commit -m "feat(tiger): 水果机引擎常量与押分" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## 任务 2：开奖、符号赔付与收分

**文件：**
- 修改：`tigerMachine/engine.js`
- 修改：`tigerMachine/test_engine.js`

**接口新增：**

```js
game.spin() -> SpinResult
game.collect() -> { collected: number, jackpot: boolean }
game.forceNextSymbol(symbolId) -> void
game.forceNextLuck() -> void
game.forceNextFeature(featureId) -> void
```

```js
SpinResult = {
  kind: 'symbol' | 'luck' | 'feature',
  stopIndex: number,          // 0..23；天门时也指向一个 LUCK 格
  symbolId: string | null,
  feature: null | object,
  win: number,
  pendingWin: number,
  message: string
}
```

- `spin()` 校验顺序：`ROUND_ACTIVE`（pendingWin > 0）→ `NO_BET` → `INSUFFICIENT_COINS`。
- 开局立即扣除 `totalBet`。
- 未强制时按顺序判定：`rng() < 0.03` 彩头；`rng() < 0.03 + 0.656` 九门；否则 LUCK。
- 九门内部按 `SYMBOL_PROB` 加权；停到的格子从该图案的环上格子中随机选。
- 符号中奖：`win = bets[symbolId] * odds`；未押则 0。
- LUCK：`win = 0`，`message = '跑空'`。
- 中奖后 `pendingWin = win`，`guessCount = 0`；`collect()` 把 `pendingWin` 加回 `coins` 并清零。
- 测试用的 `forceNext*` 只影响下一局，使用后自动清除。

- [ ] **步骤 1：编写失败的测试**

```js
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
  assert.strictEqual(g.getState().coins, 1000);
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
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd tigerMachine && node test_engine.js`
预期：新增用例失败，`spin is not a function` 或类似。

- [ ] **步骤 3：实现 `spin()`、`collect()` 与强制结果钩子**

实现时把环上格子索引预计算为 `ringIndicesBySymbol` 和 `luckIndices`。`collect()` 只处理 pendingWin，猜大小留给任务 4。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd tigerMachine && node test_engine.js`
预期：全部 `PASS`。

- [ ] **步骤 5：Commit**

```bash
git add tigerMachine/engine.js tigerMachine/test_engine.js
git commit -m "feat(tiger): 开奖跑灯、符号赔付与收分" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## 任务 3：四种彩头赔付

**文件：**
- 修改：`tigerMachine/engine.js`
- 修改：`tigerMachine/test_engine.js`

**彩头结构：**

```js
// 小三元 / 大三元
feature = {
  type: 'smallThree' | 'bigThree',
  name: '小三元' | '大三元',
  symbols: [{ id, name, odds, bet, win, indices }],
  win, stopIndex
}

// 开火车
feature = {
  type: 'train', name: '开火车',
  carriages: [{ symbolId: string|null, stopIndex, win, empty }],
  win, stopIndex
}

// 天门
feature = {
  type: 'gate', name: '天门',
  wheel: { label: '小天门'|'天门'|'大天门', multiplier: 5|10|50, win },
  win, stopIndex
}
```

- 小三元：`['s_banana','s_mango','apple']`；大三元：`['watermelon','star','seven']`。只赔押过的图案。
- 开火车：固定 5 节。每节权重 = `1/odds`，再加空车权重 `0.43`，总权重 1.25；空车概率 34.4%，空车 `win = 0`。
- 天门：转盘权重 65 / 30 / 5，倍率 5 / 10 / 50，赔付 `totalBet * multiplier`。
- 彩头结果替代普通开奖，不叠加普通符号赔付。

- [ ] **步骤 1：编写失败的测试**

```js
test('小三元只赔三小，不赔其他', () => {
  const g = E.createGame({ rng: seq([0]) });
  g.bet('s_banana', 1); g.bet('s_mango', 2); g.bet('apple', 3); g.bet('bar', 1);
  g.forceNextFeature('smallThree');
  const r = g.spin();
  assert.strictEqual(r.kind, 'feature');
  assert.strictEqual(r.feature.type, 'smallThree');
  assert.strictEqual(r.win, 1*4 + 2*6 + 3*8);
  assert.deepStrictEqual(r.feature.symbols.map(s => s.id), ['s_banana','s_mango','apple']);
});

test('大三元只赔三大', () => {
  const g = E.createGame({ rng: seq([0]) });
  g.bet('watermelon', 1); g.bet('star', 2); g.bet('seven', 3); g.bet('apple', 9);
  g.forceNextFeature('bigThree');
  const r = g.spin();
  assert.strictEqual(r.win, 1*20 + 2*30 + 3*40);
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
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd tigerMachine && node test_engine.js`
预期：彩头用例失败，`feature` 为 `null` 或类型不符。

- [ ] **步骤 3：实现 `buildFeature()` 与三种赔付**

抽离 `pickFeatureId()`、`pickSymbol()`、`pickRingIndexForSymbol()`、`randomLuckIndex()`、`drawCarriage()`、`pickGateWheel()`。`spin()` 在 `kind === 'feature'` 时调用 `buildFeature()` 并把 `win` 写入 `pendingWin`。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd tigerMachine && node test_engine.js`
预期：全部 `PASS`。

- [ ] **步骤 5：Commit**

```bash
git add tigerMachine/engine.js tigerMachine/test_engine.js
git commit -m "feat(tiger): 开火车、大小三元与天门赔付" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## 任务 4：猜大小、保底、爆机与 RTP 回归

**文件：**
- 修改：`tigerMachine/engine.js`
- 修改：`tigerMachine/test_engine.js`

**接口新增：**

```js
game.guess('small' | 'big') -> {
  number, correct, pendingWin, collected,
  autoCollected, guessCount, jackpot
}
```

- 随机开 1–13：`1 + Math.floor(rng() * 13)`。
- 小 = 1–6，大 = 8–13，7 通杀。
- 猜对 `pendingWin *= 2`；猜错 `pendingWin = 0` 并结束。
- 最多 3 次；第 3 次后若仍有奖金，自动收分。
- 任意 `collect()` / 自动收分 / 猜对后都要检查爆机：`coins >= 99999` 时返回 `jackpot: true`，并且 `jackpotArmed = false`；金币跌破 90000 后重新武装。
- 保底：`spinsSinceFeature >= 60` 时，下一局强制彩头（在 `spin()` 判定普通结果之前）。

- [ ] **步骤 1：编写失败的测试**

```js
test('猜对翻倍，收分入账', () => {
  // 第 1 个 rng 给 spin 的停灯格，第 2 个给猜大小
  const g = E.createGame({ rng: seq([0, 4/13]) }); // 开 5
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
  const g = E.createGame({ rng: seq([0, 6/13]) }); // 开 7
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
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd tigerMachine && node test_engine.js`
预期：新增用例失败，`guess is not a function` 等。

- [ ] **步骤 3：实现 `guess()`、保底与爆机**

在 `spin()` 开头检查 `spinsSinceFeature >= PITY_SPINS`；彩头时清零，普通结果时 +1。实现 `maybeJackpot()` 并在所有入账路径调用。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd tigerMachine && node test_engine.js`
预期：全部 `PASS`。

- [ ] **步骤 5：添加蒙特卡洛 RTP 回归测试**

```js
test('10 万局九门均注：RTP 在 0.85–1.05', () => {
  const g = E.createGame({ coins: 1e9, rng: E.mulberry32(20261111) });
  for (const s of E.SYMBOLS) g.bet(s.id, 1);
  let wagered = 0, won = 0, features = 0, trainCount = 0, trainSpins = 0;
  for (let i = 0; i < 100000; i++) {
    const r = g.spin();
    wagered += 9;
    won += r.win;
    if (r.kind === 'feature') {
      features++;
      if (r.feature.type === 'train') { trainSpins++; trainCount += r.feature.carriages.length; }
    }
    g.collect();
  }
  const rtp = won / wagered;
  assert.ok(rtp >= 0.85 && rtp <= 1.05, `RTP=${rtp}`);
  assert.ok(features / 100000 >= 0.015 && features / 100000 <= 0.055, `feature rate=${features / 100000}`);
  assert.strictEqual(trainCount, trainSpins * 5);
});
```

运行：`cd tigerMachine && node test_engine.js`
预期：全部 `PASS`；若 RTP 越界，优先在规格允许范围内微调 `FEATURES` 权重或 `TRAIN_EMPTY_WEIGHT`，不要改赔率。

- [ ] **步骤 6：Commit**

```bash
git add tigerMachine/engine.js tigerMachine/test_engine.js
git commit -m "feat(tiger): 猜大小、彩头保底与爆机" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## 任务 5：机箱外壳与盘面渲染

**文件：**
- 创建：`tigerMachine/index.html`
- 创建：`tigerMachine/style.css`
- 创建：`tigerMachine/render.js`
- 创建：`tigerMachine/game.js`（本任务只做静态渲染，任务 7 扩展）

**页面结构：**

```html
<div id="app" class="cabinet">
  <header class="marquee">…老虎水果机…</header>
  <main class="stage">
    <section class="board-wrap">
      <canvas id="board" width="680" height="680"></canvas>
      <div id="feature-banner" class="feature-banner hidden"></div>
      <div id="guess-panel" class="overlay hidden">…</div>
    </section>
    <aside class="panel">
      <div class="led-row">…金币 / 总押分 / 奖金 / 彩头…</div>
      <div class="chips">…1 / 5 / 10 / 50…</div>
      <div id="bet-list" class="bet-list"></div>
      <div class="actions">…投币 / 全清 / 全押 / 开始 / 自动 / 规则 / 音效…</div>
      <div class="hint">空格 开始 · C 投币 · X 全清 · M 静音</div>
    </aside>
  </main>
  <footer class="status-bar">…</footer>
  <div id="rules-modal" class="modal hidden">…</div>
  <div id="fatal" class="fatal hidden"></div>
</div>
```

**渲染接口：**

```js
window.TigerRender = {
  drawBoard(ctx, state),
  drawFruit(ctx, symbolId, cx, cy, size, opts),
  drawTrain(ctx, progress, carriages),
  drawGateWheel(ctx, wheel, progress),
};

// drawBoard 期望的 state：
{
  ring: TigerEngine.RING,
  symbols: TigerEngine.SYMBOLS,
  bets: { [symbolId]: number },
  litIndex: -1,
  winIndices: [],
  feature: null,
  phase: 'idle',
  time: performance.now(),
}
```

**盘面规格：**

- Canvas 逻辑尺寸 680×680，中心 `(340, 340)`，环半径 255，灯位 60×60。
- 24 个灯位角度：`-Math.PI/2 + i * Math.PI * 2 / 24`。
- 灯位内容：水果图标（约 32px）、赔率数字（10px）。
- 押过的图案：灯位右上角绿色小点。
- 点亮灯位：放大 1.12、金色描边、`shadowBlur` 发光；中奖格金色闪烁。
- 中央天门：半径约 165 的金色圆盘，写"天门"和"×50"，下方三个小标签"小天门 5× / 天门 10× / 大天门 50×"。
- 水果全部用 Canvas 路径绘制，不用 emoji、图片或外部字体；小香蕉 / 小芒果画小一号并在右上角加"小"字角标。
- 双击缩放：`window.addEventListener('resize', fit)`；`fit()` 计算 `scale = Math.min(innerWidth/1280, innerHeight/800, 1.25)`，设置 `#app.style.transform = 'scale(' + scale + ')'`。
- `#app` 固定 1280×800，`transform-origin: center center`；页面用 flex 居中；`overflow: hidden`。
- CRT 扫描线用 `.cabinet::after` 的重复线性渐变，`pointer-events: none`。
- 控制面板使用 flex / grid 自然宽度；不要给中文名称固定字符宽度，避免缩放后裁切。

- [ ] **步骤 1：搭建 `index.html` 与 `style.css`**

按上面的结构写静态外壳。先不接真实数据；`bet-list` 可以留空，由任务 7 生成。每个 LED 盒子显示占位 `0`。

- [ ] **步骤 2：实现 `render.js` 的静态盘面**

实现 `drawBoard`、`drawFruit`、`drawCenter`；先实现 24 灯位、9 种水果、中央天门。跑灯状态 `litIndex` 默认为 -1。`drawTrain` / `drawGateWheel` 可以留空函数，任务 8 补全。

- [ ] **步骤 3：写最小 `game.js` 只做静态渲染**

```js
(function () {
  const canvas = document.getElementById('board');
  const ctx = canvas.getContext('2d');
  let scale = 1;
  function fit() {
    scale = Math.min(innerWidth / 1280, innerHeight / 800, 1.25);
    document.getElementById('app').style.transform = `scale(${scale})`;
    const dpr = devicePixelRatio || 1;
    canvas.width = 680 * dpr;
    canvas.height = 680 * dpr;
    canvas.style.width = '680px';
    canvas.style.height = '680px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  function frame(t) {
    TigerRender.drawBoard(ctx, {
      ring: TigerEngine.RING, symbols: TigerEngine.SYMBOLS,
      bets: {}, litIndex: -1, winIndices: [], feature: null,
      phase: 'idle', time: t,
    });
    requestAnimationFrame(frame);
  }
  addEventListener('resize', fit);
  addEventListener('error', e => {
    const el = document.getElementById('fatal');
    el.textContent = '脚本错误：' + e.message;
    el.classList.remove('hidden');
  });
  fit();
  requestAnimationFrame(frame);
})();
```

- [ ] **步骤 4：用无头 Chrome 截图验证**

```bash
mkdir -p /c/Users/weihuan/AppData/Local/Temp/tiger-shots
"/c/Program Files/Google/Chrome/Application/chrome.exe" --headless=new --disable-gpu --hide-scrollbars \
  --window-size=1280,800 --virtual-time-budget=1500 \
  --screenshot=/c/Users/weihuan/AppData/Local/Temp/tiger-shots/shell-1280.png \
  "file:///D:/000_study/020_code/claude/tigerMachine/index.html"
```

再用同样命令生成 1024×640 的截图。用 Read 工具查看两张图，确认：机箱完整、24 个灯位可见、9 种水果可辨认、中央天门完整、面板文字不裁切、无红色脚本错误条。

- [ ] **步骤 5：Commit**

```bash
git add tigerMachine/index.html tigerMachine/style.css tigerMachine/render.js tigerMachine/game.js
git commit -m "feat(tiger): 复古机箱外壳与盘面渲染" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## 任务 6：WebAudio 音效与语音

**文件：**
- 创建：`tigerMachine/audio.js`
- 修改：`tigerMachine/index.html`（在 `game.js` 之前加 `<script src="audio.js"></script>`）

**接口：**

```js
window.TigerAudio = {
  init(),                 // 首次用户手势时创建/恢复 AudioContext
  setMuted(boolean),
  isMuted(),
  click(), coin(), tick(progress), win(), lose(),
  whistle(), fanfare(),
  speak(text),            // Web Speech API，不可用时静默降级
};
```

- 所有方法在未初始化或静音时直接返回，不抛错。
- `tick(progress)`：`progress` 0–1，频率 180–900Hz，时长 0.02s。
- `coin()`：两个高频短音；`win()`：上行三音；`lose()`：下行两音。
- `whistle()`：汽笛扫频；`fanfare()`：三和弦。
- `speak(text)`：`lang='zh-CN'`、`rate=1.1`、`volume=0.9`；先 `cancel()` 再 `speak()`；静音时取消。
- 若 `window.speechSynthesis` 不存在，直接跳过。

- [ ] **步骤 1：实现 `audio.js`**

用 `OscillatorNode` + `GainNode` 写一个 `beep(freq, duration, type, startOffset)` 辅助函数。`init()` 里处理 `AudioContext` 的 suspended 状态。

- [ ] **步骤 2：接入页面并手动验证**

在 `index.html` 加 `<script src="audio.js"></script>`。在最小 `game.js` 里加一个临时按钮或按键：按 `F9` 依次播放 `coin / win / lose / whistle / fanfare`，并 `speak('开火车啦')`。无头截图无法验证声音，改为在浏览器控制台手动确认，并确保页面加载无报错。

- [ ] **步骤 3：检查控制台**

用无头 Chrome 打开页面，确认 `fatal` 条未出现；再在本地手动点一次页面后按 F9，确认有声音。若浏览器拦截自动播放，确保 `TigerAudio.init()` 在第一次点击/按键里调用。

- [ ] **步骤 4：Commit**

```bash
git add tigerMachine/audio.js tigerMachine/index.html tigerMachine/game.js
git commit -m "feat(tiger): WebAudio 音效与中文语音" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## 任务 7：控制器、押分界面、跑灯与猜大小

**文件：**
- 修改：`tigerMachine/game.js`
- 修改：`tigerMachine/index.html`（补齐按钮与浮层 DOM）
- 修改：`tigerMachine/style.css`（按钮、押注行、浮层状态）

**控制器状态：**

```js
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
};
```

**关键函数：**

```js
function syncUI()                     // 金币 / 总押分 / 奖金 / 彩头进度 / 按钮禁用
function buildBetRows()               // 按 SYMBOLS 生成 9 行，图标用 drawFruit 画在小 canvas
function setChip(unit)
function addBet(symbolId, delta)
function insertCoin(amount = 100)
function clearBets()
function betAll()
function startSpin()                  // 防重入：animating 或 !state.canSpin 直接返回
async function animateSpin(result)    // 至少 2 圈，ease-out，2600ms（fast=900ms）
async function finishRound(result)    // 中奖闪烁/粒子/音效，跑空提示，彩头交给任务 8
function showGuessOrCollect()
function doGuess(choice)
function collectWin()
function toggleAuto()
function scheduleAuto()
function toggleMute()
function openRules() / closeRules()
function resize()
```

**交互规则：**

- 空格 = 开始；C = 投币；X = 全清；M = 静音。输入框 / 浮层打开时不响应快捷键。
- 9 行押注：每行 `−` / `+` 按钮，步进为当前筹码；显示图案、赔率、押分。
- 筹码 1 / 5 / 10 / 50，选中高亮。
- 开始按钮在 `animating`、`pendingWin > 0`、或 `!canSpin` 时禁用。
- 跑灯动画期间 `animating = true`；动画结束后再决定是否弹猜大小。
- 猜大小浮层：显示 pendingWin、剩余次数；按钮"小 1–6""大 8–13""收分"。
- 猜对后更新 pendingWin；猜错或自动收分后 900ms 隐藏浮层；第 3 次后自动收分。
- 自动模式：中奖直接收分，不猜；上一局完全结束后 1.2s 再开局；金币不足或再次点自动时停止。
- `syncUI()` 在每个操作后调用；按钮状态和 LED 必须与 `game.getState()` 一致。
- 爆机：`collectWin()` 返回 `jackpot: true` 时调用 `celebrateJackpot()`（金色粒子 + 大字"爆机" + fanfare），金币不重置。
- 防重入：`ui.spinCount` 只在真正扣分开局时 +1；`startSpin()` 在 `ui.animating` 或 `!state.canSpin` 时直接返回。`?demo=doubleStart` 连续调用两次 `startSpin()`，300ms 后把状态条改为 `doubleStart spins=${ui.spinCount}（应为 1）`，用截图或 `--dump-dom` 验证。

**调试与截图入口：**

```js
const params = new URLSearchParams(location.search);
const FAST = params.get('fast') === '1';
if (params.get('debug') === '1') window.__tiger = { game, ui, startSpin, syncUI };
// demo 值：spin | smallThree | bigThree | train | gate | guess | jackpot | doubleStart
const demo = params.get('demo');
if (demo) setTimeout(() => runDemo(demo), 300);
```

`runDemo` 自动投币、九门各押 1 分；`smallThree` / `bigThree` / `train` / `gate` 先 `forceNextFeature` 再 `startSpin()`；`guess` 先制造一次中奖再弹出猜大小；`jackpot` 直接投币到 99999 并触发一次中奖。

- [ ] **步骤 1：补齐 DOM 与样式**

把 `bet-list` 的行结构、按钮、LED、猜大小浮层、规则浮层写完整；CSS 用 flex/grid，中文名称不设固定字符宽度。

- [ ] **步骤 2：实现押分与 LED 同步**

`buildBetRows()` 生成 9 行；`syncUI()` 更新所有数字和按钮禁用。先不接跑灯，手动点加注/减注/全清/全押/投币，确认数字正确。

- [ ] **步骤 3：实现跑灯与普通开奖**

`startSpin()` 调 `game.spin()`，`animateSpin()` 从 `litIndex` 跑到 `result.stopIndex`；跑灯期间播放 tick；停灯后按结果闪灯/播放中奖或跑空音效。

- [ ] **步骤 4：实现猜大小与收分**

中奖后弹出浮层；猜对翻倍、猜错清零、收分入账；第 3 次自动收分。自动模式跳过猜大小。

- [ ] **步骤 5：用无头 Chrome 验证**

```bash
"/c/Program Files/Google/Chrome/Application/chrome.exe" --headless=new --disable-gpu --hide-scrollbars \
  --window-size=1280,800 --virtual-time-budget=2500 \
  --screenshot=/c/Users/weihuan/AppData/Local/Temp/tiger-shots/board.png \
  "file:///D:/000_study/020_code/claude/tigerMachine/index.html?debug=1&demo=spin&fast=1"
```

用 Read 工具查看截图：9 行押注、LED 数字、跑灯高亮、状态条正常。再生成 `?demo=guess` 截图，确认猜大小浮层可见、按钮不溢出。

再验证防重入：

```bash
"/c/Program Files/Google/Chrome/Application/chrome.exe" --headless=new --disable-gpu \
  --window-size=1280,800 --virtual-time-budget=1200 --dump-dom \
  "file:///D:/000_study/020_code/claude/tigerMachine/index.html?debug=1&fast=1&demo=doubleStart" \
  | grep -o "doubleStart spins=[0-9]*"
```

预期输出：`doubleStart spins=1`。

- [ ] **步骤 6：Commit**

```bash
git add tigerMachine/game.js tigerMachine/index.html tigerMachine/style.css
git commit -m "feat(tiger): 押分界面、跑灯与猜大小" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## 任务 8：开火车、大三元 / 小三元、天门动画

**文件：**
- 修改：`tigerMachine/game.js`
- 修改：`tigerMachine/render.js`
- 修改：`tigerMachine/style.css`（动画相关类，如抖动、金光）

**动画规格：**

```js
async function playFeature(feature)          // 按 feature.type 分发
async function animateTriple(feature, big)   // 小 / 大三元
async function animateTrain(feature)         // 开火车
async function animateGate(feature)          // 天门
```

- **小三元**：依次点亮小香蕉、小芒果、苹果的灯位（每个约 250ms），显示大字"小三元"，`TigerAudio.speak('小三元')` + `fanfare()`；最后逐个显示每个图案的赔付，停留 1.2s。
- **大三元**：同样的节奏，但三个高倍灯位同时闪烁、机箱轻微抖动（CSS class 或 canvas 位移）、金色粒子更多；`speak('大三元')`。
- **开火车**：`whistle()` + `speak('开火车啦')`；在盘面下方画一列小火车，5 节车厢依次移动并停到各自的 `stopIndex`；停在图案上就闪该灯并显示 `+win`，空车显示"空车"；每节间隔约 450ms；最后显示总奖金。
- **天门**：中央大门向两侧打开（render 里画两个金色门扇的位移）；内圈转盘加速旋转约 1.5s，减速停到 `wheel.label`；显示 `label × multiplier` 和总奖金；`fanfare()` + `speak('天门')`。
- 动画期间 `ui.animating = true`，禁止开始、改注、清注；动画结束后交给 `finishRound` 的猜大小/收分流程。
- `?fast=1` 时所有动画时长乘以 0.35。
- `drawTrain` / `drawGateWheel` 在 `render.js` 中实现，均由 `progress` 0–1 驱动，便于截图。

- [ ] **步骤 1：实现三元动画**

在 `playFeature` 里识别 `smallThree` / `bigThree`，按顺序点亮 `feature.symbols` 的 `indices`，显示横幅和赔付。用 `?demo=smallThree&fast=1` 截图确认。

- [ ] **步骤 2：实现开火车动画**

画火车与 5 节车厢，按 `feature.carriages` 的位置依次停靠；空车有独立样式；显示累计奖金。用 `?demo=train&fast=1` 截图确认。

- [ ] **步骤 3：实现天门动画**

中央门扇打开 + 内圈转盘旋转 + 结果高亮。用 `?demo=gate&fast=1` 截图确认。

- [ ] **步骤 4：回归正常流程**

用 `?debug=1` 跑 20 局普通押分，确认彩头结束后还能继续开局；再确认动画中重复点开始无效。

- [ ] **步骤 5：Commit**

```bash
git add tigerMachine/game.js tigerMachine/render.js tigerMachine/style.css
git commit -m "feat(tiger): 开火车、大小三元与天门动画" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## 任务 9：README、启动脚本与最终验收

**文件：**
- 创建：`tigerMachine/README.md`
- 创建：`tigerMachine/run_tiger.bat`
- 修改：`tigerMachine/docs/2026-11-11-tiger-fruit-machine-design.md`（仅在实现与设计有偏差时同步）

**README 必须包含：**

- 一句话介绍 + "纯娱乐 · 虚拟币，不联网"。
- 运行方式：双击 `run_tiger.bat` 或 `index.html`。
- 玩法：押分、跑灯、猜大小、四种彩头、爆机。
- 赔率表（与设计文档一致）。
- 键盘快捷键。
- 测试命令：`node test_engine.js`。
- 调试参数：`?debug=1`、`?fast=1`、`?demo=train|smallThree|bigThree|gate|guess|jackpot|doubleStart`。

**`run_tiger.bat`：**

```bat
@echo off
cd /d "%~dp0"
start "" "index.html"
```

- [ ] **步骤 1：写 README 与启动脚本**

按上面内容写；赔率表从设计文档逐字抄。

- [ ] **步骤 2：跑完整引擎测试**

运行：`cd tigerMachine && node test_engine.js`
预期：所有用例 `PASS`，退出码 0，最后输出 `passed: N, failed: 0`。

- [ ] **步骤 3：跑无头截图验收**

依次生成并查看：

- 1280×800 初始盘面
- 1024×640 初始盘面
- `?demo=spin&fast=1`
- `?demo=smallThree&fast=1`
- `?demo=bigThree&fast=1`
- `?demo=train&fast=1`
- `?demo=gate&fast=1`
- `?demo=guess&fast=1`
- `?demo=jackpot&fast=1`

每张截图确认：无红色 `fatal` 错误条、无文字裁切、无按钮溢出、彩头横幅/浮层可见。

- [ ] **步骤 4：检查文件位置与 Git 状态**

运行：

```bash
git status --short
find tigerMachine -maxdepth 2 -type f | sort
```

预期：所有新增文件都在 `tigerMachine/` 下；`git status` 里只有 `tigerMachine/` 的新增文件和原有的 `image_add/__pycache__`、`img_compress/__pycache__` 改动（后者不要提交）。

- [ ] **步骤 5：Commit**

```bash
git add tigerMachine
git commit -m "docs(tiger): 运行说明、启动脚本与验收记录" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## 最终验收清单

- [ ] `cd tigerMachine && node test_engine.js` 全部通过。
- [ ] 双击 `run_tiger.bat` 能在本地浏览器打开，无需服务器。
- [ ] 投币、加注、减注、全清、全押、开始、自动、静音、规则按钮都可用。
- [ ] 跑灯至少 2 圈，减速停在目标灯位；押中赔付正确，跑空不赔。
- [ ] 小三元 / 大三元 / 开火车 / 天门四种彩头都能通过 `?demo=` 触发并完成动画。
- [ ] 猜大小：猜对翻倍、猜错清零、开 7 通杀、最多 3 次、可随时收分。
- [ ] 连续 60 局无彩头后第 61 局必出彩头。
- [ ] 金币达到 99999 触发爆机庆祝，不重置金币。
- [ ] 1280×800 与 1024×640 下布局完整，无文字裁切。
- [ ] 所有文件位于 `tigerMachine/` 下；没有提交其他项目的改动。
