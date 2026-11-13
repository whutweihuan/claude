# warrior_web P0 机制审计 + M1 最小战斗 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 subagent-driven-development（推荐）或 executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 产出铁甲战士 72 卡的机制审计（原语词汇表 primitive-spec），并搭建网页工程实现"引擎骨架 + 15 张代表卡 + 2 种怪 + React 战斗屏 + Playwright 截图验收"的最小可玩战斗。

**架构：** 四层（设计文档 §5.1）：`src/engine` 纯逻辑状态机（公开动作返回 `GameEvent[]`，零 DOM）、`src/data` wiki 抓取规范化数据 + zod 校验、`src/ui` React 只消费 snapshot 并派发 action、`src/sim` 自动出牌器。随机数全程注入（mulberry32，种子可复现）。

**技术栈：** Node ≥ 20、Vite 5、TypeScript(strict)、React 18、zod 3、Vitest 2、@playwright/test 1.x

**规格：** `warrior_web/docs/superpowers/specs/2026-11-13-warrior-web-design.md`（范围已裁定 = A：仅铁甲战士；本计划覆盖其 P0 与 M1，M2+ 另立计划）

## 全局约束

- 只在 `warrior_web/` 内创建/修改文件；commit 前缀 `feat(warrior_web):`/`test(warrior_web):`/`docs(warrior_web):`，末尾加 `Co-Authored-By: Claude Code <noreply@anthropic.com>`。
- 开工第一步在仓库建分支 `feat/warrior-web-p0-m1`（当前在 main，不允许直接提交 main）。
- engine 层禁止 import 任何 DOM/React 模块；vitest 跑 engine 测试不得需要浏览器。
- 随机性只允许来自注入的 `Rng`（`createRng(seed)`），engine 代码内禁止 `Math.random`。
- 卡牌数值唯一真源 = `data/cards.json`（任务 2 抓取产物）。本计划测试里写的数值是抓取前的占位断言示例；实现到该任务时若与 cards.json 不符，**以 cards.json 为准并同步修订测试与 card-mapping.md**（wiki API 需自定义 User-Agent：`warrior-research/1.0`，裸 UA 返回 403）。
- 基线 = 杀戮尖塔 1（非 StS2）；卡名用中文社区惯用译名，效果描述用自己的话写简描，不复制官方风味文本。
- `.gitignore` 至少含：`node_modules/`、`dist/`、`test-results/`、`playwright-report/`、`data/raw/`（原始抓取件不入库，规范化后的 `data/cards.json` 入库）。

## 文件结构

```
warrior_web/
  package.json tsconfig.json vite.config.ts playwright.config.ts .gitignore
  scripts/fetch-cards.mjs          # wiki API 批量抓取 → data/raw/ → data/cards.json
  scripts/check-mapping.mjs        # card-mapping.md × cards.json 覆盖率/词汇闭合校验
  data/cards.json                  # 72 铁甲卡+升级形态+相关无色/诅咒/状态牌（P0/M3 共用底座）
  docs/audit/primitive-spec.md     # 原语词汇表（最终版 = M2 施工图）+ 词汇数量与预算结论
  docs/audit/card-mapping.md       # 每卡一行：card id → 原语序列（含升级行）+ 残差处置表
  src/engine/rng.ts                # createRng/mulberry32
  src/engine/types.ts              # GameEvent、CardDef/CardInstance、EnemyDef、CombatSnapshot、Rng
  src/engine/effects.ts            # applyEffect 解释器（M1 词汇子集，未知原语 throw）
  src/engine/enemies.ts            # EnemyInstance、意图生成 _genIntents/formatIntent
  src/engine/combat.ts             # Combat 类：回合循环、出牌、胜负、snapshot
  src/data/schema.ts               # zod contentSchema（cards.json 的形状 + M1 子集过滤）
  src/data/load.ts                 # loadContent(path?) → Content {cards, enemies}
  src/sim/autoplay.ts              # autoplayerCombat(combat, rng, maxTurns) 随机合法动作自动打完
  src/ui/main.tsx src/ui/App.tsx   # 挂载 + 开发用"新战斗(种子)"面板
  src/ui/CombatScreen.tsx          # 纯展示组件：props = {snapshot, onPlayCard(i,t?), onEndTurn()}
  src/ui/components/…              # CardView/HeroView/EnemyView/EventLog/ErrorBoundary + styles.css
  tests/engine/*.test.ts           # vitest 单测（rng/回合/伤害/出牌/意图/边缘原语）
  tests/data/cards.test.ts         # cards.json schema 与条数校验
  e2e/combat.spec.ts               # Playwright：出牌交互、日志、高 DPI 截图与溢出断言
```

## 接口契约（跨任务共享，命名以本节为准）

```ts
// engine/rng.ts
interface Rng { nextInt(maxExclusive: number): number; shuffle<T>(a: T[]): T[]; chance(p: number): boolean }
function createRng(seed: number): Rng

// engine/types.ts（联合类型成员按任务递增，成员名冻结）
type EffectRow = readonly [string, ...(string | number)[]]
interface CardDef { id: string; nameEn: string; nameZh: string; cost: number
  type: 'attack' | 'skill' | 'power'; rarity: 'starter' | 'common' | 'uncommon' | 'rare' | 'curse' | 'status'
  keywords: string[]; textZh: string; effects: EffectRow[]
  upgrade: { effects: EffectRow[]; cost?: number; textZh: string } | null }
interface CardInstance { uid: number; id: string; upgraded: boolean; costMod: number }
interface EnemyDef { id: string; nameEn: string; nameZh: string; hp: [number, number]
  moves: MoveDef[] }
interface MoveDef { id: string; nameZh: string; kind: 'attack' | 'defend' | 'buff' | 'heal' | 'incantation'
  damage?: number; hits?: number; block?: number; strength?: number; vulnerable?: number
  healAtHalfHp?: number; weight: number }
type GameEvent = { type: 'turn_start' | 'turn_end'; turn: number }
  | { type: 'draw'; count: number } | { type: 'shuffle' }
  | { type: 'card_played'; cardUid: number; cardId: string; energySpent: number }
  | { type: 'damage'; side: 'hero' | 'enemy'; targetIdx: number; amount: number; absorbed: number }
  | { type: 'block_gain'; side: 'hero' | 'enemy'; targetIdx: number; amount: number }
  | { type: 'hp_lost'; cause: 'effect' | 'poison'; amount: number }
  | { type: 'status'; target: 'hero' | 'enemy'; targetIdx: number; status: 'vulnerable' | 'strength'; amount: number }
  | { type: 'card_added'; where: 'discard'; cardId: string; upgraded: boolean }
  | { type: 'invalid'; reason: string }
  | { type: 'combat_end'; result: 'win' | 'lose' }
interface CombatSnapshot { hp: number; maxHp: number; block: number; energy: number; turn: number
  status: 'playing' | 'win' | 'lose'; hand: (CardInstance & { nameZh: string; cost: number
  playable: boolean; keywords: string[]; textZh: string })[]
  enemies: { nameZh: string; hp: number; maxHp: number; block: number; intent: string | null
  vulnerable: number; alive: boolean }[]
  drawCount: number; discardCount: number; exhaustCount: number }
interface Content { cards: Record<string, CardDef>; enemies: Record<string, EnemyDef> }

// engine/combat.ts
class Combat {
  constructor(opts: { content: Content; hero: { hp: number; maxHp: number; deck: CardInstance[] };
    enemyIds: string[]; rng: Rng })
  start(): GameEvent[]
  playCard(handIndex: number, targetIdx?: number): GameEvent[]
  endTurn(): GameEvent[]
  get status(): 'playing' | 'win' | 'lose'
  snapshot(): CombatSnapshot
}
// src/data/schema.ts： contentSchema: ZodSchema<Content>；loadContent(jsonPath?: string): Content（默认读 ../../data/cards.json，只放行本计划 M1 用到的卡与怪，任务 2 的 cards.json 先全量入文件、M1 引擎按需取子集）
// src/sim/autoplay.ts： function autoplayerCombat(combat: Combat, rng: Rng, maxTurns?: number): { result: 'win' | 'lose' | 'timeout'; turns: number; events: GameEvent[] }
// src/ui/CombatScreen.tsx： export function CombatScreen(props: { snapshot: CombatSnapshot; log: string[]; onPlayCard: (i: number, t?: number) => void; onEndTurn: () => void }): JSX.Element
```

## 审查重点（规格隐含、无显式任务声明覆盖的失败模式 → 钉住它的测试所在任务）

1. **抽穿牌堆**：牌库抽空时把弃牌堆洗回继续抽，事件含 `shuffle`，不崩不误抽（任务 4 测试 2）。
2. **能量不足仍点击**：`playCard` 返回 `invalid` 事件且零副作用（能量不变、手牌不动），UI 按钮同步禁用（任务 4 测试 3 + 任务 7 e2e）。
3. **多段攻击中途死亡**：Twin Strike 第 1 击打死敌人后第 2 击跳过，伤害不溢出到其他敌人（任务 4 测试 5）。
4. **高 DPI 中文裁切**（warrior 的核心教训）：deviceScaleFactor=2 下卡名、敌人名 DOM 不溢出容器（scrollWidth ≤ clientWidth）、截图人工抽查（任务 7 e2e）。
5. **引擎异常白屏**：`playCard` 抛错时 ErrorBoundary 渲染可见错误面板而非白屏（任务 7 e2e）。

---

### 任务 1：工程脚手架

**文件：** 创建 `package.json`、`tsconfig.json`、`vite.config.ts`、`playwright.config.ts`、`.gitignore`、`index.html`、`src/ui/main.tsx`、`src/ui/App.tsx`（占位标题页）、`tests/smoke.test.ts`、`e2e/smoke.spec.ts`、`README.md`（启动三步曲）

- [ ] 步骤 0：`git -C <仓库根> checkout -b feat/warrior-web-p0-m1`；在 `warrior_web/` 建 `.gitignore`（见全局约束）
- [ ] 步骤 1：`npm init -y` 后改写 package.json：scripts `dev`/`build`/`preview`/`test`(vitest run)/`e2e`(playwright test)；dependencies 装 `react react-dom zod`，devDependencies 装 `typescript vite @vitejs/plugin-react vitest @types/react @types/react-dom @playwright/test`（各取当前 stable major，记入 README"版本基线"小节）
- [ ] 步骤 2：`npx playwright install chromium`（验证 CDN 可达；失败即停，回报设计文档 §8 网络假设不成立）
- [ ] 步骤 3：写 `tests/smoke.test.ts`（`expect(1+1).toBe(2)`）→ `npm test` 绿
- [ ] 步骤 4：写 `e2e/smoke.spec.ts`：`webServer` 起 `vite preview`（playwright.config 里 `reuseExistingServer: !process.env.CI`），page.goto('/') 断言 `document.title === 'warrior_web'` 并 `expect(page).toHaveScreenshot()` 生成基线截图 → `npm run e2e` 绿
- [ ] 步骤 5：commit `chore(warrior_web): 工程脚手架与双测试环`

### 任务 2：wiki 数据抓取 → cards.json（P0 输入）

**文件：** 创建 `scripts/fetch-cards.mjs`、`data/cards.json`（产物）；测试 `tests/data/cards.test.ts`

- [ ] 步骤 1：先写失败测试 `tests/data/cards.test.ts`：
```ts
test('铁甲常规卡恰为 72 张', () => { expect(content.cards 中 type!=='status'/'curse' 且颜色为红的卡数).toBe(72) })
test('每张卡通过 contentSchema 且含升级差异或 upgrade:null', ...)
test('状态/诅咒牌带 unplayable 或对应关键词', ...)   // Burn、Ascender's Bane 等在池内
```
- [ ] 步骤 2：`npm test` → 红（cards.json 不存在）
- [ ] 步骤 3：实现 `scripts/fetch-cards.mjs`：
  - 铁甲卡名清单：解析 wiki `Ironclad` 页 `{{QueryLink|Cards|color:Red…}}` 分池不可得，改用 `categorymembers` 遍历 `Category:Cards` 后逐页取 infobox 的 Color=Red 过滤（或已知 72 名单硬编码兜底，二选一，代码注释写明依据）。
  - MediaWiki API `action=query&prop=revisions&rvprop=content&titles=…` 每批 50 个 title，带 UA `warrior-research/1.0`；原始 wikitext 存 `data/raw/`（gitignore）；解析 `{{Card Infobox}}` 的 Name/Cost/Type/Rarity/Effects/Upgraded Effects 与关键词行；追加抓取相关无色/诅咒/状态卡（至少：Burn、Wound、Dazed、Empty、Clumsy、Ascender's Bane、Regret、Moment of Silence）。
  - 中文 `nameZh`/`textZh` 简描：脚本产出英文名与原文后，由执行者按社区惯用译名补 zh 字段（逐卡核对效果数值与原文一致）；每条含 `source: {page, fetchedAt}` 字段，`verified: true` 仅当 wiki 解析成功。
  - `data/cards.json` 顶层含 `meta.startingDeck`（从 wiki `Ironclad` 页 `Starting Deck` 节解析：如 `[[strike×5, defend×4, bash×1]]`，以抓取实际输出为准），UI 组装英雄初始卡组（任务 7）与 autoplayer（任务 4）从这里取数，禁止散落硬编码。
- [ ] 步骤 4：`node scripts/fetch-cards.mjs` → `npm test` 绿（vitest 用 zod `contentSchema.partial` 之外的严格版解析 data 文件）
- [ ] 步骤 5：commit `feat(warrior_web): wiki 抓取与铁甲全卡数据底座`

### 任务 3：primitive-spec 词汇表 + 全卡映射审计（P0 本体）

**文件：** 创建 `docs/audit/primitive-spec.md`、`docs/audit/card-mapping.md`、`scripts/check-mapping.mjs`；测试 `tests/audit/mapping.test.ts`

- [ ] 步骤 1：先写失败测试（跑 check-mapping 的逻辑，vitest 直接 import）：
```ts
test('cards.json 每张卡（含升级行）在 card-mapping 恰有一行映射', ...)
test('映射引用的每个原语都在词汇表中声明（词汇闭合）', ...)
test('词汇表中每个原语至少被一张卡使用，或显式标注 reserved(理由)', ...)
test('残差表每行有处置字段（新增原语/裁定特例/待M2）', ...)
```
- [ ] 步骤 2：`npm test` → 红
- [ ] 步骤 3：起草 `primitive-spec.md`：初始词汇 = warrior 18 原语（从 `warrior/core.py apply_effect` 抄录）+ 按 72 卡实际语义增补（预计新增 25~40 个：`damage_equal_block`、`add_card_copy`、`end_turn`、`heal_hp_loss`、X 费用表示法、`apply_per_turn` 型 power、combo 关键词钩子…）。逐卡填写 `card-mapping.md`（72 基础 + 72 升级 + 状态诅咒 ≈ 150 行；效果原文 → 原语序列，`|` 分隔；目标语义列 single/all/random/x）。表达不出的卡进残差表，逐个裁定。
- [ ] 步骤 4：`npm test` → 绿（映射覆盖率 100%）
- [ ] 步骤 5：在 `primitive-spec.md` 末尾写**预算锁定节**：最终原语数、关键词数、钩子清单、遗物触发点数（顺带把 `Category:Relics` 铁甲相关遗物做一次同法粗映射，遗物名+触发+数值一段表，供 M4），以及"按设计文档 §7 口径重算的 M2/M3 预算区间"；同步修订设计文档 §7 的数字
- [ ] 步骤 6：commit `docs(warrior_web): P0 机制审计——原语词汇表与全卡映射`

### 任务 4：引擎骨架——rng、回合循环、基础原语

**文件：** 创建 `src/engine/rng.ts`、`src/engine/types.ts`、`src/engine/effects.ts`、`src/engine/combat.ts`、`src/data/schema.ts`、`src/data/load.ts`、`src/sim/autoplay.ts`；测试 `tests/engine/rng.test.ts`、`tests/engine/turn-loop.test.ts`

- [ ] 步骤 1：写失败测试 rng（同种子序列一致、`shuffle` 可复现）
- [ ] 步骤 2：写失败测试回合循环与伤害（数值从 cards.json 读取，以下断言形状为准）：
```ts
test('test1 同种子两实例逐事件相等')
test('test2 抽穿牌堆洗回并出 shuffle 事件')            // 审查重点 1
test('test3 能量不足 playCard 返回 invalid 零副作用')    // 审查重点 2
test('test4 Strike 消耗1能量→damage事件→进弃牌堆')
test('test5 Twin Strike 第1击致死则第2击跳过且无溢出伤害') // 审查重点 3
test('test6 回合开始格挡清零、Defend 的 block 事件生效')
test('test7 全敌死亡 status=win 并发 combat_end；英雄 hp≤0 status=lose')
test('test8 未知原语 applyEffect throw（词汇外调用即炸）')
```
- [ ] 步骤 3：实现 types.ts（接口契约原样）、rng.ts、effects.ts（M1 子集：`damage(block-aware)/block/draw/energy/hp_cost/exhaust 标记`；伤害管线顺序钉死：**基础值→力量→本回合首击加成→易伤×1.5→格挡吸收**，与 warrior `hit_enemy` 一致）、combat.ts（牌堆三区、`playCard` 校验→扣能→逐效果执行→目标死则中断、`endTurn` 弃手牌→敌行动→下回合、`snapshot`）。`playCard` 非法索引/越界 target 一律 `invalid` 事件不抛错
- [ ] 步骤 4：`npm test` 绿；`src/sim/autoplay.ts`：随机合法动作循环到终局（maxTurns=80 超时保护）
- [ ] 步骤 5：commit `feat(warrior_web): 战斗引擎骨架与回合循环`

### 任务 5：意图系统与 M1 敌人

**文件：** 创建 `src/engine/enemies.ts`、`data/cards.json` 内 enemies 节（修改任务 2 抓取脚本一并产出）；测试 `tests/engine/intent.test.ts`、`tests/engine/enemies.test.ts`

- [ ] 步骤 1：写失败测试：
```ts
test('敌人意图在玩家行动前生成且整回合不重掷（Cultist 攻击值含已有力量）')
test('Cultist 首回合布道，之后每次攻击力量+2 且意图数字随之显示')
test('Jaw Worm 生命低于一半时一次性回血 12 并跳过该次行动意图')  // wiki 实际行为为准，若为"回血后仍攻击"按 cards.json 修测试
test('意图被易伤时显示的伤害×1.5 与结算一致')
test('autoplayer 以 seed 0..49 对 [cultist]/[jaw_worm]/[cultist,jaw_worm] 打 150 场全部终局无异常（≤80回合）')
```
- [ ] 步骤 2：红 → 步骤 3：实现 `EnemyInstance`（`pendingMove` 锁定、hp 区间按 tier 掷值、`incantation` 型力量、半血阈值 heal）、`genIntents/formatIntent`（中文短语"攻击 8×1 / 格挡 5"，多段显示 `d×h`）。敌普攻走同一伤害管线（英雄格挡吸收）
- [ ] 步骤 4：`npm test` 绿 → 步骤 5：commit `feat(warrior_web): 敌人意图与 M1 遭遇`

### 任务 6：M1 边缘原语（X 费/连击/复制/转目标伤害/群体）

**文件：** 修改 `src/engine/effects.ts`、`src/engine/types.ts`（联合成员 `combo_pending`、`heal`）、`src/engine/combat.ts`；测试 `tests/engine/edge-primitives.test.ts`

- [ ] 步骤 1：写失败测试（每例一张 cards.json 真卡驱动）：
```ts
test('Offering：hp_cost 6→energy+2→draw3→立即 end_turn 结算敌方行动')
test('Bloodletting：损失3HP 得2能量')
test('Double Tap：其后第一张攻击本回合打两遍（第二遍吃 Double Tap 后新挂的易伤状态）')
test('Anger：伤害后弃牌堆多一张未强化副本（uid 不同）')
test('Body Slam：伤害值等于当前格挡，ignore 力量后仍=block？——按 cards.json/wiki 原文钉死（力量是否加算）')
test('Cleave：对全部存活敌人各打 5，含已死跳过')
test('Shrug It Off：block+draw 顺序与事件流一致')
test('X 费卡 energy=0 时 cost 显示 0 且 playable=true')
```
- [ ] 步骤 2：红 → 步骤 3：实现原语 `heal? 不需要——M1 用 hp_cost/energy/draw/end_turn/add_card_copy/damage_equal_block/damage_all`；combo 实现为 `pendingDoubleAttack` 标志，`playCard` 检测到 attack 卡时整段效果再执行一遍（事件流带 `from_combo: true`）；`_card_cost` 支持 `'x'` 成本
- [ ] 步骤 4：绿 → 步骤 5：把 15 张 M1 卡接入 `loadContent` 白名单，`npm test` 全绿 → 步骤 6：commit `feat(warrior_web): M1 边缘机制原语`

### 任务 7：React 战斗屏 + Playwright 验收（M1 研究命题的验证点）

**文件：** 创建 `src/ui/App.tsx`（替换占位）、`src/ui/CombatScreen.tsx`、`src/ui/components/{CardView,HeroView,EnemyView,EventLog,ErrorBoundary}.tsx`、`src/ui/styles.css`；测试 `e2e/combat.spec.ts`

- [ ] 步骤 1：写失败的 e2e：
```ts
test('首屏渲染 10 张起始卡组抽到的 5 张手牌与 2 敌意图；点 Strike→选敌→敌人 hp 条与日志更新、能量-1', { dsf: 2 })
test('能量不足时其余卡按钮 disabled 且点击无日志变化')          // 审查重点 2
test('deviceScaleFactor=2 下所有卡名/敌名 scrollWidth<=clientWidth，页面 document.scrollWidth<=clientWidth') // 审查重点 4
test('强制注入抛错（?fault=1 查询参数使 playCard 抛）→ 渲染错误面板而非白屏')  // 审查重点 5
test('打完一场胜利后显示结算条（重开按钮出现）')
```
- [ ] 步骤 2：红 → 步骤 3：实现 UI。约束：CardView 用自然宽度 + flex wrap（warrior DPI 教训：中文标签禁止固定字符宽）；手牌卡面 = 名称/费用圆标/简描 tooltip；点击目标流程 = 选卡→敌区点击；App 用 `useReducer` 包 Combat 实例（`ref` 持有，snapshot 进 state），日志 = 事件流→中文行；`?seed=`/`?fault=` 参数从 URL 读（e2e 用）
- [ ] 步骤 4：`npm run e2e` 绿 + `toHaveScreenshot` 基线截图归档复核（肉眼过一遍，截图存 `docs/audit/m1-screens/`）→ 步骤 5：commit `feat(warrior_web): 战斗屏与 e2e 验收`

### 任务 8：M1 验收关与合入准备

**文件：** 修改 `README.md`；创建 `docs/audit/m1-acceptance.md`

- [ ] 步骤 1：全量验证三连并记录输出：`npm test`、`npm run e2e`、`node --experimental-strip-types src/sim/cli.ts --games 500 --seed-base 1`（新建 `src/sim/cli.ts`：autoplayer 批跑 M1 三遭遇×500 场，胜率/平均回合/异常计数打印；预期异常 0、终局率 100%）
- [ ] 步骤 2：对照设计文档 §6-M1 验收项 + 本计划"审查重点"5 条逐项打勾写入 `m1-acceptance.md`，缺项补测
- [ ] 步骤 3：commit `test(warrior_web): M1 验收关与整局模拟`
- [ ] 步骤 4：向用户汇报 M1 结果与 primitive-spec 最终词汇数，确认 M2 预算后另立计划（writing-plans 产出计划 2）

---

## 自检记录（计划完成后按 writing-plans 自检五项执行；此项在保存后由作者勾）

- [ ] 规格覆盖度：设计 §6-M1 全部要素（事件流/卡实例/10~15 卡/2 怪/回合循环/截图验收）↔ 任务 4-7；§5.4-P0 ↔ 任务 2-3；§5.4 预算锁定 ↔ 任务 3 步骤 5
- [ ] 步骤扫描：无"待定/适当处理"占位；数值断言标注了 cards.json 真源规则
- [ ] 类型一致性：跨任务命名以"接口契约"节为准（`playCard/endTurn/snapshot/autoplayerCombat/contentSchema/createRng/CardDef/EffectRow/GameEvent`）
- [ ] 审查重点 5 条均已挂测试（1→T4、2→T4+T7、3→T4、4→T7、5→T7）
- [ ] 比例：测试给名字+断言形状，函数体只给签名与钉死的管线顺序
