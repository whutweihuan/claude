# 勇士冒险（终端 Roguelike 卡牌游戏）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 subagent-driven-development（推荐）或 executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在 `warrior/` 实现一个纯文字终端的杀戮尖塔式 roguelike：分支地图、回合制出牌战斗、火堆/事件/商店/宝箱、武器/防具/遗物成长（无等级系统），顶层击败魔王通关，单局十几分钟。

**架构：** 五文件分层——`content.py` 纯数据表（卡池/装备/遗物/敌人/事件），`core.py` 无 IO 的确定性逻辑（战斗状态机 + 效果原语解释器 + 地图生成 + 一局编排 + 商店），`ui.py` 终端渲染与输入循环（IO 可注入以便脚本化测试），`records.py` 战绩原子读写，`main.py` 装配。所有随机走注入的 `random.Random(seed)`，同种子可复现整局。

**技术栈：** Python 3.8.3（本机实测版本），仅标准库（dataclasses、unittest、random、json、os、time），无第三方依赖。

**规格：** `warrior/docs/superpowers/specs/2026-11-13-warrior-roguelike-design.md`（执行者先读规格再读本计划）

## 全局约束

- Python 3.8 兼容：不用 3.9+ 语法（`dict | None` 注解、`list[str]` 运行时注解需 `from __future__ import annotations` 或省注解）；只用标准库。
- `core.py`/`content.py`/`records.py` 内不得出现 `print(`、`input(`；全部 IO 只在 `ui.py` 与 `main.py`。
- 全部随机性经由注入的 `random.Random` 实例；逻辑不读系统时间（records 时间戳除外）。
- 锚定数值（规格逐字）：HP 上限 80；能量 3；每回合抽 5；打击 1 费 6 伤、防御 1 费 5 格挡、初始卡组 6 打击 4 防御；易伤 ×1.5 且每次受攻击触发 -1 层；火堆睡觉回上限 30%；精英固定 2、火堆保底第 4/7/10 层、商店 ≥1、前两层无精英、入口层全战斗；魔王血量过半进二阶段（每回合力量 +2）。
- 界面文案全中文；战斗屏 ≤50 行。
- 测试命令一律在 `warrior/` 目录运行：`python -m unittest <模块> -v`。
- 每个任务以 commit 结束，消息格式 `feat(warrior): …` / `test(warrior): …`，只提交 warrior/ 下文件。
- 事件/卡牌效果只能使用附录 C 的封闭原语集合（content 载入时用 `validate_content()` 校验）。

## 审查重点（Review Focus）

- **抽牌堆耗尽时的续抽**：一回合连续"战吼"把抽牌堆抽空后应立刻把弃牌堆洗回继续抽、不足则如实少抽，绝不报错或凭空发牌——任务 3 `test_draw_reshuffles_discard` 钉住。
- **每个菜单的垃圾输入**：空行、乱码、超范围编号、EOF 都必须重打菜单提示或体面退出，不能 traceback——任务 11 `test_invalid_inputs_reprompt`、`test_eof_exits_gracefully` 钉住。
- **战绩文件损坏/被占用**：损坏 JSON 改名 `records.corrupt-*.json` 后从空记录继续；PermissionError 不得覆盖原文件、不得崩溃——任务 10 全部测试钉住。
- **过杀与目标消失**：多段攻击中途敌人已死、群体招式的目标全灭、处决已死目标——伤害作废、不越界索引、不抛异常——任务 4 `test_overkill_and_dead_target` 钉住。
- **边界资源状态**：满血睡觉、药水 3/3 时获得、无牌可锻造、商店货架全部售罄后购物——各自给出明确提示而非异常——任务 7 `test_campfire_edges`、任务 8 `test_shop_edges` 钉住。

---

## 文件结构与测试归属

| 文件 | 职责 | 由哪些任务构建 | 测试写进 |
|---|---|---|---|
| `warrior/content.py` | 数据表 + 原语封闭集 + `validate_content()` | 1、2 | `test_core.py` |
| `warrior/core.py` | Hero/Combat/效果解释器/钩子/地图/Run/商店 | 3~9 | `test_core.py`（战斗/地图）、`test_run.py`（编排/事件/UI 冒烟） |
| `warrior/records.py` | 战绩原子读写三路径 | 10 | `test_records.py` |
| `warrior/ui.py` | 终端渲染 + 输入循环（IO 注入） | 11 | `test_run.py` |
| `warrior/main.py` | 装配、种子、records 更新 | 12 | `test_run.py` |

## 任务

### 任务 1：内容数据模型与卡牌/装备/药水表

**文件：**
- 创建：`warrior/content.py`、`warrior/test_core.py`

**接口：**

```python
@dataclass
class Card:      # id, name, cost:int, kind('attack'|'skill'|'power'),
                 # text:str, effects:list[tuple], upgrade:Optional[dict]  # upgrade={'text','effects'} 覆盖
@dataclass
class Gear:      # id, name, kind('weapon'|'armor'), attack_bonus:int, text, mods:dict
@dataclass
class Potion:    # id, name, text, effects:list[tuple], targeted:bool

CARDS: dict; WEAPONS: dict; ARMORS: dict; POTIONS: dict
BASICS = ('strike', 'defend')
STARTER_DECK  # 6×('strike',False) + 4×('defend',False)
CARD_RARITY: dict  # id -> 'basic'|'common'|'uncommon'|'rare'
PRIMITIVES: frozenset          # 战斗效果原语名，见附录 C
def validate_content() -> None  # 抛 ValueError 表示表违规
```

- [ ] **步骤 1：编写失败的测试**（`test_core.py`，类 `ContentTableTests`）

```python
def test_anchor_card_values(self):
    s, d = content.CARDS['strike'], content.CARDS['defend']
    self.assertEqual((s.cost, s.effects), (1, [('damage', 6)]))
    self.assertEqual((d.cost, d.effects), (1, [('block', 5)]))
    self.assertEqual(s.upgrade['effects'], [('damage', 9)])
    self.assertEqual(content.STARTER_DECK, [('strike', False)] * 6 + [('defend', False)] * 4)

def test_pool_sizes_and_uniqueness(self):
    self.assertGreaterEqual(len(content.CARDS), 28)   # 含 2 基础
    self.assertGreaterEqual(len(content.WEAPONS), 6)
    self.assertGreaterEqual(len(content.ARMORS), 5)
    self.assertGreaterEqual(len(content.POTIONS), 5)
    self.assertEqual(len(set(list(content.CARDS) + list(content.WEAPONS) + list(content.ARMORS) + list(content.POTIONS))),
                     len(content.CARDS) + len(content.WEAPONS) + len(content.ARMORS) + len(content.POTIONS))

def test_all_effects_use_closed_primitives(self):
    content.validate_content()   # 内部断言：cost∈0..3、kind 合法、effects 全在 PRIMITIVES、非基础牌必有 upgrade、rarity 全覆盖
```

- [ ] **步骤 2：运行验证失败**：`python -m unittest test_core.ContentTableTests -v` → ModuleNotFoundError/FAIL
- [ ] **步骤 3：按附录 A/B 誊写数据表**（`content.py`），实现 `validate_content()`（用 PRIMITIVES 校验每条 effects，校验 CARD_RARITY 覆盖 CARDS 全部 id、武器名/防具名互不重复）。
- [ ] **步骤 4：运行验证通过**：同上 → PASS
- [ ] **步骤 5：Commit**：`git add warrior/content.py warrior/test_core.py && git commit -m "feat(warrior): 卡牌/装备/药水数据表"`

### 任务 2：敌人、遭遇与事件表

**文件：**
- 修改：`warrior/content.py`；修改：`warrior/test_core.py`

**接口：**

```python
@dataclass
class Move:   # name, kind('attack'|'block'|'buff'|'debuff'|'poison'), weight:int,
              # damage:int=0, hits:int=1, block:int=0, strength:int=0, vulnerable:int=0, poison:int=0
@dataclass
class Enemy:  # id, name, hp:int, moves:list[Move], is_elite:bool=False, is_boss:bool=False,
              # cycle:bool=False（固定循环出招）, phase2_at_half:bool=False, phase2_per_turn_strength:int=0
ENEMIES: dict            # 附录 D；含 7 普通 + 2 精英 + 魔王
ELITE_IDS, BOSS_ID
ENCOUNTERS: list[tuple]  # (layer_min:int, layer_max:int, [(enemy_id, weight), ...], max_count:int)
@dataclass
class EventOption:  # label, outcome:list[tuple]  # 原语见附录 C 的 EVENT_PRIMITIVES
@dataclass
class GameEvent:    # id, title, text, options:list[EventOption]  # 2~3 选项
EVENTS: dict        # 附录 E，≥8 个
def validate_content() -> None  # 追加敌人/事件校验
```

- [ ] **步骤 1：编写失败的测试**（`ContentTableTests` 追加）

```python
def test_enemy_tables(self):
    self.assertGreaterEqual(len(content.ENEMIES), 10)
    for e in content.ENEMIES.values():
        self.assertGreaterEqual(len(e.moves), 2)
        self.assertTrue(all(m.kind in ('attack', 'block', 'buff', 'debuff', 'poison') for m in e.moves))
    boss = content.ENEMIES[content.BOSS_ID]
    self.assertTrue(boss.is_boss and boss.phase2_at_half and boss.hp >= 140)
    self.assertGreaterEqual(len(content.ELITE_IDS), 2)

def test_events(self):
    self.assertGreaterEqual(len(content.EVENTS), 8)
    for ev in content.EVENTS.values():
        self.assertTrue(2 <= len(ev.options) <= 3)
    content.validate_content()  # 校验事件 outcome 全在 EVENT_PRIMITIVES、引用 id 存在

def test_encounters_cover_layers(self):
    for layer in range(1, 12):
        self.assertTrue(any(a <= layer <= b for a, b, _, _ in content.ENCOUNTERS), layer)
```

- [ ] **步骤 2：运行验证失败**（FAIL）
- [ ] **步骤 3：誊写附录 D/E 表并入 `validate_content()`**
- [ ] **步骤 4：运行验证通过**（`test_core.ContentTableTests` 全 PASS）
- [ ] **步骤 5：Commit**：`git commit -am "feat(warrior): 敌人/遭遇/事件数据表"`

### 任务 3：战斗引擎·玩家侧

**文件：**
- 创建：`warrior/core.py`；修改：`warrior/test_core.py`

**接口：**

```python
@dataclass
class Hero:   # max_hp=80, hp, gold=0, deck=list[(card_id,upgraded)], weapon='rusty',
              # armor=None, relics=[], potions=[]
class Combat:
    def __init__(self, hero: Hero, enemy_ids: list, rng: random.Random, tier: int = 1): ...
    # tier 影响敌方 hp ×(1.0/1.3/1.6)、伤害 +0/+1/+2；构造期生成敌人实例，不改动 hero
    hand, draw_pile, discard_pile, energy, block, enemies, log, status('playing'|'win'|'lose')
    def start(self) -> list          # 起手（抽 5），返回日志行
    def play_card(self, i: int, target: int = None) -> list   # 返回日志行；非法（费不足/越界/已结束）只回错误行且状态不变
    def end_turn(self) -> list       # 弃手牌→敌人回合→玩家新回合（见任务 4）
    def snapshot(self) -> dict       # 供 UI：hp/block/energy/手牌(含可打出标记)/敌人(意图)/牌堆计数
    def effects_for(self, card_id, upgraded) -> list          # 解释前查 upgrade 覆盖
```

效果解释器 `apply_effect(hero, combat, eff, target)` 按附录 C 原语实现：`damage`（含武器加成、自身力量、目标易伤 ×1.5 并 -1 层）、`damage_all`、`block`、`draw`（抽牌堆空洗弃牌堆）、`energy`、`hp_cost`、`heal`（≤max_hp）、`self_strength`、`vulnerable(target)`、`poison(target)`、`bonus_if_vulnerable`、`execute`（目标 hp 比例阈值）、`pierce`（无视格挡）、`exhaust`（本战移出）、`power`（本战持续词条）。

- [ ] **步骤 1：编写失败的测试**（类 `CombatPlayerTests`；用单只假敌人，如 `[('goblin',...)]` 或最小 stub enemy dict）

```python
def test_opening_hand_and_energy(self):        # 锚定：start 后 len(hand)==5, energy==3
def test_strike_and_defend_values(self):       # 打出 strike→敌 hp -6；defend→block==5；能量各 -1
def test_cannot_play_without_energy(self):      # 能量 0 时 play_card 返回含"能量"的错误行，手牌/敌人状态不变
def test_hand_discarded_at_end_of_turn(self):   # end_turn 前 block==X>0：新回合 block 归 0，原手牌在弃牌堆
def test_draw_reshuffles_discard(self):         # 10 张组抽空抽牌堆后，弃牌堆洗回继续抽（审查重点 1）
def test_weapon_bonus_applies_per_hit(self):    # 双段卡 + 武器加成 +1：两段各 +1（规格 6.4 多段每段加成）
def test_strength_and_vulnerable_math(self):    # 力量+1→strike 7；目标易伤→strike int(6*1.5)=9 且易伤层数 -1
def test_power_card_persists(self):             # 打出 fury(狂怒)后本战每回合首次攻击 +3
```

- [ ] **步骤 2：运行验证失败**（FAIL）
- [ ] **步骤 3：实现 Hero、Combat 玩家侧 + 解释器**（敌人侧先留最小占位：`end_turn` 里敌人不行动、仅回合推进与抽牌；任务 4 补全）
- [ ] **步骤 4：运行验证通过**（PASS）
- [ ] **步骤 5：Commit**：`git commit -am "feat(warrior): 战斗引擎玩家侧"`

### 任务 4：战斗引擎·敌人侧（意图、回合、胜负）

**文件：**
- 修改：`warrior/core.py`、`warrior/test_core.py`

- [ ] **步骤 1：编写失败的测试**（类 `CombatEnemyTests`）

```python
def test_intent_visible_before_acting(self):
    # start 后每个敌人 snapshot 里有 intent 文本（如"意图：攻击 5"）；同种子重跑意图序列一致
def test_enemy_attack_hits_block_first(self):  # block=3 敌攻 5 → hp-2、block 清零
def test_multi_hit_attack(self):               # 狼 attack 3×2 → hp-6
def test_dead_enemy_removed_no_index_error(self):
    # 三段攻击 killing 第 1 只后，其余段继续打剩余目标；全灭后 play_card 越界目标返回错误行（审查重点 4）
def test_win_and_lose_status(self):            # 全灭→status=='win'；hero.hp<=0→status=='lose'
def test_elite_cycle_moves_learnable(self):    # cycle=True 敌人按招式顺序循环、意图提前显示下招
def test_boss_phase_switch(self):
    # boss hp 过半后每回合 strength+2，招式换入 phase2 池（规格 6.10）
def test_enemy_debuffs_on_hero(self):          # 敌人 vulnerable 词条→英雄打出攻击牌 ×1.5
```

- [ ] **步骤 2：运行验证失败**
- [ ] **步骤 3：实现敌人实例（hp 按 tier 缩放）、`_pick_move`（cycle 顺序 / weight 随机经由注入 rng）、意图预生成、`_enemy_turn`（attack 逐段结算、block、buff strength、debuff vulnerable、poison）、胜负判定接入 play_card/end_turn**
- [ ] **步骤 4：运行验证通过**
- [ ] **步骤 5：Commit**：`git commit -am "feat(warrior): 敌人意图与回合结算"`

### 任务 5：武器/防具/遗物钩子接入

**文件：**
- 修改：`warrior/core.py`、`warrior/test_core.py`

**接口（钩子点，规格 9 节要求"新增内容不改动流程代码"）：** `combat_start`、`turn_start`、`turn_end`、`attack_damage_base`（武器 attack_bonus 与 torch/whetstone 类词条）、`cost_adjust`、`gold_mult`、`shop_discount`、`death_save`（血之圣瓶）。`Combat.__init__/_apply_*` 遍历 `hero.relics`（RELICS hooks）与 `WEAPONS/ARMORS mods` 派发到钩子点。

- [ ] **步骤 1：编写失败的测试**（类 `HookTests`；规格 10.1 要求附录 B 全部 19 件遗物每件至少一条触发断言，下列为代表，其余用参数化/子测试补齐）

```python
def test_rusty_sword_zero(self):               # 初始锈剑：strike 仍 6
def test_weapons_modify_rules(self):           # axe(+4, first_card_extra_cost)：首张牌 2 费、非首张 1 费；
                                               # flame(+2, turn_start_self_damage 2)；twinblades(-1 且 draw+1→首回合手牌 6、strike 5)
def test_armor_start_block(self):              # leather 开局 block5；plate block9 且每回合能量 2；spiked 被击后攻者受 3
def test_relic_combat_triggers(self):          # coffee 首回合能量 4；horn 首回合抽 7；ember 战后 heal 4（经 core.settle 层调用）；
                                               # tooth：hp=20(<30%) 时开战力量+2、hp=80 时无
def test_gold_mult_and_shop_discount(self):    # purse：settle_combat 金币 ×1.25 取整；hag_hat：报价 80%
def test_death_save_once(self):                # 圣瓶：致死一击后 hp=ceil(80*0.3)=24、遗物移除、status 仍 playing；第二场不再有
def test_lucky_dice_four_choices(self):        # 奖励展示 4 张而非 3 张
```

- [ ] **步骤 2：运行验证失败**
- [ ] **步骤 3：实现钩子派发**（数据表在 RELICS/WEAPONS/ARMORS 的 hooks/mods 字段，已按附录 A/B 就位；本任务只写 core 侧派发与 settle_combat 结算函数 `settle_combat(hero, combat, rng, layer) -> {'gold':int,'relic_drop':Optional[str],'card_choices':list[(card_id,upgraded)]}`：普通战金币 12~18+tier×4（purse 前）、15% 掉遗物（common 池）、卡选择 3（有 lucky_dice 则 4），rarity 权重早期 common8/uncommon3/rare1、层≥7 改 5/4/2）
- [ ] **步骤 4：运行验证通过**
- [ ] **步骤 5：Commit**：`git commit -am "feat(warrior): 装备与遗物钩子"`

### 任务 6：地图生成

**文件：**
- 修改：`warrior/core.py`、`warrior/test_core.py`

**接口：**

```python
@dataclass
class MapNode:  # id:int, layer:int, kind('combat'|'elite'|'campfire'|'event'|'shop'|'chest'|'boss'), next:list[int]
class GameMap:  # nodes:dict[int, MapNode], entry_ids:list[int], boss_id:int
def generate_map(rng) -> GameMap
# 结构：10 个常规层（每层 1~3 节点）+ boss 层单节点；总节点 15~20（含 boss）；
# layer1 全 combat 且 2 个；elite 固定落第 6、9 层各 1（该层随机一节点改 elite）；
# 第 4、7、10 层各保底 1 火堆；第 8 层保底 1 火堆；商店≥1（第 2~8 层随机节点）；事件≥2；
# 其余节点在 combat/event/chest 加权随机；连线保证：每节点≥1 出边、非入口层每节点≥1 入边、
# 任意节点到 boss 均有路径、每层每节点可达。
def layer_tier(layer) -> int  # ≤4→1, ≤8→2, ≥9→3
```

- [ ] **步骤 1：编写失败的测试**（类 `MapGenTests`）

```python
def test_invariants_over_1000_maps(self):
    for s in range(1000):
        m = generate_map(random.Random(s))
        kinds = [n.kind for n in m.nodes.values()]
        assert 15 <= len(kinds) <= 20
        assert kinds.count('elite') == 2 and kinds.count('boss') == 1
        assert kinds.count('campfire') >= 3 and kinds.count('shop') >= 1 and kinds.count('event') >= 2
        assert all(m.nodes[i].kind == 'combat' for i in m.entry_ids) and len(m.entry_ids) == 2
        assert no elite in layers 1..2（逐条 assert，非循环吞断言）
def test_every_node_reachable_and_progresses(self):
    # BFS：入口→所有节点可达；每个非 boss 节点存在至少一条到 boss 的通路；每层节点 next 全在下一层
def test_same_seed_same_map(self):
    # 同 rng 种子两次 generate_map 结构逐字段相等（含节点 kind 序列）
```

- [ ] **步骤 2：运行验证失败**
- [ ] **步骤 3：实现 generate_map**（先按保底规则布 elite/火堆/商店，再填其余，最后连边并做可达性修复：孤立节点补边；保底火堆与 elite 同层冲突时 elite 优先、火堆挪该层另一节点）
- [ ] **步骤 4：运行验证通过**（1000 图断言全绿；若某保底规则在个别层数下无法满足，微调该层节点数分布并在测试里同步——这是规格 11 节授权的分布决定）
- [ ] **步骤 5：Commit**：`git commit -am "feat(warrior): 分支地图生成与保底规则"`

### 任务 7：一局编排 Run（节点结算、火堆、宝箱、奖励、死亡）

**文件：**
- 修改：`warrior/core.py`、`创建/追加`：`warrior/test_run.py`

**接口：**

```python
class Run:
    def __init__(self, seed: int): ...   # 内部 random.Random(seed)、Hero 初始配置、generate_map、visited、seen_events
    def choices(self) -> list[int]        # 当前位置可达且未访问的节点 id
    def go(self, node_id) -> None
    def enter(self) -> tuple              # ('combat'|'elite'|'boss', Combat) | ('campfire', None) | ('event', GameEvent)
                                          # | ('shop', None) | ('chest', loot) | ('win', stats) | ('dead', stats)
    def campfire_options(self) -> list    # [{'kind':'sleep'...}, {'kind':'forge','cards':[...可锻造]}, {'kind':'sharpen'}]（sleep 满血时 available=False）
    def campfire(self, kind, card_slot=None) -> list[str]
    def take_card(self, i), def skip_card(self)   # 战斗奖励协议；collect 完才允许离开节点
    def combat_finished(self) -> None     # 调 settle_combat、累计 records 用击杀数、boss→'win'、hp<=0→'dead'
    finished: bool; outcome: 'win'|'dead'|None
```

- [ ] **步骤 1：编写失败的测试**（`test_run.py::RunFlowTests`）

```python
def test_full_flow_to_boss(self):
    # 固定种子：按 choices 里第一个可行节点走到底（跳过战斗用注入"必赢"：把 Combat 置 status='win' 或直调 combat_finished），
    # 断言依次经过 combat→campfire→…→enter()==('boss',...)，层号单调 +1，choices 只给未访问的下一层
def test_campfire_forge_upgrades_card(self):  # forge 一张 strike→hero.deck 出现 ('strike',True)；sharpen→weapon 的 attack_bonus+1 且上限 +3（每局限 3 次）
def test_chest_gives_gear_or_relic(self):     # 宝箱 loot 结构 {kind, id}，武器/防具替换旧件、金币入账
def test_campfire_edges(self):
    # 满血 sleep：available False 且调用返回提示行不崩溃；无 upgrade 空间时 forge 列表仍返回（审查重点 5）
def test_death_ends_run(self):                # 把 hero.hp 打 0 → enter/combat_finished 后 outcome=='dead'、finished True
def test_seed_reproducibility(self):
    # 同种子两次 Run：map 相等、同一决策序列下奖励内容（card_choices、chest loot）逐字段相等（规格 8 节）
def test_events_no_repeat_in_run(self):       # 连续经过 event 节点 ≥3 次，事件 id 不重复
```

- [ ] **步骤 2：运行验证失败**
- [ ] **步骤 3：实现 Run 与节点结算**（奖励暂存 `pending`，取完才能 `advance`；'win' 统计 stats：{'depth','kills','gold_earned','turns_total'}）
- [ ] **步骤 4：运行验证通过**
- [ ] **步骤 5：Commit**：`git commit -am "feat(warrior): 一局编排与火堆/宝箱结算"`

### 任务 8：商店与药水

**文件：**
- 修改：`warrior/core.py`、`warrior/test_run.py`

**接口：** `make_shop(rng, hero, layer) -> Shop`；`Shop.slots: list[Slot(kind,content_id,base_price,price,sold)]`；`Shop.remove_cost:int`；`buy(run, slot_idx) -> list[str]`；`remove_card_service(run, deck_index)`；`Combat.use_potion(slot, target=None)`；`run.use_potion_outside(slot)`。

货架（规格 6.9）：2 牌 + 1 武器 + 1 防具 + 1 遗物 + 2 药水；定价按附录 B；钱包类 `shop_discount` 生效并显示 base/现价。删牌服务常驻。药水携带 ≤3，超出时获得渠道给"背包已满"提示并保留原物（丢弃需显式选择——首版直接不获得并提示，这是计划决定，写进测试）。

- [ ] **步骤 1：编写失败的测试**（`test_run.py::ShopTests`）

```python
def test_shop_inventory_shape_and_price(self):
    # 固定种子：slots 类型计数 {card:2, weapon:1, armor:1, relic:1, potion:2}；hag_hat 时 price==int(base*0.8)
def test_buy_and_spend_rules(self):           # 金币不足返回提示行不入账；买武器替换 hero.weapon（旧件消失）；sold 后不能再买
def test_remove_card_service(self):           # 删牌后 deck 少一张且金币扣 65
def test_shop_edges(self):                     # 全部 sold 后再次 buy 返回"已售罄"；gold=0 买任何东西只回提示（审查重点 5）
def test_potion_in_and_out_of_combat(self):
    # p_blood：hp 30→44；p_energy：本回合能量+2；use_potion 槽位消耗；局外 heal 类可用、攻击类只能在战斗中（目标存在性）
def test_potion_cap_three(self):              # 满 3 时 gain_potion 返回提示、列表长度仍 3、物品未丢
```

- [ ] **步骤 2：运行验证失败**
- [ ] **步骤 3：实现商店与药水路径**（事件里的药水/金币原语复用同一 gain 函数，保证 3 瓶上限一致）
- [ ] **步骤 4：运行验证通过**
- [ ] **步骤 5：Commit**：`git commit -am "feat(warrior): 商店与药水"`

### 任务 9：事件结算

**文件：**
- 修改：`warrior/core.py`、`warrior/test_run.py`

**接口：** `apply_event(run, event, option_idx) -> (lines, follow)`；follow 为 `None` 或 `('combat', enemy_ids)`（事件引战：战斗胜利才离开节点，奖励照 settle_combat）。outcome 原语执行器：`hp`、`heal`、`gold`、`gain_potion_random`、`gain_relic_random(rarity)`、`gain_gear_random(kind,tier)`、`add_card_random(rarity)`、`upgrade_random_card`、`remove_random_card`、`start_combat(ids)`、`branch([(weight, outcomes), ...])`（注入 rng）。

- [ ] **步骤 1：编写失败的测试**（`test_run.py::EventTests`）

```python
def test_every_event_option_runs(self):
    # 双循环遍历 content.EVENTS × options：每个都在新建 Run 上执行不抛异常，且 lines 非空
def test_branch_deterministic_with_seed(self):
    # 赌博地精同种子两次结果一致（赢/输分支固定），不同种子至少一次两种结果都出现过（扫 20 种子）
def test_followup_combat_blocks_leave(self):  # 引战事件后 combat_finished 前 run 不能进下一节点
def test_altar_sacrifice_boundaries(self):    # 献 HP 选项：hp 低于代价时该选项 available=False 或提示失败（不出现负 hp）
```

- [ ] **步骤 2：运行验证失败**
- [ ] **步骤 3：实现原语执行器与 apply_event**
- [ ] **步骤 4：运行验证通过**
- [ ] **步骤 5：Commit**：`git commit -am "feat(warrior): 随机事件结算"`

### 任务 10：records.py 战绩存档

**文件：**
- 创建：`warrior/records.py`、`warrior/test_records.py`

**接口：**

```python
DEFAULT_PATH = 'records.json'  # main 里用程序目录绝对路径
SCHEMA = {'runs':0,'wins':0,'deaths':0,'best_layer':0,'total_kills':0,'last_seed':None,'history':[]}  # history 最近 10 局 {'date','outcome','depth','seed'}
def load_records(path) -> (dict, str)   # status ∈ 'ok'|'missing'|'corrupt'|'io_error'；corrupt 时原文件改名 records.corrupt-<YYYYmmdd-HHMMSS>.json
def save_records(path, records) -> str  # 'ok'|'io_error'；临时文件 records.json.tmp + os.replace；PermissionError 返回 'io_error' 且原文件不动
def update_records(records, outcome_stats) -> dict  # 纯函数：累计 + history append/截断
```

- [ ] **步骤 1：编写失败的测试**（`test_records.py`，用 tempfile 目录；审查重点 3 全在此）

```python
def test_missing_file_returns_defaults(self)
def test_roundtrip_ok(self)
def test_corrupt_json_renamed_and_defaults(self)   # 写 "{not json" → status 'corrupt'、records 为默认、目录存在 records.corrupt-*.json、原损坏内容在其中
def test_permission_error_does_not_overwrite(self)  # mock os.replace 抛 PermissionError → status 'io_error'，原文件字节不变
def test_history_capped_at_10_and_counters(self)    # update_records 12 次 → len(history)==10、wins/deaths/best_layer 正确
```

- [ ] **步骤 2：运行验证失败**
- [ ] **步骤 3：实现三路径读写与原子替换**（沿用仓库 farmer/milkCow 已验证做法：`open(path,'w')` tmp → flush → `os.replace`；仅 `json.JSONDecodeError` 视为损坏；`OSError` 一律 io_error 不改名不覆盖）
- [ ] **步骤 4：运行验证通过**
- [ ] **步骤 5：Commit**：`git commit -am "feat(warrior): 战绩存档原子读写与损坏隔离"`

### 任务 11：终端 UI

**文件：**
- 创建：`warrior/ui.py`、追加 `warrior/test_run.py`

**接口：**

```python
class UI:
    def __init__(self, run, write=None, read=None, clear=None)
    # write(str)->None、read()->str（默认 print / input；clear 默认 os.system('cls')，注入替身跳过）
    def play(self) -> dict
    # 流程：地图屏(ASCII 分层图+图例+状态栏，编号选下一节点) → 按 enter() 分屏处理
    # 战斗屏 ≤50 行：顶栏(HP/格挡/能量/金币)、敌人区(名/HP/意图)、手牌区(编号/费/效果)、日志尾 4 行
    # 战斗命令：数字=出牌(多目标时再输目标编号)，d=结束回合，p=药水(补槽位/目标)，i=详情，其余任意输入=重打菜单
    # 地图命令：编号=移动，s=查看遗物/牌堆，q=放弃本局(确认)
    # EOFError 在任何 read() 处 → 视为放弃本局，回到战绩屏，不 traceback
```

- [ ] **步骤 1：编写失败的测试**（`test_run.py::UITests`：`UI(read=脚本迭代器, write=列表收集器, clear=lambda:None)` 驱动固定种子 Run）

```python
def test_combat_screen_budget(self):
    # 3 敌+满手牌时，一屏渲染行数 <= 50
def test_scripted_win(self):
    # 脚本输入 ["1","d",...] 打完一场 goblin 战并进入奖励选择"跳过"，断言 run 离开节点且日志含"胜利"
def test_invalid_inputs_reprompt(self):
    # 战斗输入喂 ["zzz","", "99", "d"] → 前三次各打印一行含"请重新"的提示且回合数只 +1（审查重点 2）
def test_eof_exits_gracefully(self):
    # read 抛 EOFError → play() 正常返回 outcome dict（outcome=='aborted'），无异常上抛
def test_map_screen_lists_choices(self)  # 地图渲染含当前层各可选节点编号与类型图标
```

- [ ] **步骤 2：运行验证失败**
- [ ] **步骤 3：实现 ui.py**（渲染函数逐屏拆分：`draw_combat/draw_map/draw_shop/draw_event/draw_campfire`；ANSI 颜色不实装——计划决定，纯黑白）
- [ ] **步骤 4：运行验证通过**
- [ ] **步骤 5：Commit**：`git commit -am "feat(warrior): 终端界面与输入循环"`

### 任务 12：main 装配、整局自走模拟与平衡微调

**文件：**
- 创建：`warrior/main.py`；追加 `warrior/test_run.py`

**接口：** `main(argv=None)`：读种子输入（默认 `time.time_ns()` 取模打印出来）→ `records.load` → `UI(Run(seed)).play()` → `update_records`+`save_records`（io_error 只 print 提示）→ 询问再来一局。`if __name__ == '__main__'` 守卫。

- [ ] **步骤 1：编写失败的测试**（`test_run.py::FullRunSimTests`，机器人策略内置于测试：出牌优先最高期望伤害、end_turn；火堆 hp<60% 选 sleep 否则 forge 首张；事件选第 1 项；商店买买得起的遗物→药水；地图优先火堆>商店>宝箱>事件>普通战斗，hp>75% 时优先踩精英）

```python
def test_20_seeds_no_crash(self):
    # 20 个种子全图跑完：断言每个 run.finished，且 >=18 个能走到 boss 节点（depth 达标）
def test_fixed_seed_winnable(self):
    # 种子 20261113 机器人局 outcome=='win'
def test_loss_path_settles(self):
    # 构造低开局血量注入（hp=8）后 bot 大概率死亡：断言 dead 时 stats 完整、records 更新路径可用
```

- [ ] **步骤 2：运行验证失败**
- [ ] **步骤 3：实现 main.py 并跑通模拟**；若 `test_fixed_seed_winnable` 失败按序微调（属规格 11 节授权）：金币产出 +10% → boss hp -10 → 掉落权重上调 → 火堆第 8 层保底放宽为第 7/8 层各 1；每调一档重跑 20 种子统计胜率，目标：bot 胜率 3~5/20（人类玩家上限更高）
- [ ] **步骤 4：运行全部测试**：`python -m unittest discover -v` → 全 PASS
- [ ] **步骤 5：人工验收清单**（规格 10.4）：真机 `python main.py` cmd 与 Windows Terminal 各打一小局——一屏不溢出、非法输入提示、`records.json` 落盘正常、损坏文件隔离生效
- [ ] **步骤 6：Commit**：`git commit -am "feat(warrior): 主装配与整局模拟测试，平衡微调至种子可胜"`

---

## 附录 A：卡牌池（30 张 = 2 基础 + 28 奖励池；upgrade 仅列增量数值）

`id|名称|费|效果原语|升级`（攻击伤害均为基准值，武器加成另计）

- strike 打击 1 `[damage 6]` → 9 ｜ defend 防御 1 `[block 5]` → 8（均不入奖励池）
- heavy 重击 2 `[damage 12]`→16 ｜ twin 连刺 1 `[damage 3,damage 3]`→4×3 ｜ cleave 横扫 1 `[damage_all 7]`→10 ｜ quake 震地 2 `[damage_all 7, block 3]`→10 ｜ whirl 旋风连斩 2 `[damage 4,damage 4,damage 4]`→5×3 ｜ execute 处决 2 `[execute 0.3 22 7]`→26/9 ｜ pierce 破甲刺 1 `[pierce 8]`→11 ｜ brand 猎印 1 `[bonus_if_vulnerable 6, damage 5]`→+9 ｜ rip 撕裂 0 `[damage 4, exhaust]`→7 ｜ poison_stab 淬毒之刺 1 `[damage 4, poison 4]`→poison 6 ｜ fury_edge 燃血斩 1 `[hp_cost 4, damage 11]`→15 ｜ shatter 碎骨 2 `[damage 9, self_vulnerable 1]`→13 ｜ annihilate 湮灭 3 `[hp_cost 6, damage 24]`→30
- iron_will 铁志 1 `[block 8]`→11 ｜ taunt 挑衅 1 `[vulnerable_all 2]`→3 ｜ warcry 战吼 0 `[draw 3]`→+block 5 ｜ focus 蓄能 0 `[energy 2]`→3 ｜ bulwark 壁垒 2 `[block 14]`→18 ｜ second_wind 回春 1 `[heal 6]`→9 ｜ adrenaline 肾上腺素 0 `[draw 2, energy 1, exhaust]`→+block 3 ｜ blood_price 血之代价 1 `[hp_cost 8, energy 3, exhaust]`→energy 4
- fury 狂怒 1 `[power first_attack_bonus 3]`→5 ｜ stone_skin 石肤 1 `[power block_per_turn 3]`→4 ｜ trance 战意 2 `[power strength_per_turn 2]`→3 ｜ keen 嗜刃 1 `[power draw_per_turn 1]`→+1 能量（power 键 energy_per_turn）｜ war_drum 战鼓 2 `[power strength_per_turn 1, power block_per_turn 2]`→2/3

稀有度：common = defend 系数值牌（twin/cleave/iron_will/warcry/focus/second_wind/rip/strike 系）；uncommon = poison_stab/fury_edge/whirl/brand/taunt/adrenaline/bulwark/fury/stone_skin/war_drum；rare = heavy/execute/pierce/quake/shatter/annihilate/trance/keen/blood_price。

## 附录 B：装备/遗物/药水与价格表

**武器**（WEAPONS，rusty 初始）：`id|攻击加成|mods`
- rusty 锈剑 +0 ｜ longsword 旅行者长剑 +1 ｜ axe 巨斩斧 +4 first_card_extra_cost=1 ｜ twinblades 双刃 -1 draw_per_turn=1 ｜ flame 燃火之刃 +2 turn_start_self_damage=2 ｜ spear 猎魔长矛 +2（无词条，商店最便宜档）

**防具**（ARMORS，无=不装备）：cloth 布甲 start_block 2 ｜ leather 皮甲 5 ｜ plate 板甲 9+energy_per_turn -1 ｜ spiked 刺甲 3+thorns 3 ｜ guardian 守护胸甲 4+heal 2（combat_start 回复）

**遗物**（RELICS，稀有度 C/U/R）：ember 炭炉石 U(combat_end heal 4) ｜ coffee 咖啡壶 R(首回合能量+1) ｜ horn 战吼号角 U(首回合抽+2) ｜ purse 钱包 C(gold_mult 1.25) ｜ tooth 巨魔之牙 R(hp<30% 开战力量+2) ｜ torch 火把 U(attack_damage_base +1) ｜ bandage 旧绷带 C(start_block +4) ｜ ration 口粮 C(turn_end heal 2) ｜ whetstone 磨刀石 U(每回合首击+2) ｜ hag_hat 商人之帽 U(shop_discount 0.8) ｜ lucky_dice 幸运骰 C(卡奖励+1 选) ｜ iron_heel 铁踵 R(回合结束格挡不衰减) ｜ warpaint 战纹面具 U(开战全体敌人 poison 1) ｜ vial 血之圣瓶 R(本局限一次：致死时回 30% hp) ｜ nugget 金锭 C(获得时立即 +30 金) ｜ fang_necklace 狼牙项链 U(thorns 2) ｜ idol 战神小像 R(power 卡费用 -1，最低 0) ｜ hourglass 时之沙漏 R(第 3/6/9…回合能量+1) ｜ crown 魔王冠冕 BOSS(通关奖杯，不入场内池)

**药水**：p_blood 血瓶 heal 14 ｜ p_energy 灵感 energy 2 ｜ p_fury 怒火 self_strength 3(本战) ｜ p_acid 酸瓶 damage 12(单体,targeted) ｜ p_gall 胆汁膏 poison_all 6

**商店定价**（base，hag_hat 后再 80% 取整）：牌 common 45/uncommon 65/rare 90；武器 longsword/spear/flame 100、axe 150、twinblades 120；防具 80~130（cloth 60）；遗物 C 110/U 140/R 175；药水 45；删牌 65。宝箱：金币 20~40 + 随机武器或防具（tier 匹配深度，已有同类时替换）。

**tier 映射**：hp ×1.0/1.3/1.6，招式伤害 +0/+1/+2（任务 3 定义）。

## 附录 C：效果原语封闭集

- 战斗卡/药水（content.PRIMITIVES）：`damage n`、`damage_all n`、`pierce n`、`execute frac hi lo`、`bonus_if_vulnerable n`、`self_vulnerable n`、`block n`、`draw n`、`energy n`、`hp_cost n`、`heal n`、`self_strength n`、`vulnerable n`、`poison n`、`vulnerable_all n`、`poison_all n`、`power key n`（key∈first_attack_bonus/strength_per_turn/block_per_turn/draw_per_turn/energy_per_turn）、`exhaust`。
- Gear mods 键（附录 B 用名）：`attack_bonus`(字段)、`first_card_extra_cost`、`draw_per_turn`、`turn_start_self_damage`、`energy_per_turn`、`start_block`、`thorns`、`heal`。
- 遗物 hooks 键：`combat_start`(dict: energy/draw/block/strength/poison_all/thorns…)、`turn_start`、`turn_end`(heal)、`attack_damage_base`、`cost_adjust`(kind,min)、`gold_mult`、`shop_discount`、`death_save`(pct,once)、`card_reward_extra`、`block_persist`、`instant_gold`、`first_attack_bonus`。
- 事件 outcome（EVENT_PRIMITIVES）：`hp n`（可为负）、`heal n`、`gold n`（可负，余额不足则选项置灰）、`gain_potion_random`、`gain_relic_random rarity`、`gain_gear_random kind tier`、`add_card_random rarity`、`upgrade_random_card`、`remove_random_card`、`start_combat [ids]`、`branch [(w, outcomes)...]`、`nothing`。
- 敌人 Move.kind：`attack`(damage,hits)、`block`(block)、`buff`(strength)、`debuff`(vulnerable)、`poison`(poison)。

## 附录 D：敌人表（hp 为 tier1 基准；weight 加权）

- goblin 哥布林 hp14：攻击 5(w3)/格挡 4(w1) ｜ wolf 野狼 hp12：攻击 3×2(w3)/攻击 6(w1) ｜ slime 史莱姆 hp20：攻击 4(w2)/格挡 6(w2) ｜ bandit 强盗 hp24：攻击 8(w3)/格挡 6+力量+1(w1) ｜ archer 骷髅弓手 hp16：攻击 4×3(w3)/攻击 9(w1) ｜ imp 小恶魔 hp18：攻击 7(w2)/易伤 2(w1)/毒 3(w1) ｜ knight 黑暗骑士 hp32：攻击 11(w3)/格挡 8+力量+2(w1)
- 精英 golem 石魔像 hp58(cycle)：格挡 12→蓄力(力量+2)→攻击 9×2 循环 ｜ 精英 assassin 影刺客 hp48(cycle)：攻击 4×3→攻击 10+易伤 1→格挡 6 循环
- boss demon_lord 魔王 hp160 phase2_at_half：阶段 1 cycle：攻击 12/格挡 10/攻击 6×2+易伤 1；阶段 2：phase2_per_turn_strength=2、招式池换入 攻击 15、攻击 8×2

**ENCOUNTERS**（(层区间, 池+weight, 上限数)）：(1~2, wolf/goblin/slime 独或双, 2)；(3~5, +bandit/archer，1~3 只)；(6~8, +imp/knight，2~3 只)；(9~10, knight/archer 混搭 2~3 只)。精英层直接单精英。

## 附录 E：事件表（9 个，outcome 用附录 C 原语）

- wounded_traveler 受伤的旅人：A 救助 `hp -3, gain_relic_random C`／B 搜身 `gold 25, branch[(1,[start_combat wolf]),(1,[nothing])]`／C 离开 nothing
- goblin_gambler 赌博地精：A 押 30 `gold -30, branch[(1,[gold 60]),(1,[nothing])]`／B 出千 `gold 45, branch[(1,[start_combat bandit imp]),(2,[nothing])]`／C 不赌
- dark_altar 黑暗祭坛：A 献 8 HP `hp -8, gain_relic_random U`／B 砸祭坛 `gain_gear_random weapon 2, branch[(1,[hp -6]),(1,[start_combat slime])]`／C 离开
- ruined_forge 铁匠铺废墟：A 翻找 `branch[(2,[gain_gear_random weapon 1]),(1,[hp -6]),(1,[gain_potion_random])]`／B 离开
- merchant_corpse 商人的尸体：A 搜刮 `gold 40, gain_potion_random, branch[(1,[start_combat bandit]),(2,[nothing])]`／B 安葬 `branch[(1,[gain_relic_random C]),(2,[nothing])]`
- hot_spring 温泉：A 泡澡 `heal 12`／B 灌满水壶 `gain_potion_random`／C 匆匆路过 `nothing`
- shrine_of_bones 骨之祠：A 祈祷 `upgrade_random_card`／B 亵渎 `gold 55, remove_random_card, branch[(1,[start_combat knight]),(2,[nothing])]`
- mimic_chest 会咬人的箱子：A 硬开 `hp -10, gain_relic_random U`／B 识破先手 `start_combat mimic`（新增弱怪 mimic hp20：攻击 9 重 2/格挡 5）／C 走开
- wandering_bard 流浪诗人：A 听一曲 `heal 4`／B 给小费 25 `gold -25, add_card_random uncommon`／C 点一曲《屠魔》 `gold -10, gain_potion_random`

## 附录 F：规格覆盖对照

| 规格章节 | 任务 |
|---|---|
| 6.1 地图/保底 | 6、7 |
| 6.2 战斗流程/状态 | 3、4 |
| 6.3 卡牌 | 1、3 |
| 6.4/6.5 武器防具 | 1、5 |
| 6.6 遗物 | 1、5 |
| 6.7 火堆 | 7 |
| 6.8 事件 | 2、9 |
| 6.9 商店 | 8 |
| 6.10 敌人/精英/魔王 | 2、4、6 |
| 6.11 药水 | 1、8 |
| 7 界面 | 11、12 |
| 8 存档/种子复现 | 10、7 |
| 10 测试策略 | 各任务 + 12 |
