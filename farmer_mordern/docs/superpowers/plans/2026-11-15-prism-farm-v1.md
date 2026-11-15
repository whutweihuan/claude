# Prism Farm v1 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 subagent-driven-development（推荐）或 executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在 `farmer_mordern/` 从零实现 Prism Farm v1 —— 纯离线、可 `file://` 直开的 5 图农场放置游戏（种植→开垦→自动化→迁徙）。

**架构：** 系统层为纯函数（`src/game/systems/`，输入 `RunState + GameEvent + now`，不依赖 React），内容全部是数据文件（`src/game/content/`），Zustand+immer+persist 只做事件分发与状态承载，React/Tailwind/Framer Motion/Canvas 只做渲染。在线心跳与离线结算共用同一套结算函数，保证同时长同结果。

**技术栈：** Vite 5 + `vite-plugin-singlefile`、TypeScript 5 strict、React 18、Tailwind CSS v3、Zustand(+immer/persist)、break_infinity.js、Framer Motion、Howler.js、Canvas 2D、Vitest、ESLint+Prettier。

**规格：** `farmer_mordern/docs/superpowers/specs/2026-11-15-prism-farm-design.md`（§ 引用均指该文档；CLAUDE.md 技术红线视为公理）

## 全局约束

- TS `strict: true`，禁止 `any`（测试文件同样适用；未知 JSON 用 `unknown` + 校验收窄）。
- 所有金额（coins、价格、收益、累计）一律 `Decimal`（break_infinity.js）；`number` 只允许出现在时长(ms)、百分比系数、动画参数。存档中金额为十进制字符串。
- 零网络：产物不得含任何外部 URL/CDN；`vite.config` `base: './'` + singlefile 内联，保证 Chrome/Edge `file://` 双击可运行。
- 字体走 `@fontsource/inter`（npm 安装打进产物）；音频用 Howler 且**默认静音**；无 Redux/Pixi/Three/axios。
- 无失败状态：任何路径不得让 coins 变负、不得使作物/地块消失或衰减。
- 每个任务结束时 `npx vitest run` 全绿才可 commit；commit message 用中文 conventional 风格（`feat(...)`/`test(...)` 等）。
- 工程根目录 = `D:/000_study/020_code/claude/farmer_mordern/`，下文相对路径均基于此。

## 审查重点

规格隐含、但单任务测试未必天然覆盖的高危输入，实现对应任务时必须加测试钉住：

1. **存档解析失败 ≠ 损坏**：localStorage 有内容但 JSON.parse 抛错时，不得覆盖原档（进入只读模式）→ 任务 8 `parseSave` 用例 + 任务 9 写盘守卫。
2. **时钟回拨 / `now < plantedAt` 或 `lastSeenAt > now`**（改系统时间、跨时区）：进度钳制为 0..1，离线 elapsed ≤ 0 按 0 处理，绝不产生负收益、不崩溃 → 任务 4、7 用例。
3. **超长离线**（如 3650 天）：受离线上限钳制；无上限内容也不得死循环/Infinity/NaN → 任务 7 用例。
4. **导入非法文件**（非本项目 JSON、外站产物、version 高于当前）：明确拒绝并报原因，当前存档原样保留 → 任务 8、12 用例。
5. **自动补种遇到 coins < seedCost**：该图停摆于"已收未种"，不扣负、不跳过轮次；玩家补钱后恢复 → 任务 7 用例。

---

## 文件结构（决策已锁定）

```
farmer_mordern/
  index.html  package.json  tsconfig.json  vite.config.ts  tailwind.config.js
  postcss.config.js  eslint.config.js  .prettierrc  .gitignore
  tools/gen-sounds.mjs
  public/sounds/{harvest,buy,unlock,migrate}.wav      # 由 tools 生成后提交
  src/
    main.tsx  App.tsx  styles/index.css
    game/
      types.ts                  # 全部共享类型（单一事实来源）
      content/maps.ts crops.ts upgrades.ts index.ts
      systems/format.ts growth.ts engine.ts offline.ts save.ts migrate.ts
    store/gameStore.ts
    ui/
      HUD.tsx MapRail.tsx PlotGrid.tsx PlotCell.tsx PlantSprite.tsx
      ShopPanel.tsx PlotDetail.tsx OfflineReport.tsx SettingsPanel.tsx
      BackgroundCanvas.tsx floatText.ts sound.ts
  src/**: *.test.ts 与实现同目录共置
```

`types.ts` 关键形状（任务 1 建立骨架、任务 2 定型，之后任务只引用不擅改）：

```ts
import Decimal from 'break_infinity.js'
export type { Decimal }
export interface PlotState { id: string; unlocked: boolean; cropId: string | null
  presetCropId: string | null; plantedAt: number | null; growMs: number | null }
  // growMs = 种植时刻的有效生长时长快照（§6）；成熟 = plantedAt+growMs <= now
export interface MapState { unlocked: boolean }
export interface RunState { schemaVersion: number; coins: Decimal; totalEarned: Decimal
  plots: Record<string, PlotState>       // key 与 value.id 相同，plotId = `${mapId}:${n}` n 从 0
  maps: Record<string, MapState>
  cropsUnlocked: Record<string, boolean> // cropId -> 是否已解锁
  upgrades: Record<string, number>       // key = `${upgradeDefId}:${scope}` scope = mapId 或 'global'
  lastSeenAt: number; startedAt: number
  foreign: Record<string, unknown> }     // 前向兼容：加载时原样保留的未知字段，toSaveData 合回
export interface CropDef { id: string; mapId: string; name: string
  seedCost: string; yieldCoins: string; growTimeMs: number
  unlockCost: string | null              // null = 随进度自动可用(§4.2)
  sprite: { body: string; accent: string; leaf: string; form: 'stem'|'bush'|'flower'|'tree'|'vine'|'grain'|'fantasy' } }
export interface MapDef { id: string; order: number; name: string; hue: number // 主题色相 0-360
  plotCount: number; freePlots: number; plotBaseCost: string; plotCostGrowth: number
  migrationCost: string | null }         // 离开本图去下一图的迁徙费；最后一图为 null
export type UpgradeKind = 'soil'|'speed'|'autoHarvest'|'autoReplant'|'offlineLamp'
export interface UpgradeDef { id: UpgradeKind; name: string; kind: UpgradeKind
  maxLevel: number; baseCost: string; costGrowth: number
  scope: 'map'|'global'; effectPerLevel: number } // soil .25 / speed .1 / lamp: levels=[8h,24h,72h] 特判
export type GameEvent =
  | { t: 'plant'; plotId: string; cropId: string }
  | { t: 'harvest'; plotId: string }
  | { t: 'buyPlot'; plotId: string }
  | { t: 'unlockCrop'; cropId: string }
  | { t: 'buyUpgrade'; defId: UpgradeKind; scope: string }
  | { t: 'swapPreset'; plotId: string; cropId: string }   // 更换预设作物(§7.1)
  | { t: 'clearCrop'; plotId: string }                   // 清茬：铲除生长中作物，进度作废
  | { t: 'migrate'; mapId: string }                      // 支付迁徙费解锁下一图
export type RejectReason = 'noCoins'|'notSequenced'|'alreadyOwned'|'locked'|'prereq'|'invalid'|'maxLevel'
export interface ApplyResult { ok: boolean; reason?: RejectReason; state: RunState }
```

---

### 任务 1：工程脚手架（可跑的空壳游戏）

**创建：** `package.json` `tsconfig.json` `vite.config.ts` `tailwind.config.js` `postcss.config.js` `eslint.config.js` `.prettierrc` `.gitignore` `index.html` `src/main.tsx` `src/App.tsx` `src/styles/index.css` `src/game/systems/format.test.ts`（占位冒烟）`src/smoke.test.ts`

依赖清单钉死：`react react-dom zustand immer break_infinity.js framer-motion howler @fontsource/inter`；dev：`vite @vitejs/plugin-react typescript tailwindcss postcss autoprefixer vitest vite-plugin-singlefile eslint prettier @types/react @types/react-dom @types/howler`。版本取 npm 当前 stable。

- [ ] **步骤 1：** `npm create vite@latest . -- --template react-ts`（在 farmer_mordern 内，保留已有 CLAUDE.md/docs）+ 装上述依赖 + 配置：tsconfig `"strict": true, "noUncheckedIndexedAccess": true`；vite `base:'./'` + `vite-plugin-singlefile`（`inlinePattern` 默认即可，`build.assetsInlineLimit: 100_000_000`）；vitest 走 vite config `test:{environment:'node'}`；tailwind content 指 `index.html`/`src/**/*.{ts,tsx}`。
- [ ] **步骤 2：** package.json scripts：`dev/build`(`tsc -b && vite build`)/`preview/test`(`vitest run`)/`lint`/`format`。
- [ ] **步骤 3：** `src/smoke.test.ts`：`expect(new Decimal('1e21').mul(2).toString()).toBe('2e+21')` —— 证明 Decimal+vitest 管道通。
- [ ] **步骤 4：** App 渲染深色底 + "Prism Farm" 字样占位；`npm run build && npm run test && npm run lint` 三项全绿；`.gitignore` 含 `node_modules/ dist/`。
- [ ] **步骤 5：** commit `chore(farmer_mordern): Vite+React+TS+Tailwind 脚手架与离线打包`

### 任务 2：内容数据表 + 节奏断言（§4、§9）

**创建：** `src/game/types.ts`（上文形状）`src/game/content/maps.ts crops.ts upgrades.ts index.ts`，测试 `src/game/content/content.test.ts`

数据要点（命名可微调，数值按此骨架生成）：

- `maps.ts` 5 图：`garden`(12 块/赠 2/基准价 `25`/hue 95)、`greenhouse`(14/2/`2.5e5`/330)、`orchard`(16/3/`5e8`/35)、`lake`(18/3/`1e12`/195)、`aurora`(20/4/`5e15`/265)；`plotCostGrowth: 1.9` 全图；`migrationCost`：图1 `1e7`、图2 `1e10`、图3 `1e13`、图4 `1e16`、aurora `null`。
- `crops.ts` 每图 6~8 种，按公式生成：`growTimeMs(k) = base × ratio^k`，`yieldCoins(k) = yBase × 5^k`，`seedCost(k) ≈ yieldCoins(k) × 0.5`（k 为图内序号；首种 seedCost 用 `1`）。图参数：garden base `5e3`ms ratio `3`；greenhouse base `1.8e6`ms ratio `2.2`；orchard base `1.44e7`ms ratio `2`；lake base `8.64e7`ms ratio `1.9`；aurora base `4.32e8`ms ratio `1.8`。yBase：`12` / `3e5` / `8e8` / `1.5e12` / `8e15`。每图前 4 种 `unlockCost: null`，其余定价 ≈ 该种 `yieldCoins×8`。
- `upgrades.ts`：soil(max 50, baseCost `图基准×8`, ×1.6, +25%)；speed(max 10, baseCost 基准×15, ×1.8, +10%)；autoHarvest(max 1, 基准×60)；autoReplant(max 1, 基准×200)；offlineLamp(scope global, max 2, baseCost `5e6`, ×500)。`upgrades.ts` 里 `baseCost` 用函数 `(mapIndex:number)=>string` 或分图覆盖表实现均可——选后在 index.ts 收敛为 `upgradeCost(def, mapDef, level): Decimal` 单一入口。
- `index.ts`：`buildIndex(): ContentIndex { maps: MapDef[]; mapById; cropById; cropsByMap; upgradeById }`，并导出 `OFFLINE_CAPS_MS = [8,24,72].map(h=>h*3600e3)`、`upgradeKey(defId, scope)`、`plotKey(mapId, n)` 工具。

- [ ] **步骤 1：写失败测试 `content.test.ts`**（§9 节奏断言 + 审查重点前置）：遍历 `buildIndex()` 断言 —— 每作物 `yieldCoins > seedCost`；同图相邻作物 `yieldCoins` 比 ∈ [1.3, 8]（单轮净利恒正前提下单位时间收益不倒挂：`yield/growTime` 严格递增）；每图 6~8 种；`freePlots + (plotCount - freePlots) == plotCount`；地块第 n 价 < 该图前 n+2 种作物单轮总净利之和 ×50（防空窗卡死）；`migrationCost` 非图 5 恒存在且递增。
- [ ] **步骤 2：** `npx vitest run src/game/content` 预期 FAIL（文件不存在/断言不过）。
- [ ] **步骤 3：** 按上表实现 types+content 四文件，命名取 garden:白萝卜/小青菜/向日葵/番茄/辣椒/南瓜…aurora:星霜花/月见藤 等，`sprite` 配色按主题色相挑。
- [ ] **步骤 4：** 测试 PASS；`npm run build` 仍绿。
- [ ] **步骤 5：** commit `feat(farmer_mordern): 类型定义与 5 图内容数据表 + 节奏断言`

### 任务 3：format.ts（§8.3）

**创建：** `src/game/systems/format.ts` + `format.test.ts`（替换任务 1 占位）

签名：`formatCoins(d: Decimal): string`（`1.23K` 千分位阶梯 K,M,B,T,Qa,Qi,Sx,Sp,Oc,No,Dc；≥1e36 → `d.toString()` 科学计数；<1000 原样取整）；`formatDuration(ms: number): string`（`1小时23分`/`45秒`）；`formatPercent(x: number): string`。

- [ ] **步骤 1：失败测试**：`formatCoins(new Decimal(1234))==='1.23K'`；`formatCoins(new Decimal(999))==='999'`；`formatCoins(new Decimal('1e36'))==='1.00e+36'`；`formatDuration(3_600_000+5*60_000)==='1小时5分'`；`formatDuration(999)==='0秒'`。
- [ ] **步骤 2：** 运行确认 FAIL。
- [ ] **步骤 3：** 实现。
- [ ] **步骤 4：** 运行 PASS。
- [ ] **步骤 5：** commit `feat(farmer_mordern): 金额/时长格式化为 Decimal 阶梯`

### 任务 4：growth.ts —— 进度纯函数（§6、审查重点 2）

**创建：** `src/game/systems/growth.ts` + `growth.test.ts`

签名：`progressOf(plot: PlotState, now: number): number`（钳制 0..1；空地/未解锁 0）；`isMature(plot: PlotState, now: number): boolean`；`effectiveGrowMs(crop: CropDef, speedLevel: number): number = crop.growTimeMs / (1 + 0.1×min(level,10))`；`stageOf(progress: number): 0|1|2|3`（阈值 0.25/0.6/0.95）。

- [ ] **步骤 1：失败测试**：半程 `0.5`；`now >= plantedAt+growMs` → 1 且 mature；**`now < plantedAt`（时钟回拨）→ 0，不抛错**；`growMs` 快照意味着种植后再升 speed 级不影响本轮 `progressOf`（断言用旧 growMs 算）；stageOf 边界值。
- [ ] **步骤 2：** 确认 FAIL。
- [ ] **步骤 3：** 实现（纯函数，无 import Decimal 需要——进度是时间比值，number 合法）。
- [ ] **步骤 4：** 确认 PASS。
- [ ] **步骤 5：** commit `feat(farmer_mordern): 生长进度纯函数与墙钟快照语义`

### 任务 5：engine.ts 核心事件 —— 种/收/买地/解锁作物（§3、§4.5 记账）

**创建：** `src/game/systems/engine.ts` + `engine.test.ts`

本任务实现：`initialState(c: ContentIndex, now: number): RunState`（garden 图 unlocked、前 freePlots 块 unlocked、首图 `unlockCost===null` 作物置 true、coins `new Decimal(15)`、lastSeenAt/startedAt=now、foreign={}）；`applyEvent` 骨架 + 事件 `plant/harvest/buyPlot/unlockCrop/swapPreset/clearCrop`；`soilMult(s, c, mapId): number = 1 + 0.25×level`；`plotPrice(mapDef, n): Decimal = base × 1.9^n`。

规则（写进实现注释）：plant 扣 seedCost、写 cropId/presetCropId（首次）/plantedAt/growMs=effectiveGrowMs；harvest 仅成熟可收，`+yieldCoins×soilMult(结算时刻等级)`，收后 cropId 清空、**presetCropId 保留**；buyPlot 必须按 n 顺序（前一块已开垦）否则 `notSequenced`；unlockCrop 一次性扣费；swapPreset 只改 presetCropId 不打断当前轮；clearCrop 铲除生长中作物（不退款、扣费不重复）。全部拒绝路径返回 `{ok:false, reason}` 且 `state` 与传入**引用相等**（ Immer-free：内部 `structuredClone` 或手工浅拷贝+Decimal clone，实现自选，测试钉语义）。

- [ ] **步骤 1：失败测试**（每组都断言拒绝时 `result.state === inputState` 且 coins 不变——审查重点 5 的在线半区）：`plant` 成功扣款并设 growMs 快照；`plant` 余额不足 → `noCoins`；`harvest` 未熟 → `invalid`，成熟 → 入账 = yield×soilMult、地块转空且 preset 保留；`buyPlot` 跳号 → `notSequenced`，顺序购买扣款+解锁；`buyPlot` 越界 id → `invalid`；`unlockCrop` 重复 → `alreadyOwned`；`swapPreset` 后当前 cropId/plantedAt 不动；`clearCrop` 后 cropId=null 且不扣钱不退款；`totalEarned` 只随 harvest 增长。
- [ ] **步骤 2：** 确认 FAIL。
- [ ] **步骤 3：** 实现。
- [ ] **步骤 4：** 确认 PASS。
- [ ] **步骤 5：** commit `feat(farmer_mordern): 事件引擎——种植/收获/开垦/解锁/换种/清茬`

### 任务 6：engine.ts 升级与迁徙（§4.2、§4.3）

**修改：** `src/game/systems/engine.ts`（补 `buyUpgrade/migrate` 分支）、`engine.test.ts` 追加

- [ ] **步骤 1：失败测试**：`buyUpgrade('soil','garden')` 扣款升 1 级，二次购买价格 ×1.6；soil 生效后 garden 收获额 ×1.25（与任务 5 harvest 断言联动）；`speed` 达 maxLevel(10) 后再买 → `maxLevel`；`buyUpgrade('autoReplant','garden')` 未先买 autoHarvest → `prereq`；`offlineLamp` scope 恒为 `'global'`（传 mapId 也归一 global）；`migrate('greenhouse')`：garden 仍有锁定地块 → `notSequenced`；全开垦且钱够 → 扣 migrationCost、greenhouse 图与 freePlots、首 4 作物解锁、garden 状态原样保留；钱不够 → `noCoins`；重复 migrate 同图 → `alreadyOwned`；对 aurora 调 migrate → `invalid`。
- [ ] **步骤 2：** 确认 FAIL。
- [ ] **步骤 3：** 实现；导出 `canMigrate(s, c, mapId): {ok: boolean; missing: 'plots'|'coins'|'prereq'} `（UI 灰显与 tooltip 用）。
- [ ] **步骤 4：** 确认 PASS。
- [ ] **步骤 5：** commit `feat(farmer_mordern): 升级线与跨图迁徙`

### 任务 7：offline.ts + autoTick —— 三档自动化与在线/离线一致性（§4.5、审查重点 2/3/5）

**创建：** `src/game/systems/offline.ts` + `offline.test.ts`

签名：`offlineCapMs(s: RunState): number`（lamp 0/1/2 → 8/24/72h）；`settleOffline(s: RunState, c: ContentIndex, lastSeen: number, now: number): { state: RunState; report: OfflineReport }`；`autoTick(s: RunState, c: ContentIndex, now: number): RunState`；`interface OfflineReport { elapsedMs: number; gained: Decimal; perMap: Record<string, { cycles: number; gained: Decimal }> }`。

语义：`elapsed = clamp(now - lastSeen, 0, cap)`（负值→0：审查重点 2；3650 天被钳到 cap：审查重点 3）。对每个已解锁图逐块：手动档 → 只推进（到熟停）；自动收获 → 到熟收 1 次停"已收未种"；自动收获+补种 → 循环"收(±seedCost) 种"直到 elapsed 尽或 **coins < seedCost 即停**（审查重点 5）。在线档 `autoTick` 是同一规则的单心跳特化（每个成熟块最多推进一轮）。**一致性核心测试**：同种子状态、同 N 个心跳步进 vs 一次 settleOffline，coins/plots 完全相等（容差 0，Decimal 精确比较）。

- [ ] **步骤 1：失败测试**（各档 × 边界：elapsed=0、恰好 1 轮、N 轮+余数、超 cap、elapsed 负）：手动档成熟停、不自动收；收获档只收不种；补种档多轮后 `plantedAt = 结算窗口终点 - 余数进度` 语义（断言 progressOf 等于期望余数）；**买不起**用例：预置 coins < 下一轮 seedCost → 停在"已收未种"、coins ≥ 0、后续手动补钱再 settle 正常续轮；一致性用例（100 心跳 vs 一次离线，24h 窗口、混合三档地块）；`report.perMap` 分图轮数与 gained 合计 = coins 增量。
- [ ] **步骤 2：** 确认 FAIL。
- [ ] **步骤 3：** 实现（逐块解析闭式解，勿逐毫秒循环：`cycles = floor(remAfterMature / growMs)`，逐轮扣种钱时以 `while (i < cycles && coins.gte(cost))` 收敛，i 上限 = 该轮 cycles，杜绝无界循环）。
- [ ] **步骤 4：** 确认 PASS。
- [ ] **步骤 5：** commit `feat(farmer_mordern): 离线结算三档与在线/离线一致性`

### 任务 8：save.ts + migrate.ts —— 序列化、校验、迁移链、导入导出（§5）

**创建：** `src/game/systems/save.ts migrate.ts` + `save.test.ts migrate.test.ts`

签名：`toSaveData(s: RunState, now: number): SaveData`（金额→`toString()` 字符串；`foreign` 原样合回；结构镜像 RunState）；`type LoadOutcome = {kind:'empty'} | {kind:'ok'; state: RunState} | {kind:'unreadable'} | {kind:'invalid'; reason: string}`；`parseSave(raw: string | null, c: ContentIndex): LoadOutcome`；`migrateSave(raw: Record<string, unknown>): Record<string, unknown>`；`CURRENT_SCHEMA_VERSION = 1`；`MIGRATIONS: Record<number, (r: Record<string, unknown>) => Record<string, unknown>>`（v1 首发链为空，但管道完整）；`exportJson(s): string` / `importJson(text, c): LoadOutcome`（复用 parseSave）。

校验规则：schemaVersion 存在且 ≤ CURRENT（高于 → `invalid: '版本更新'`，审查重点 4）；金额字段必须 `new Decimal(str)` 不抛且 ≥0（负 → invalid）；未知 cropId/mapId/plotId：跳过该条进 `foreign`（不炸局）；JSON.parse 抛错 → `unreadable`（**调用方据此禁写盘**，审查重点 1）。

- [ ] **步骤 1：失败测试**：Round-trip：`parseSave(exportJson(initialState), idx)` 的 state 与原 state `toEqual`（Decimal 按 toString 比较）；金额在 JSON 文本里**是带引号字符串**（`/"coins":"15"/` 类断言，钉 number 红线）；`'1e21'` 科学计数往返精度不丢；坏 JSON → `unreadable`；`{schemaVersion: 99}` → `invalid`；含 `cropId:'future-crop'` 的地块 → ok 且进 foreign、往返后该字段仍在；负 coins → invalid；v0→v1 假迁移函数被 `migrateSave` 调用（用测试注册的临时链验证管道）。
- [ ] **步骤 2：** 确认 FAIL。
- [ ] **步骤 3：** 实现。
- [ ] **步骤 4：** 确认 PASS。
- [ ] **步骤 5：** commit `feat(farmer_mordern): 存档序列化/校验/迁移链与导入导出函数`

### 任务 9：gameStore.ts —— Zustand 接线、心跳、写盘守卫（§5、§6、全局约束之"不每心跳写盘"）

**创建：** `src/store/gameStore.ts` + `gameStore.test.ts`；修改 `src/App.tsx` 临时挂 debug 文本

接口：`useGame = create<Store>()(persist(immer(...)))`，state：`game: RunState; ui: { report: OfflineReport|null; loadError: string|null; nowTick: number; muted: boolean }`；actions：`dispatch(ev: GameEvent)`（调 applyEvent，ok=false 静默拒绝并可读 reason）、`tick(now: number)`（心跳：nowTick 更新→autoTick→lastSeenAt=now）、`receiveReport/dismissReport`、`newGame()`、`hardResetAndReload()`；导出 `startHeartbeat(): () => void`（100ms `setInterval`，测试可注入假 now）。持久化：`partialize` 排除 `ui`；**`loadError !== null` 时 storage 写入函数直接 return（只读模式）**；`throttle: 1000` 写盘。启动流程 `bootstrapGame()`：parseSave(localStorage) → `empty`→initialState+settleOffline(0)；`ok`→settleOffline(state, lastSeenAt, now) 并挂 report；`unreadable/invalid`→进入新局但 `loadError` 置位且**本次会话禁写**（unreadable 场景连开新局都不许覆盖原档：state 用新局内存态，storage 写被守卫拦）。

- [ ] **步骤 1：失败测试**（用内存 Map 假 localStorage 注入）：启动→空档→initialState 且写盘发生一次；预置合法档→启动后 report 非空、coins 含离线收益、再次启动不重复计（lastSeenAt 已刷新）；预置坏 JSON→`ui.loadError` 非空、`useGame.getState().dispatch(plant)` 生效于内存但 storage 原文未被覆盖；muted 默认 `true`；throttle：连续 12 次 `tick` 写盘 ≤2 次（计数假 storage）。
- [ ] **步骤 2：** 确认 FAIL。
- [ ] **步骤 3：** 实现。
- [ ] **步骤 4：** 确认 PASS。
- [ ] **步骤 5：** commit `feat(farmer_mordern): zustand 全局 store、心跳与只读守卫`

### 任务 10：PlantSprite + PlotCell/PlotGrid —— 地图主视图（§7.2）

**创建：** `src/ui/PlantSprite.tsx PlotCell.tsx PlotGrid.tsx`

`PlantSprite({ crop: CropDef; stage: 0|1|2|3; mature: boolean })`：按 `sprite.form` × `stage` 组合 SVG 图元（茎/叶/花/果/藤/穗 6~7 个 path 构件，配色取 sprite.body/accent/leaf），stage<3 时缩放/构件渐显，mature 附 `animate-breathe`（CSS keyframe `scaleY(1±0.02)`）。PlotCell：未开垦→虚位+价格；空→"+"；生长→Sprite+进度环；成熟→辉光+可点。点击语义接线 `dispatch`（空→选中态交由任务 11 的 PlotDetail；成熟→harvest）。PlotGrid：按 MapDef 网格布局（2 行自适应列），含 HUD 所需 `onPlotSelect`。本任务无强制单测（纯渲染），验收 = `npm run build` 绿 + dev 手测截图。

- [ ] **步骤 1：** 实现 Sprite（先 3 个 form 跑通，其余同构补齐——form 全集见任务 2 数据）。
- [ ] **步骤 2：** 实现 Cell/Grid 并接 store（garden 可玩：种、收、买地）。
- [ ] **步骤 3：** `npm run build && npm run lint` 绿；`npm run dev` 手动走一遍 garden 循环。
- [ ] **步骤 4：** commit `feat(farmer_mordern): 参数化作物 SVG 与地块网格视图`

### 任务 11：HUD + MapRail + ShopPanel + PlotDetail —— 交互闭环（§7.1）

**创建：** `src/ui/HUD.tsx MapRail.tsx ShopPanel.tsx PlotDetail.tsx CropPicker.tsx floatText.ts`

HUD：coins（`formatCoins` + Framer Motion 数字滚动，共享元素 `layoutId="coins"`）、每秒产出（当前各图 autoTick 均值估算，简单实现：`totalEarned` 差分的 10s 滑窗）、设置入口。MapRail：5 图图标（锁灰显 + `canMigrate` 原因 tooltip）。ShopPanel：作物解锁/四升级线/迁徙按钮（不足灰显价格红字）。PlotDetail + CropPicker：空地→选种（显示回本周期 `seedCost/(yield−seed)×growTime` 折算）；生长中→"更换预设作物 / 清茬改种"两键（§7.1 语义）；收获飘字 `+N`（`floatText.ts` 命令式挂 DOM，勿进 React 树重渲染风暴）。

- [ ] **步骤 1：** 实现四组件 + 接线全部 GameEvent（游戏从 UI 完整可玩至 aurora）。
- [ ] **步骤 2：** build/lint 绿；dev 手测：手动循环→买自动化→观察地块自转→换预设作物→清茬→迁徙。
- [ ] **步骤 3：** commit `feat(farmer_mordern): HUD/地图栏/商店/地块详情——全交互闭环`

### 任务 12：OfflineReport + SettingsPanel —— 报告仪式感与存档进出口（§4.5、§5）

**创建：** `src/ui/OfflineReport.tsx SettingsPanel.tsx`；测试 `src/ui/io.test.ts`（纯逻辑：文件名生成/下载 blob 组装可测部分）

OfflineReport：加载结算完成自动弹（`ui.report` 非 null），展示离开时长/分图轮数/总收益（纯展示已入账，§4.5），数字滚动，点任意处 dismiss。SettingsPanel：导出（Blob+a[download] `prism-farm-save-YYYY-MM-DD.json`）、导入（file input → `importJson` → 失败展示 reason 且**不落盘不覆盖**，成功则整店替换）、静音开关、音量滑杆、长按 3s 重置（进度环视觉，`hardResetAndReload`）。`loadError` 非空时顶部常驻红条："存档无法读取，本次不会覆盖 —— 可导出文本自救"（附导出原始 localStorage 按钮）。

- [ ] **步骤 1：** 实现两面板 + 接线。
- [ ] **步骤 2：** 手测：改系统时间/编辑 localStorage 模拟离线 10h→报告数字与 §4.5 表一致；导出→清档→导入→状态还原；塞坏 JSON→只读模式→刷新原档仍在。
- [ ] **步骤 3：** commit `feat(farmer_mordern): 离线报告与设置面板（导入导出/只读模式提示）`

### 任务 13：BackgroundCanvas + 动效抛光（§7.2）

**创建：** `src/ui/BackgroundCanvas.tsx`；修改 `styles/index.css` 及各组件

Canvas 粒子：30~60 个光点，主题色 = 当前图 hue，缓慢上浮+闪烁，`requestAnimationFrame`，tab 隐藏自动暂停（`visibilitychange`），**组件内零金额/逻辑**。抛光：收获缩放弹跳、购买面板微沉、迁徙全屏扫光一次、未解锁按钮统一微动效。性能底线：粒子层 `pointer-events:none` + 独立 canvas，不引发网格 re-render。

- [ ] **步骤 1：** 实现粒子层与动效。
- [ ] **步骤 2：** build/lint 绿 + dev 手测 60s 无明显掉帧、切图 hue 跟随。
- [ ] **步骤 3：** commit `feat(farmer_mordern): 环境粒子层与收获/购买动效`

### 任务 14：音效自合成 + Howler 接线（§7.3）

**创建：** `tools/gen-sounds.mjs public/sounds/*.wav src/ui/sound.ts`

`gen-sounds.mjs`：Node 原生写 44.1kHz 16bit 单声道 WAV（无依赖，头+PCM 正弦/三角合成）：harvest(上滑叮 0.18s)、buy(闷嗒 0.12s)、unlock(双音 0.3s)、migrate(上行琶音 0.8s)。脚本运行一次生成，wav 提交进仓库。`sound.ts`：Howler（`html5: true`）封装 `playSound(name)`，读 store `muted`（默认 true → 一律不发声）与音量。

- [ ] **步骤 1：** `node tools/gen-sounds.mjs` 生成 4 wav；`file --mime-type` 或播放自检合法。
- [ ] **步骤 2：** sound.ts + 在 harvest/buy/unlock/migrate 成功路径调用。
- [ ] **步骤 3：** 手测：默认静音无请求；开启后各动作有声、音量滑杆生效。
- [ ] **步骤 4：** commit `feat(farmer_mordern): 自合成 wav 音效与 Howler 静音开关`

### 任务 15：终验收 —— file:// 冒烟与全量绿（§10、建造者裁定）

- [ ] **步骤 1：** `npm run lint && npm run test && npm run build` 全绿；vitest 报告任务 2~9 用例总数记录进 commit 信息。
- [ ] **步骤 2：** `grep -RnE "(src|href)=\"https?://|@import url|fonts.googleapis" dist/` 零命中；dist 仅 1 个 index.html（+vite 允许的资源内联形态），字体/音频为 data URI 或同目录相对路径。
- [ ] **步骤 3：** Windows Chrome **双击 `dist/index.html`**：新局可玩（种收买迁）、F12 Network 面板零外部请求；刷新后存档保留；控制台零报错。Edge 复测一遍。
- [ ] **步骤 4：** 快进实测：临时 localStorage 注入中后期档（脚本改 coins/plots），验证自动化自转、离线报告、迁徙到账目正确。
- [ ] **步骤 5：** commit `chore(farmer_mordern): v1 终验收——file:// 离线冒烟通过`；若有修复另起 commit。

---

## 自检记录

- 规格覆盖度：§3 循环→任务5/10/11；§4.1/4.2→任务2/6；§4.3→任务6；§4.4→任务2 断言；§4.5→任务7；§5→任务8/9/12；§6→任务4/9；§7.1/7.2→任务10/11/13；§7.3→任务1/14；§8→任务2/5/9 文件结构；§9 全项→任务2/3/4/5/6/7/8；§10→任务1/15；§11 建造者裁定（singlefile、赠地、写盘节流、沃土结算时点）→任务1/2/9/5。无遗漏。
- 类型一致性：`RunState/PlotState/GameEvent/ApplyResult/OfflineReport/LoadOutcome` 自任务 2 定型，后续任务只引用；`upgradeKey/plotKey/buildIndex/canMigrate/offlineCapMs/effectiveGrowMs` 命名全文一致。
- 审查重点 1~5 已分别钉入任务 8/9、4/7、7、8/12、5/7。
