# 地下城跑团游戏（自包含网页版）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 subagent-driven-development（推荐）或 executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 把 `CLAUDE.md` 的跑团规则实现成一个零依赖、离线可玩、双击即玩、可单文件分享的暗黑哥特网页游戏。

**架构：** 三层解耦——`game-logic.js` 是纯函数核心规则（无 DOM，用 UMD 同时暴露给浏览器全局与 Node `require`），承载所有可测试的数值与流程；`game-ui.js` + `index.html` + `style.css` 是浏览器 UI 层，只做渲染、事件绑定与调用核心；`build.mjs` 把三者合并成 `dist/index.html` 自包含单文件交付物。

**技术栈：** 原生 HTML + CSS + 原生 JS（ES 模块语法，无框架、无构建依赖）。测试用 Node 内置 `node --test`（零第三方依赖）。Node ≥ 18（本机 v26.13.0 已确认可用）。

**规格：** `docs/superpowers/specs/2026-11-16-dungeon-game-design.md`（本计划的论证依据；执行者两份都读）

---

## 全局约束

以下每条对所有任务隐含生效。数值与措辞逐字来自规格。

- **零外部依赖**：不引用任何 CDN、外部字体、外部图片（pollinations 图床一律不依赖）、不引入任何 npm 运行时依赖。离线双击必须能玩。
- **伤害下限为 1**：任何"攻击力 − 防御力"的结果，最低为 1（避免 0/负伤害卡死战斗）。
- **统一伤害公式**：所有攻击（普攻 + 技能）都按 `攻击力 − 对方防御`，下限 1。普攻的攻击力 = 玩家总攻；技能攻击力 = 其固定值（见任务 2 技能表）。怪物同理：普攻 = 怪物攻；技能 = 其技能伤害值（约 2× 攻）。
- **暴击**：玩家所有攻击方式（普攻 + 技能）都有 10% 概率暴击 = 3× 伤害。暴击在"减防之后"判定还是"减防之前"？**判定在最终伤害值上**：先按公式算出基础伤害，再 10% 概率 ×3。怒吼 3× 与暴击 3× 可叠加（先怒吼 ×3 再暴击 ×3，即 ×9）。
- **法力**：战斗中玩家每回合（玩家回合开始时）法力 +5（不超过上限）；施放技能消耗对应法力；**法力不足时该技能不可用**（UI 置灰 + 核心层返回"法力不足"，不消耗、不生效）；战斗结束后**回满玩家法力**。奥术智慧免费 +30 法力。
- **探索判定**：难度值 X 为 `[9,13]` 内的整数；探索点 = d6 骰值 R（1-6）+ 智力；**探索点 > X 才成功**（严格大于，等于 X 为失败）；失败触发惩罚。
- **buff 语义**（见任务 2）：
  - **法力护盾（法师）**：3 回合免疫所有伤害；护盾期间玩家受击伤害 = 0；每承受一次怪物攻击回合数 −1。
  - **格挡反击（战士）**：完全格挡怪物的下一次攻击（该次伤害 = 0），并对怪物造成等于那次本应造成的伤害。
  - **怒吼（战士）**：下一次玩家攻击伤害 ×3，用后失效。
  - **裁决（战士）**：怪物当前 HP < 其上限的 20% 时，直接处决（无视防御与护盾）；否则不生效（视为无效回合，不消耗以外的效果）。
- **HP 恢复经济**：每进入新一层（上一层怪物被击败后）HP 回补上限的 25%；探索成功额外 +10~15；祭坛祈祷回法力或冒风险换较多 HP；获得"HP 上限"类奖励时上限提升并**回满 HP**。
- **必遇怪**：每层 1–2 次探索后**必须**触发一次怪物遭遇；击败后进入下一层。
- **20 层全做**：20 个怪物（第 20 层为最终 Boss，数值最强）；击败 20 层 Boss 获得「复苏之心」→ 胜利结局。
- **玩家先手**：每回合玩家先行动。
- **自由输入**：每轮末尾"说出你想做什么"，做"关键词→回应 + 统一兜底文案"，**不**做完整自然语言解析。
- **UI**：暗黑哥特（深色底、火把暖光/血红点缀）；每步给有序号的行动选项；战斗日志滚动显示；面板实时显示 HP/法力/攻/防/智力/装备/当前层；场景用 CSS 渐变 + emoji（不依赖外链）；移动端自适应。
- **提交卫生**：只 add/commit `demo_word/` 下本任务相关文件，绝不带进 monorepo 里其他项目（cal/farmer/snake_game 等）的改动；`dist/` 是生成物，进 `demo_word/.gitignore`。

---

## 审查重点（Review Focus）

规格隐含、最可能伤到玩家的失败模式（最严重的排最前）。每条已在对应任务的测试里钉死：

1. **战斗数值算错**（HP、法力、暴击、伤害、buff 叠加）——规格反复强调"不能出任何错，极其严重失误"。→ 任务 2 的纯函数单元测试 + 任务 8 全流程手测共同钉死。
2. **攻 ≤ 防时打出 0/负伤害**导致战斗卡死。→ 任务 1 `calcDamage` 下限 1 的边界测试。
3. **法力不足时技能仍生效 / 战斗结束后没回满法力**。→ 任务 2 "法力不足拦截""战斗结束回满"测试。
4. **buff（护盾/格挡/怒吼/裁决）到期时机错或异常叠加**。→ 任务 2 buff 到期与叠加测试。
5. **探索点恰好等于难度 X 被误判为成功**（规格要求严格大于）。→ 任务 1 `rollExploration` 边界测试（points === X → 失败；points === X+1 → 成功）。
6. **离线/断网下页面打不开或功能失效**（误引了 CDN、外部图床、相对路径资源）。→ 任务 5 "无外链"检查 + 任务 8 断网全流程手测。

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `game-logic.js` | 纯函数核心规则（无 DOM）。UMD：浏览器暴露 `window.GameLogic`，Node 暴露 `module.exports`。承载全部可测试的数值、buff、流程、数据表。 |
| `tests/game-logic.test.js` | `node --test` 单元测试，覆盖核心数值/buff/流程。 |
| `index.html` | 入口页：DOM 结构 + 引入 `style.css`、`game-logic.js`、`game-ui.js`。 |
| `style.css` | 暗黑哥特主题：CSS 变量、布局、组件、移动端自适应。 |
| `game-ui.js` | 浏览器 UI 层：角色选择、面板渲染、场景渲染、探索/互动/战斗的事件绑定与日志；只调用 `GameLogic`，不写数值规则。 |
| `build.mjs` | 读 `index.html` + `style.css` + `game-logic.js` + `game-ui.js`，内联合并成 `dist/index.html` 自包含单文件。 |
| `dist/index.html` | 交付物：单文件、可发送、离线双击即玩。**生成物，进 `.gitignore`**。 |
| `README.md` | 怎么本地跑 / 怎么测 / 怎么构建单文件 / 怎么发给别人。 |
| `demo_word/.gitignore` | 忽略 `dist/`、`node_modules/`。 |

`game-logic.js` 的 UMD 骨架（所有任务共享，任务 1 建立）：

```js
(function (global) {
  'use strict';
  // ... 常量、纯函数、数据表 ...
  const GameLogic = { /* 导出的 API */ };
  if (typeof module !== 'undefined' && module.exports) module.exports = GameLogic;
  else global.GameLogic = GameLogic;
})(typeof self !== 'undefined' ? self : this);
```

---

## 任务 1：核心数值纯函数 + 测试基建

**文件：**
- 创建：`game-logic.js`
- 创建：`tests/game-logic.test.js`
- 创建：`demo_word/.gitignore`

- [ ] **步骤 1：编写失败的测试**

`tests/game-logic.test.js`：

```js
const test = require('node:test');
const assert = require('node:assert');
const GL = require('../game-logic.js');

test('calcDamage 下限为 1（攻 ≤ 防不打负）', () => {
  assert.equal(GL.calcDamage(5, 10), 1);
  assert.equal(GL.calcDamage(15, 10), 5);
  assert.equal(GL.calcDamage(30, 3), 27);
});

test('applyCrit 暴击 = 3×，非暴击不变', () => {
  assert.equal(GL.applyCrit(27, true), 81);
  assert.equal(GL.applyCrit(27, false), 27);
});

test('MANA_PER_TURN = 5', () => {
  assert.equal(GL.MANA_PER_TURN, 5);
});

test('explorationPoints = 骰值 + 智力', () => {
  assert.equal(GL.explorationPoints(8, 6), 14);
  assert.equal(GL.explorationPoints(5, 1), 6);
});

test('rollExploration 成功需严格大于难度 X（points === X 为失败）', () => {
  // 用固定 rng 与固定 difficulty 便于断言：直接测判定函数
  assert.equal(GL.judgeExploration(13, 13), false); // 13 > 13 为假
  assert.equal(GL.judgeExploration(14, 13), true);  // 14 > 13 为真
  assert.equal(GL.judgeExploration(9, 13), false);  // 9 > 13 为假
});

test('rollExploration 返回结构且难度在 [9,13]', () => {
  let ok = true;
  for (let i = 0; i < 200; i++) {
    const r = GL.rollExploration(8, Math.random);
    if (!(r.difficulty >= 9 && r.difficulty <= 13)) ok = false;
    if (!(r.roll >= 1 && r.roll <= 6)) ok = false;
    if (typeof r.success !== 'boolean') ok = false;
  }
  assert.ok(ok);
});
```

- [ ] **步骤 2：运行测试验证失败**

运行：`node --test tests/game-logic.test.js`
预期：FAIL，报错 `Cannot find module '../game-logic.js'`（或 `GL.calcDamage is not a function`）

- [ ] **步骤 3：在 `game-logic.js` 中实现 UMD 骨架 + 基础纯函数**

导出（签名，函数体由实现者写）：
- `calcDamage(atk: number, def: number): number` — 返回 `max(1, atk - def)`。
- `applyCrit(baseDamage: number, isCrit: boolean): number` — 暴击返回 `baseDamage * 3`，否则原值。
- `MANA_PER_TURN: number` — 常量 `5`。
- `explorationPoints(intel: number, roll: number): number` — 返回 `intel + roll`。
- `judgeExploration(points: number, difficulty: number): boolean` — 返回 `points > difficulty`（严格大于）。
- `rollExploration(intel: number, rng: () => number): { difficulty: number, roll: number, points: number, success: boolean }` — `difficulty` 取 `[9,13]` 随机整数，`roll` 取 `[1,6]` 随机整数，`points = explorationPoints`，`success = judgeExploration(points, difficulty)`。`rng` 为注入的随机源（测试可注入固定值）。

- [ ] **步骤 4：运行测试验证通过**

运行：`node --test tests/game-logic.test.js`
预期：PASS（全部用例通过）

- [ ] **步骤 5：创建 `demo_word/.gitignore` 并 Commit**

`demo_word/.gitignore`：
```
dist/
node_modules/
*.corrupt-*.json
```

```bash
git add demo_word/game-logic.js demo_word/tests/game-logic.test.js demo_word/.gitignore
git commit -m "feat(dungeon): 核心数值纯函数（伤害下限/暴击/法力/探索判定）+ node:test 基建"
```

---

## 任务 2：战斗纯函数（玩家攻击 / 怪物回合 / buff / 技能表）

**文件：**
- 修改：`game-logic.js`
- 测试：`tests/game-logic.test.js`

技能表（确切值，逐字来自规格；`cost` = 法力消耗，`dmg` = 攻击力用于减防公式，`type` 区分普攻/技能/特殊）：

```
MAGE:
  attack        普攻            cost 0   dmg = totalAtk
  fireball      火球术          cost 10  dmg 30
  shield        法力护盾        cost 20  buff shield=3
  arcana        奥术智慧        cost 0   mana +30
  blizzard      暴风雪          cost 30  dmg 20
WARRIOR:
  attack        普攻            cost 0   dmg = totalAtk
  counter       格挡反击        cost 10  buff counter=1
  roar          怒吼            cost 20  buff roar=1
  whirlwind     旋风斩          cost 20  dmg 30
  execute       裁决            cost 30  处决 HP<20% 上限 的敌人
```

战斗状态对象（`newBattle` 产出）：

```
battle = {
  player: { /* 引用任务1的角色 state，见任务4 */ },
  monster: { name, hp, maxHp, atk, def, skillDmg },
  buff: { shield: 0, counter: 0, roar: 0 },
  over: false,
  playerWon: false
}
```

- [ ] **步骤 1：编写失败的测试**

追加到 `tests/game-logic.test.js`：

```js
const M = () => ({ name:'测试怪', hp:50, maxHp:50, atk:10, def:2, skillDmg:20 });

test('playerAction 普攻 = 总攻 - 怪物防，下限 1', () => {
  const b = GL.newBattle({ atk:15, def:5, intel:5, equipment:{} }, M());
  const r = GL.playerAction(b, 'attack', () => 0.9); // 0.9 → 非暴击
  assert.equal(r.damage, 13); // 15 - 2
  assert.equal(r.isCrit, false);
});

test('playerAction 技能 fireball 伤害 = 30 - 怪物防', () => {
  const b = GL.newBattle({ atk:5, def:5, intel:8, equipment:{} }, M());
  const r = GL.playerAction(b, 'fireball', () => 0.9);
  assert.equal(r.damage, 28); // 30 - 2
  assert.equal(r.manaCost, 10);
});

test('暴击 3×（rng < 0.1 触发）', () => {
  const b = GL.newBattle({ atk:15, def:5, intel:5, equipment:{} }, M());
  const r = GL.playerAction(b, 'attack', () => 0.05); // 0.05 < 0.1 → 暴击
  assert.equal(r.damage, 13 * 3);
  assert.equal(r.isCrit, true);
});

test('法力不足时技能不可用（不消耗、不生效、不造成伤害）', () => {
  const p = { atk:5, def:5, intel:8, mana:5, maxMana:100, equipment:{} };
  const b = GL.newBattle(p, M());
  const r = GL.playerAction(b, 'fireball', () => 0.9); // 需 10 法力，只有 5
  assert.equal(r.ok, false);
  assert.equal(r.manaCost, 0);
  assert.equal(b.player.mana, 5);
  assert.equal(b.monster.hp, 50);
});

test('法力护盾 3 回合免疫：护盾期间受击伤害 = 0', () => {
  const p = { atk:5, def:5, intel:8, mana:100, maxMana:100, equipment:{} };
  const b = GL.newBattle(p, M());
  GL.playerAction(b, 'shield', () => 0.9); // 加护盾
  const hit1 = GL.monsterTurn(b, () => 0.9);
  const hit2 = GL.monsterTurn(b, () => 0.9);
  assert.equal(hit1.damage, 0);
  assert.equal(hit2.damage, 0);
  assert.equal(b.buff.shield, 1); // 3 - 2
});

test('格挡反击：格挡下次伤害 = 0 且等量反伤怪物', () => {
  const p = { atk:15, def:5, intel:5, mana:100, maxMana:50, equipment:{} };
  const b = GL.newBattle(p, M()); // 怪物攻 10，def 2 → 普攻伤害 = max(1,10-5)=5
  GL.playerAction(b, 'counter', () => 0.9);
  const m = b.monster.hp;
  const hit = GL.monsterTurn(b, () => 0.9); // 怪物普攻 5 被格挡
  assert.equal(hit.damage, 0);
  assert.equal(b.monster.hp, m - 5); // 反伤 5
});

test('怒吼：下次攻击 ×3，用后失效', () => {
  const p = { atk:15, def:5, intel:5, mana:100, maxMana:50, equipment:{} };
  const b = GL.newBattle(p, M());
  GL.playerAction(b, 'roar', () => 0.9);
  const r = GL.playerAction(b, 'attack', () => 0.9);
  assert.equal(r.damage, 13 * 3); // 怒吼 ×3
  assert.equal(b.buff.roar, 0);
});

test('怒吼 ×3 与暴击 3× 可叠加（×9）', () => {
  const p = { atk:15, def:5, intel:5, mana:100, maxMana:50, equipment:{} };
  const b = GL.newBattle(p, M());
  GL.playerAction(b, 'roar', () => 0.9);
  const r = GL.playerAction(b, 'attack', () => 0.05); // 暴击
  assert.equal(r.damage, 13 * 3 * 3);
});

test('裁决：处决 HP<20%上限 的敌人；否则不生效', () => {
  const p = { atk:15, def:5, intel:5, mana:100, maxMana:50, equipment:{} };
  const b = GL.newBattle(p, M()); // maxHp 50，20% = 10
  b.monster.hp = 9; // < 10
  const r = GL.playerAction(b, 'execute', () => 0.9);
  assert.equal(b.monster.hp, 0);
  assert.equal(b.over, true);
  assert.equal(b.playerWon, true);
  // 另一局：HP 未低于 20%
  const b2 = GL.newBattle(p, M());
  b2.monster.hp = 30;
  const r2 = GL.playerAction(b2, 'execute', () => 0.9);
  assert.equal(b2.monster.hp, 30);
  assert.equal(r2.executed, false);
});

test('怪物回合：50% 概率用技能(技能伤害值)，否则普攻；均受玩家防御减伤', () => {
  const p = { atk:5, def:5, intel:8, mana:100, maxMana:100, equipment:{} };
  // rng 控制：0.4 → 普攻（<0.5? 定义为 rng<0.5 用技能）；固定验证两种
  const b = GL.newBattle(p, M());
  const normal = GL.monsterTurn(b, () => 0.9); // > 0.5 → 普攻
  assert.equal(normal.usedSkill, false);
  assert.equal(normal.damage, Math.max(1, 10 - 5)); // 5
  const b2 = GL.newBattle(p, M());
  const skill = GL.monsterTurn(b2, () => 0.1); // < 0.5 → 技能
  assert.equal(skill.usedSkill, true);
  assert.equal(skill.damage, Math.max(1, 20 - 5)); // 15
});

test('每回合玩家法力 +5（回合开始），不超过上限', () => {
  const p = { atk:5, def:5, intel:8, mana:98, maxMana:100, equipment:{} };
  const b = GL.newBattle(p, M());
  GL.startPlayerTurn(b); // 应 +5，但封顶 100
  assert.equal(b.player.mana, 100);
});

test('战斗结束回满玩家法力', () => {
  const p = { atk:5, def:5, intel:8, mana:20, maxMana:100, equipment:{} };
  const b = GL.newBattle(p, M());
  b.over = true; b.playerWon = true;
  GL.endCombat(b);
  assert.equal(b.player.mana, 100);
});
```

- [ ] **步骤 2：运行测试验证失败**

运行：`node --test tests/game-logic.test.js`
预期：FAIL，`GL.newBattle is not a function` 等（新函数未定义）

- [ ] **步骤 3：在 `game-logic.js` 中实现战斗纯函数**

导出（签名；函数体由实现者按"全局约束"的 buff 语义与统一伤害公式实现）：
- `SKILLS: { MAGE: {...}, WARRIOR: {...} }` — 上文技能表（含 `cost`、`dmg`（普攻为 null，取 totalAtk）、`type`）。
- `newBattle(playerState: object, monster: { name, hp, maxHp, atk, def, skillDmg }): battle` — 构建战斗对象（见上文结构），`buff` 全 0。
- `totalAtk(playerState): number` — `playerState.atk + (equipment.weapon?.atk || 0)`。
- `startPlayerTurn(battle): void` — 法力 `+MANA_PER_TURN`，封顶 `maxMana`。
- `playerAction(battle, actionId: string, rng: () => number): { ok: boolean, damage: number, isCrit: boolean, manaCost: number, usedSkill: boolean, executed?: boolean, log: string }`：
  - 解析技能；校验法力（不足则 `ok:false, manaCost:0, damage:0`，不改状态）。
  - buff 型技能（shield/counter/roar/arcana）设置对应 buff 或回法力。
  - execute：怪物 `hp < maxHp*0.2` 则处决（`hp=0, over, playerWon`），否则 `executed:false`。
  - 伤害型：基础伤害 = `dmg`（或 totalAtk）− 怪物 `def`，下限 1；怒吼待发则 ×3（用后清）；`rng()<0.1` 暴击 ×3；扣怪物 HP；扣玩家法力。
- `monsterTurn(battle, rng: () => number): { damage: number, usedSkill: boolean, log: string }`：
  - `rng() < 0.5` 用技能（技能伤害值），否则普攻（怪物攻）；减玩家 `def`（含护甲），下限 1。
  - 护盾 `buff.shield>0` 时伤害 = 0，且 `shield--`。
  - 格挡反击 `buff.counter>0` 时伤害 = 0，对怪物造成等于该次本应伤害的反伤，`counter=0`。
  - 扣玩家 HP。
- `endCombat(battle): void` — 玩家法力回满 `maxMana`。
- 战斗结束判定（`playerAction`/`monsterTurn` 内）：怪物 `hp<=0` → `over, playerWon`；玩家 `hp<=0` → `over, playerWon:false`。

- [ ] **步骤 4：运行测试验证通过**

运行：`node --test tests/game-logic.test.js`
预期：PASS（含任务 1 与任务 2 全部用例）

- [ ] **步骤 5：Commit**

```bash
git add demo_word/game-logic.js demo_word/tests/game-logic.test.js
git commit -m "feat(dungeon): 战斗纯函数（玩家/怪物回合、暴击、buff、技能表、法力）"
```

---

## 任务 3：奖励 / 装备 / HP 经济纯函数

**文件：**
- 修改：`game-logic.js`
- 测试：`tests/game-logic.test.js`

奖励二选一（随机）：a) 属性成长；b) 装备。装备三槽：`weapon(+atk)` / `armor(+def)` / `trinket(+intel 或 回法)`；同槽取更高者替换，否则丢弃。

- [ ] **步骤 1：编写失败的测试**

```js
test('applyStatReward 属性成长：攻/防/HP上限/智力', () => {
  const p = { atk:5, def:5, intel:8, hp:80, maxHp:100, mana:50, maxMana:100, equipment:{} };
  GL.applyStatReward(p, { kind:'atk', amount:2 });
  assert.equal(p.atk, 7);
  GL.applyStatReward(p, { kind:'hpMax', amount:20 });
  assert.equal(p.maxHp, 120);
  assert.equal(p.hp, 120); // HP 上限奖励回满
});

test('applyEquipment 同槽取更高替换，否则丢弃', () => {
  const p = { atk:5, def:5, intel:8, hp:100, maxHp:100, mana:100, maxMana:100, equipment:{} };
  GL.applyEquipment(p, { slot:'weapon', name:'铁剑', atk:3 });
  assert.equal(p.equipment.weapon.atk, 3);
  GL.applyEquipment(p, { slot:'weapon', name:'木剑', atk:1 }); // 更低 → 丢弃，保留铁剑
  assert.equal(p.equipment.weapon.name, '铁剑');
  assert.equal(p.equipment.weapon.atk, 3);
  GL.applyEquipment(p, { slot:'armor', name:'皮甲', def:2 });
  assert.equal(p.equipment.armor.def, 2);
});

test('totalAtk 计入武器加成', () => {
  const p = { atk:5, equipment:{ weapon:{ name:'铁剑', atk:3 } } };
  assert.equal(GL.totalAtk(p), 8);
});

test('healOnNewFloor 回补上限 25%（不超过上限）', () => {
  const p = { hp:10, maxHp:100, mana:0, maxMana:100 };
  GL.healOnNewFloor(p);
  assert.equal(p.hp, 35); // 10 + 25
  p.hp = 95;
  GL.healOnNewFloor(p);
  assert.equal(p.hp, 100); // 封顶
});

test('healExploreSuccess 探索成功 +10~15，封顶上限', () => {
  const p = { hp:95, maxHp:100 };
  GL.healExploreSuccess(p);
  assert.ok(p.hp >= 100 && p.hp <= 110); // 至少回满
  assert.ok(p.hp <= 100); // 但封顶 100
});
```

- [ ] **步骤 2：运行测试验证失败**

运行：`node --test tests/game-logic.test.js`
预期：FAIL，`GL.applyStatReward is not a function`

- [ ] **步骤 3：在 `game-logic.js` 中实现**

导出（签名）：
- `applyStatReward(player, { kind, amount }): void` — `kind ∈ {atk, def, hpMax, intel}`；`hpMax` 提升 `maxHp` 并回满 `hp`；其余直接加对应属性。
- `applyEquipment(player, { slot, name, atk?, def?, intel?, manaRegen? }): void` — 同槽已有且旧数值更高则丢弃；否则替换。
- `rollReward(rng: () => number): object` — 随机返回属性成长或装备对象（数值范围：攻 +1~3 / 防 +1~2 / HP上限 +10~20 / 智力 +1；武器 +攻 2~6 / 护甲 +防 1~4 / 饰品 +智力 1~2 或 每层回法）。
- `healOnNewFloor(player): void` — `hp = min(maxHp, hp + maxHp*0.25)`。
- `healExploreSuccess(player): void` — `hp = min(maxHp, hp + 随机10~15)`。
- `healAltar(player, rng): object` — 返回 `{ healed, manaHealed, riskTaken, log }`：祈祷回法力，或冒风险换较多 HP。
- `totalDef(player): number` — `def + (equipment.armor?.def || 0)`（任务 2 怪物回合减防用）。

- [ ] **步骤 4：运行测试验证通过**

运行：`node --test tests/game-logic.test.js`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add demo_word/game-logic.js demo_word/tests/game-logic.test.js
git commit -m "feat(dungeon): 奖励/装备槽/HP 经济纯函数"
```

---

## 任务 4：游戏流程状态机 + 20 层怪物数据

**文件：**
- 修改：`game-logic.js`
- 测试：`tests/game-logic.test.js`

20 层怪物曲线（确切值；`skillDmg` ≈ 2× 攻；第 20 层为最终 Boss）：

```
层  名称          HP   攻   防  技能伤害
1   洞穴巨鼠      50   7    3   14
2   腐尸          70   9    4   18
3   幽影蝙蝠      90   11   5   22
4   毒液蛛        110  13   6   26
5   骷髅守卫      130  15   7   30
6   嗜血狼        150  17   8   34
7   地精掠夺者    170  19   9   38
8   石像鬼        190  21   10  42
9   暗影刺客      210  23   11  46
10  深渊骑士      230  25   12  50
11  毒龙幼崽      250  27   13  54
12  血魔          270  29   14  58
13  亡魂骑士      290  31   15  62
14  熔岩兽        310  33   16  66
15  虚空行者      330  35   17  70
16  冰霜巨人      350  37   18  74
17  堕落天使      370  39   19  78
18  龙裔          390  41   20  82
19  深渊领主      410  43   21  86
20  复苏之影(最终Boss)  480  48  24  96
```

角色初始值（规格 7.1）：
```
法师  hp100 maxHp100 mana100 maxMana100 atk5 def5 intel8
战士  hp200 maxHp200 mana50  maxMana50  atk15 def10 intel5
```

- [ ] **步骤 1：编写失败的测试**

```js
test('newGame 法师初始值正确', () => {
  const s = GL.newGame('mage');
  assert.equal(s.hp, 100); assert.equal(s.maxHp, 100);
  assert.equal(s.mana, 100); assert.equal(s.atk, 5); assert.equal(s.def, 5); assert.equal(s.intel, 8);
  assert.equal(s.floor, 1);
});

test('newGame 战士初始值正确', () => {
  const s = GL.newGame('warrior');
  assert.equal(s.hp, 200); assert.equal(s.mana, 50); assert.equal(s.atk, 15); assert.equal(s.def, 10);
});

test('MONSTERS 有 20 个，第 20 个是最终 Boss', () => {
  assert.equal(GL.MONSTERS.length, 20);
  assert.equal(GL.MONSTERS[19].name, '复苏之影(最终Boss)');
  assert.ok(GL.MONSTERS[19].hp > GL.MONSTERS[0].hp); // 曲线递增
});

test('shouldEncounter：1-2 次探索后必遇怪', () => {
  const s = GL.newGame('mage');
  assert.equal(GL.shouldEncounter(s, 0), false);
  assert.equal(GL.shouldEncounter(s, 1), true);  // ≥1 次探索
  assert.equal(GL.shouldEncounter(s, 2), true);
});

test('advanceFloor 击败怪物后进入下一层，并回补 25% HP', () => {
  const s = GL.newGame('mage');
  s.hp = 10; // 低血
  GL.advanceFloor(s);
  assert.equal(s.floor, 2);
  assert.ok(s.hp >= 35); // 回补 25%
});

test('checkVictory：击败 20 层 Boss → 胜利', () => {
  const s = GL.newGame('mage');
  s.floor = 20;
  assert.equal(GL.checkVictory(s, true), true);  // 20 层且击败
  assert.equal(GL.checkVictory(s, false), false); // 未击败
});

test('checkDefeat：玩家 HP≤0 → 失败', () => {
  const s = GL.newGame('mage');
  s.hp = 0;
  assert.equal(GL.checkDefeat(s), true);
  s.hp = 1;
  assert.equal(GL.checkDefeat(s), false);
});

test('getFloorContent 返回该层怪物与互动元素', () => {
  const c = GL.getFloorContent(1);
  assert.equal(c.monster.name, '洞穴巨鼠');
  assert.ok(Array.isArray(c.interactions));
  assert.ok(c.interactions.length >= 1);
});
```

- [ ] **步骤 2：运行测试验证失败**

运行：`node --test tests/game-logic.test.js`
预期：FAIL，`GL.newGame is not a function`

- [ ] **步骤 3：在 `game-logic.js` 中实现**

导出（签名）：
- `CHARS: { mage: {...}, warrior: {...} }` — 上文初始值。
- `MONSTERS: Array<{ name, hp, maxHp, atk, def, skillDmg }>` — 上文 20 行曲线（`maxHp = hp`）。
- `newGame(charType: 'mage'|'warrior'): state` — 按 `CHARS` 建状态，`floor:1, exploredThisFloor:0, equipment:{}, over:false, won:false`。
- `shouldEncounter(state, exploredCount: number): boolean` — 返回 `exploredCount >= 1`（1–2 次探索后必遇怪）。
- `advanceFloor(state): void` — `floor++`、`exploredThisFloor=0`、调 `healOnNewFloor(state)`；若 `floor > 20` 标记结束。
- `checkVictory(state, monsterDefeated: boolean): boolean` — `state.floor === 20 && monsterDefeated`。
- `checkDefeat(state): boolean` — `state.hp <= 0`。
- `getFloorContent(floor: number): { monster, interactions: Array<string> }` — 返回该层怪物（`MONSTERS[floor-1]`）与该层互动元素 id 列表（从 `box`/`puzzle`/`rps`/`altar`/`trap` 中选 1–3 个，含随机性用 `rng` 参数可选注入）。

- [ ] **步骤 4：运行测试验证通过**

运行：`node --test tests/game-logic.test.js`
预期：PASS

- [ ] **步骤 5：Commit**

```bash
git add demo_word/game-logic.js demo_word/tests/game-logic.test.js
git commit -m "feat(dungeon): 流程状态机 + 20 层怪物曲线数据"
```

---

## 任务 5：UI 骨架 — 角色选择 + 面板 + CSS 场景（无外链）

**文件：**
- 创建：`index.html`
- 创建：`style.css`
- 创建：`game-ui.js`

- [ ] **步骤 1：创建 `index.html` 结构**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>地下城跑团</title>
  <link rel="stylesheet" href="style.css" />
</head>
<body>
  <div id="app"></div>
  <script src="game-logic.js"></script>
  <script src="game-ui.js"></script>
</body>
</html>
```

- [ ] **步骤 2：创建 `style.css` 暗黑哥特主题**

定义 CSS 变量（深底 `#0d0a0f`、暖光 `#d4a04a`、血红 `#a12a2a`、暗金边 `#3a2f22`），实现：角色选择卡片、HP/法力条、面板、选项按钮、战斗日志滚动区、场景卡（CSS 渐变 + emoji）。移动端 `@media (max-width:600px)` 单列布局。不引用任何外链字体/图片。

- [ ] **步骤 3：创建 `game-ui.js`（骨架）**

职责（只渲染 + 绑定，数值规则一律调 `window.GameLogic`）：
- `renderCharSelect()` — 渲染法师/战士卡片（属性来自 `GameLogic.CHARS`），点击 → `startGame(charType)`。
- `startGame(charType)` — `state = GameLogic.newGame(charType)`；进入楼层视图。
- `renderPanel()` — 显示 HP/法力条、攻/防/智力（含装备加成 `totalAtk`/`totalDef`）、装备、当前层。
- `renderScene(floor)` — 用 CSS 渐变 + 1–2 个 emoji 营造该层氛围（数据来自 `getFloorContent`），不加载任何外部图片。
- `renderFloor()` — 描述房间 + 有序号选项（探索要素 + 遭遇怪 + "说出你想做什么"）。
- `log(msg)` — 追加到战斗/事件日志滚动区。
- 初始化：页面加载后调 `renderCharSelect()`。

- [ ] **步骤 4：浏览器验证**

运行：在 `demo_word/` 下打开 `index.html`（浏览器直接打开）。
预期：看到暗黑风格的角色选择；点"法师"进入第 1 层，面板显示 HP100/法力100/攻5/防5/智8/层数1，场景有 CSS 氛围；无控制台报错；断网（DevTools→Network→Offline）下功能仍正常。

- [ ] **步骤 5：Commit**

```bash
git add demo_word/index.html demo_word/style.css demo_word/game-ui.js
git commit -m "feat(dungeon): UI 骨架（角色选择/面板/CSS 场景，零外链）"
```

---

## 任务 6：UI — 探索判定 + 互动元素 + 自由输入

**文件：**
- 修改：`game-ui.js`
- 修改：`style.css`

互动元素（每层随机 1–3 个）：
- **箱子**：打开得奖励（调 `rollReward`）；小概率陷阱（小伤害）。
- **谜题机关**：二选一判定；成功得奖励，失败少量伤害。
- **猜拳石像**：石头剪刀布；赢奖励、输小惩罚。
- **神秘祭坛**：祈祷回法力，或冒风险换大奖励/较多 HP（调 `healAltar`）。
- **陷阱通道**：小概率伤害，可先"探查"（走探索判定）规避。

- [ ] **步骤 1：实现探索判定 UI**

`doExplore()` — 调 `GameLogic.rollExploration(state.intel, Math.random)`，展示：难度 X、骰值 R、探索点、成功/失败；成功调 `healExploreSuccess` + 可能奖励；失败小伤害或触发怪物（走任务 7 战斗）。

- [ ] **步骤 2：实现五个互动元素**

每个渲染成有序号选项；点击走对应判定（`rollReward`/`healAltar`/猜拳/探查），结果进日志并更新面板。

- [ ] **步骤 3：实现自由输入**

底部输入框"说出你想做什么"。关键词→回应映射（如含"箱"→打开箱子；"祭坛"→祈祷；"走"→下一层；"打/攻击"→遇怪）；无匹配 → 统一兜底"（这里没有能这样做的。请选择上方编号选项，或换个说法。）"。不做 NLP 解析。

- [ ] **步骤 4：浏览器验证**

运行：浏览器打开 `index.html`。
预期：探索显示难度/骰值/判定；五种互动都能触发并有合理结果；自由输入命中关键词有回应、无匹配有兜底；面板实时刷新；断网仍可用。

- [ ] **步骤 5：Commit**

```bash
git add demo_word/game-ui.js demo_word/style.css
git commit -m "feat(dungeon): 探索判定 + 五种互动元素 + 自由输入（关键词→回应）"
```

---

## 任务 7：UI — 战斗界面 + 日志 + 胜负结局

**文件：**
- 修改：`game-ui.js`
- 修改：`style.css`

- [ ] **步骤 1：实现战斗界面**

`startBattle()` — `battle = GameLogic.newBattle(state, getFloorContent(floor).monster)`；渲染怪物（名称/HP 条/简介）。
`renderBattleOptions()` — 有序号选项：普攻 + 该角色已掌握的技能（`GameLogic.SKILLS[charType]`），法力不足的技能置灰并标注"法力不足"。
`onPlayerAction(actionId)` — `startPlayerTurn` → `playerAction(battle, actionId, Math.random)` → 日志 → 怪物 HP 更新 → 若未结束 `monsterTurn` → 日志 → 检查胜负。

- [ ] **步骤 2：实现战斗日志与 buff 显示**

`log()` 滚动显示每回合（谁做了什么、伤害/暴击/法力变化、护盾剩余、格挡/怒吼待发）。面板显示 buff 状态。

- [ ] **步骤 3：实现胜负结局**

怪物 HP≤0：`endCombat`（回满法力）→ 掉落（`rollReward`）→ `advanceFloor` + `healOnNewFloor` → 若 20 层 Boss 则「复苏之心」胜利结局；否则下一层。
玩家 HP≤0：失败结局 + "重新选择角色"按钮（`renderCharSelect` 重开）。

- [ ] **步骤 4：浏览器验证**

运行：浏览器打开 `index.html`，打一场完整战斗。
预期：玩家先手；普攻/技能伤害正确（与核心层一致）；暴击/护盾/格挡/怒吼/裁决表现符合规格；法力每回合 +5、不足技能置灰、战后回满；击败怪物有掉落并进下一层；20 层 Boss 击败出「复苏之心」；死亡出失败结局可重开；断网仍可用。

- [ ] **步骤 5：Commit**

```bash
git add demo_word/game-ui.js demo_word/style.css
git commit -m "feat(dungeon): 战斗界面 + 日志 + buff + 胜负结局 + 重开"
```

---

## 任务 8：构建单文件 + README + 全流程离线验证

**文件：**
- 创建：`build.mjs`
- 创建：`README.md`
- 生成：`dist/index.html`

- [ ] **步骤 1：实现 `build.mjs`**

读 `index.html`，把 `<link rel="stylesheet" href="style.css">` 替换为内联 `<style>…style.css 内容…</style>`，把两个 `<script src=…>` 替换为内联 `<script>…对应文件内容…</script>`，输出到 `dist/index.html`。用 `node:fs` + `node:path`，无第三方依赖。

- [ ] **步骤 2：写 `README.md`**

内容：本地跑（浏览器打开 `index.html`）、跑测试（`node --test tests/`）、构建单文件（`node build.mjs`）、发给别人（发 `dist/index.html`，双击即玩、离线可用）。

- [ ] **步骤 3：构建并验证单文件**

运行：`node build.mjs`
预期：生成 `dist/index.html`；用浏览器打开 `dist/index.html`（断网），全流程可用。

- [ ] **步骤 4：全流程离线手测（硬性）**

运行：断网打开 `dist/index.html`（桌面 + 手机视口各一遍）。
逐层验证：选角 → 探索（判定正确）→ 互动 → 遇怪 → 战斗（普攻/技能/暴击/buff/法力/裁决）→ 掉落 → 逐层推进 → 20 层 Boss → 「复苏之心」胜利；另测死亡 → 失败结局 → 重开。
预期：全程无报错、数值正确、能玩到底。

- [ ] **步骤 5：跑全量单元测试**

运行：`node --test tests/`
预期：PASS（任务 1–4 全部用例）

- [ ] **步骤 6：Commit**

```bash
git add demo_word/build.mjs demo_word/README.md
git commit -m "feat(dungeon): 单文件构建 + README + 全流程离线验证"
```

---

## 自检记录

- **规格覆盖度**：§7.1 角色（任务 4 `CHARS`）；§7.2 战斗（任务 2）；§7.3 探索（任务 1 判定 + 任务 6 UI）；§7.4 怪物（任务 4 `MONSTERS`）；§7.5 奖励/装备（任务 3）；§7.6 互动（任务 6）；§7.7 层/流程（任务 4 + 任务 7）；§7.8 场景（任务 5，CSS+emoji 零外链）；§7.9 状态/UI（任务 5/6/7）；§7.10 HP 经济（任务 3）。§9 验证（任务 1–4 单元测试 + 任务 5–8 浏览器手测 + 任务 8 断网全流程）。无遗漏。
- **步骤扫描**：每步给了签名/确切取值/测试断言，无"待定/处理边界"式空行；函数体未抄（实现者按全局约束与签名写）。
- **类型一致性**：`state`（任务 4 `newGame`）与任务 2 `newBattle(playerState)`、任务 3 `applyStatReward/applyEquipment/healOnNewFloor` 的字段一致（`hp/maxHp/mana/maxMana/atk/def/intel/equipment/floor`）；`totalAtk`/`totalDef` 在任务 2/3 定义、任务 5 面板引用；`MONSTERS` 字段（`name/hp/maxHp/atk/def/skillDmg`）在任务 2 `newBattle` 与任务 4 一致。
- **审查重点**：6 条均已钉进对应任务测试（见上文各任务的测试断言）；离线可玩性由任务 5 无外链 + 任务 8 断网手测钉死。
- **比例**：计划以签名 + 测试断言 + 确切数据表为主，未抄函数体；数据表（技能/怪物/奖励范围）是规格定死的取值，保留是必要的。
