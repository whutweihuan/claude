# 奶牛牧场实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 subagent-driven-development（推荐）或 executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在 `milkCow/` 实现一个 Tkinter 桌面奶牛挂机小游戏：小牛长大、自动繁殖、挤奶卖钱、加工奶酪、买饲料/扩建牧场。

**架构：** 照搬 `farmer/` 已验证的分层——`cow_core.py` 纯逻辑（时间戳推导 + `catch_up` 离线补算 + 原子存档），`cow_gui.py` Tkinter 界面（1 秒 refresh、300ms 走动动画、子进程真实 DPI 布局回归）。核心状态与动画严格分离：位置不进核心、不进存档。

**技术栈：** Python 3.8.3+、Tkinter 8.6、标准库（unittest、json、os、tempfile、subprocess、ctypes）。零第三方依赖。

**规格：** `milkCow/docs/superpowers/specs/2026-11-12-milkcow-game-design.md` —— 计划的论证依据来自规格，执行者两份都读。参考实现：`farmer/farm_core.py`、`farmer/farm_gui.py`、`farmer/test_farm.py`、`farmer/test_gui_smoke.py`。

## 全局约束

- 仅标准库 + Tkinter；不引入 Pillow 或任何第三方包；不使用 emoji（Tk 8.6 渲染不可靠），全部 Canvas 矢量绘制。
- 平台 Windows 10/11；`main()` 启动时调用 `ctypes.windll.shcore.SetProcessDpiAwareness(1)`，失败静默忽略。
- 窗口初始 1280×680，`minsize(1260, 640)`；仓库面板宽 340；牧场画布 760×460。
- 中文界面，字体 `("Microsoft YaHei UI", 10)`（另有 9 号小字、11 号加粗、14 号标题）。
- 所有时间使用 `time.time()` 浮点秒；核心函数一律显式注入 `now`，GUI 通过 `clock` 参数注入时钟以便测试。
- 存档 `milkCow/save.json` 与程序同目录；临时文件 + `os.replace` 原子写；容错三分类：文件不存在=新开档、JSON/校验失败=备份 `save.corrupt-<时间戳>.json` 后新开档、`OSError`=抛 `SaveUnreadableError` 且不写盘不覆盖。
- 金币唯一来源：卖牛奶/卖奶酪/卖牛；除此之外金币只减不增。
- 常量从规格逐字照抄：`GROWTH_YOUNG=45*60`、`GROWTH_ADULT=135*60`、`FEED_CREDIT=900`、`FEED_MAX=3`、`FEED_COOLDOWN=600`、`MILK_INTERVAL=1200`、`GESTATION=3600`、`POSTPARTUM=1800`、`CHEESE_MILK_COST=3`、`CHEESE_TIME=1200`、`INITIAL_COINS=200`、`INITIAL_CAPACITY=4`、`MAX_CAPACITY=12`、`MAX_MACHINES=3`、`CALF_PRICE=150`、`FEED_PRICE=25`、`MILK_PRICE=15`、`CHEESE_PRICE=75`、`COW_SELL_PRICES={"calf":80,"young":160,"adult":350}`、`MACHINE_PRICES=(300,700,1500)`、`CAPACITY_PRICES=(200,400,700,1000,1500,2200,3000,4000)`。
- 测试用 `unittest`，工作目录 `milkCow/`，命令 `python -m unittest test_cow -v` / `python -m unittest test_gui_smoke -v`；GUI 测试构建窗口用 `start_loops=False`，不进入 mainloop。
- 布局/DPI 纪律（项目 CLAUDE.md 已验证）：真实 DPI 布局测试必须在子进程内先调用 `_enable_dpi_awareness()` 再建 Tk；中文标签用自然宽度不用固定字符宽；Canvas 文字 `anchor="n"` 且留正上边距；断言 `font.measure(text) <= winfo_width()`、bbox 不出画布。

## 审查重点

- **离线极长时间（数天～30 天）**：`catch_up(now)` 必须终止且无死循环（容量闸门使事件有限）、结果与逐步推进一致 → 任务 6 测试覆盖。
- **多孕妇同日待产 + 牧场恰差一位**：生产、受孕排队按事件时间与 `eligible_at` 先后处理，任何时刻不出现 `牛数 > 容量` → 任务 6 测试覆盖。
- **系统时间回拨（now 早于 settled_until / 各时间戳）**：所有推导 `max(0, …)` 夹逼，不崩溃、不产生负库存、不重复产仔 → 任务 6/7 测试覆盖。
- **存档字段缺失、类型错误、未知 key、未知牛名字段**：整档判损坏并备份重开；`PermissionError` 不当损坏、本次禁用保存 → 任务 7 测试覆盖。
- **150% 缩放下牧场画布牛名/头顶标记 bbox 不出界、顶栏与商店按钮文字不裁切**：子进程真实 DPI 逐控件断言 → 任务 11 测试覆盖。

---

### 任务 1：核心骨架 —— 常量、Cow、阶段与奶量推导

**文件：**
- 创建：`milkCow/.gitignore`（内容：`__pycache__/`、`*.pyc`、`save.json`、`save.corrupt-*.json`）
- 创建：`milkCow/cow_core.py`
- 创建：`milkCow/test_cow.py`

**接口（本任务建立，后续任务全部依赖）：**

- `class Cow`（dataclass）：字段 `id: int`、`name: str`、`born_at: float`、`fed_count: int`、`last_fed_at: float`、`last_milked_at: float`、`pregnant: bool`、`due_at: float`、`recovery_until: float`。
- `stage_of(cow: Cow, now: float) -> str`：返回 `"calf" | "young" | "adult"`。有效年龄 = `now - born_at + fed_count * FEED_CREDIT`；阈值 45 分/135 分。
- `adult_at(cow: Cow) -> float`：`born_at + GROWTH_ADULT - fed_count * FEED_CREDIT`（成年时刻，与 now 无关）。
- `ready_at(cow: Cow) -> float`：`max(recovery_until, adult_at(cow))`（最早可受孕时刻，纯函数）。
- `udder_ready(cow: Cow, now: float) -> bool`：成年且 `now - max(last_milked_at, adult_at(cow)) >= MILK_INTERVAL`。
- `class GameState`：字段 `coins`、`capacity`、`cows: List[Cow]`、`machines: List[Optional[float]]`（元素为 `started_at` 或 `None`）、`warehouse: Dict[str, int]`（键 `"milk"`/`"cheese"`，缺项视为 0）、`feed_count`、`total_income`、`total_births`、`next_cow_id`、`settled_until: float`。
- `new_game(now: float) -> GameState`：金币 200、容量 4、1 头成年牛（`id=1, name="花花", born_at=now-10800, fed_count=0, last_milked_at=now, pregnant=False, recovery_until=0.0`）、`machines=[]`、仓库空、`feed_count=0`、`next_cow_id=2`、`settled_until=now`。
- 名字池常量 `NAME_POOL: Tuple[str, ...]`（12 个：花花、妞妞、大壮、团团、默默、糖糖、豆豆、云朵、麦子、布丁、奶茶、雪球）。
- `free_slot_left(state) -> bool`：`len(state.cows) + sum(c.pregnant for c in state.cows) < state.capacity`（预留空位闸门，买牛仔/受孕共用）。

- [ ] **步骤 1：编写失败的测试**（`test_cow.py`，类 `StageTests(unittest.TestCase)`）

```python
T0 = 1_700_000_000.0

def test_stage_boundaries(self):
    cow = make_cow(born_at=T0)          # 测试辅助：按字段构造 Cow，默认成年牛
    self.assertEqual(stage_of(cow, T0 + 45*60 - 1), "calf")
    self.assertEqual(stage_of(cow, T0 + 45*60), "young")
    self.assertEqual(stage_of(cow, T0 + 135*60 - 1), "young")
    self.assertEqual(stage_of(cow, T0 + 135*60), "adult")

def test_feed_credit_advances_stage(self):
    cow = make_cow(born_at=T0, fed_count=3)   # 省 45 分钟
    self.assertEqual(stage_of(cow, T0 + 90*60), "adult")   # 135-45=90 分钟即成年

def test_initial_game_is_one_adult_with_empty_udder(self):
    s = new_game(T0)
    self.assertEqual((s.coins, s.capacity, len(s.cows)), (200, 4, 1))
    self.assertEqual(stage_of(s.cows[0], T0), "adult")
    self.assertFalse(udder_ready(s.cows[0], T0))
    self.assertTrue(udder_ready(s.cows[0], T0 + 1200))      # 20 分钟满奶
    # make_cow(born_at=T0) 是刚出生的牛仔；134 分钟时仍是青年牛，未成年永不满奶
    self.assertFalse(udder_ready(make_cow(born_at=T0), T0 + 134 * 60))

def test_free_slot_counts_pregnant_cows(self):
    s = new_game(T0)
    s.capacity = 2; s.cows.append(make_cow(id=2)); s.cows[1].pregnant = True
    self.assertFalse(free_slot_left(s))                     # 牛2 + 孕妇1 = 3 > 2 的预留：牛数+孕妇数<容量
```

（`make_cow(**overrides)` 为本测试文件的辅助函数：成年、未孕、`born_at=T0-10800`、`last_milked_at=T0` 为默认，按 overrides 覆盖。）

- [ ] **步骤 2：运行验证失败** — `python -m unittest test_cow -v`，预期 ERROR（`ModuleNotFoundError: cow_core` 或符号未定义）。
- [ ] **步骤 3：实现** `cow_core.py` 上述常量与函数/类（阶段推导注意 `max(0.0, …)` 防回拨：有效年龄为负按 0）。`last_milked_at` 锚点用 `max(last_milked_at, adult_at(cow))`。
- [ ] **步骤 4：运行验证通过** — 预期 4 个测试 PASS。
- [ ] **步骤 5：Commit** — `git add milkCow/.gitignore milkCow/cow_core.py milkCow/test_cow.py && git commit -m "feat(milkCow): 核心常量与成长/奶量推导"`

### 任务 2：挤奶与一键挤奶

**文件：** 修改 `cow_core.py`、`test_cow.py`。

**接口：**
- `catch_up(self, now: float) -> None`：本任务先建雏形——只做 `self.settled_until = max(self.settled_until, now)`；任务 5、6 扩展。所有会改变世界的玩家操作（milk/sell/feed/process/买/扩建）开头先调它，保证时间线一致。
- `milk(self, cow_id: int, now: float) -> None`：`catch_up` → 找不到牛报 `ValueError("没有这头牛")`；未满奶报 `ValueError("这头牛还没蓄满奶")`；成功则 `warehouse["milk"] += 1`、`last_milked_at = now`。挤孕妇/休养牛合法。
- `milk_all(self, now: float) -> int`：对所有 `udder_ready` 的牛逐头 `milk`，返回头数；0 头合法（不报错）。
- `sell_stock(item: str) -> int` / `sell_all_stock() -> int`：卖出仓库单项/全部，按 `MILK_PRICE`/`CHEESE_PRICE` 加金币并累加 `total_income`，清零该键；数量 0 返回 0 不报错。`stock_value() -> int`：当前库存总价值。

- [ ] **步骤 1：编写失败的测试**（`MilkTests`）

```python
def test_milk_requires_full_udder(self):        # 19:59 报错“这头牛还没蓄满奶”，20:00 成功 milk×1
def test_milk_resets_timer(self):               # 挤后 now+1199 不可挤，now+1200 可再挤
def test_milk_pregnant_cow_allowed(self):       # pregnant=True 的成年牛可挤，金币不变
def test_milk_all_counts_only_ready(self):      # 2 满 1 不满 → 返回 2，milk 库存 +2；全不满返回 0
def test_milk_unknown_id_raises(self):          # “没有这头牛”
def test_sell_milk_adds_coins(self):            # 3 瓶卖 45 金币，total_income=45，库存清零
def test_sell_all_stock_totals(self):           # milk2+cheese1 = 30+75=105；空仓返回 0
```

- [ ] **步骤 2：运行验证失败** — FAIL/ERROR。
- [ ] **步骤 3：实现**（`milk_all` 内部复用 `milk`；库存卖出是纯金币操作、无时间参数，与 farmer 的 `sell` 一致）。
- [ ] **步骤 4：运行验证通过** — 全部 PASS。
- [ ] **步骤 5：Commit** — `"feat(milkCow): 挤奶与库存卖出"`

### 任务 3：高级饲料

**文件：** 修改 `cow_core.py`、`test_cow.py`。

**接口：**
- `can_feed(self, cow_id: int, now: float) -> bool`：牛存在、`stage_of != "adult"`、`fed_count < FEED_MAX`、`now - last_fed_at >= FEED_COOLDOWN`（首喂 `last_fed_at=0` 天然通过）、`feed_count > 0`。
- `feed(self, cow_id: int, now: float) -> None`：`catch_up` 后校验，失败按原因抛 `ValueError`（文案分别为“这头牛已经成年”/“这头牛最多喂 3 次”/“投喂间隔不足 10 分钟”/“没有高级饲料”/“没有这头牛”）；成功则 `feed_count -= 1`、`cow.fed_count += 1`、`cow.last_fed_at = now`。

- [ ] **步骤 1：编写失败的测试**（`FeedTests`）

```python
def test_feed_advances_adulthood(self):
    s = new_game(T0); calf = make_cow(id=2, born_at=T0); s.cows.append(calf); s.feed_count = 1
    s.feed(2, T0)
    self.assertEqual(stage_of(calf, T0 + 120 * 60), "adult")  # 135 - 15（一次饲料）= 120 分钟成年
    self.assertEqual(stage_of(calf, T0 + 119 * 60), "young")
def test_feed_three_max_and_cooldown(self):    # 第 4 次抛“最多喂 3 次”；9 分 59 秒后再喂抛“间隔不足”
def test_feed_rejects_adult_and_empty_bag(self):  # “已经成年” / “没有高级饲料”
def test_feed_does_not_touch_coins(self):     # feed() 本身不扣金币（钱在花购买时已付）
```

- [ ] **步骤 2：运行验证失败**。
- [ ] **步骤 3：实现**。
- [ ] **步骤 4：运行验证通过**。
- [ ] **步骤 5：Commit** — `"feat(milkCow): 高级饲料加速生长"`

### 任务 4：商店经济 —— 买牛仔、卖牛、买饲料、买加工器、扩建

**文件：** 修改 `cow_core.py`、`test_cow.py`。

**接口：**
- `buy_calf(self, now: float) -> int`：`catch_up` → 校验 `free_slot_left`（否则 `ValueError("牧场满了")`）、金币（“金币不够”）→ 扣 150，新牛入场（`id=next_cow_id`、`born_at=now`、`last_milked_at=now`、未孕、`recovery_until=0`），返回新牛 id。
- `sell_cow(self, cow_id: int, now: float) -> int`：`catch_up` → 按卖出瞬间 `stage_of` 取 `COW_SELL_PRICES`；移除该牛（孕妇可卖，`due_at` 随对象消失）；加金币、`total_income`；返回所得。之后**立即调用 `conception_pass(now)`**（任务 6 提供；任务 4 实现时先声明为 `catch_up` 末尾同样调用的空实现，任务 6 填充）——腾位即补位。
- `buy_feed(self) -> int`：扣 25，`feed_count += 1`，返回背包份数。
- `buy_machine(self) -> None`：`len(machines) >= 3` 抛“加工器已达上限”；价格 `MACHINE_PRICES[len(machines)]`；扣款后 `machines.append(None)`。
- `expand_capacity(self) -> None`：`capacity >= 12` 抛“牧场已扩建到上限”；价格 `CAPACITY_PRICES[capacity - INITIAL_CAPACITY]`；扣款 `capacity += 1`。
- 所有价格校验失败统一 `ValueError("金币不够")`。

- [ ] **步骤 1：编写失败的测试**（`ShopTests`）

```python
def test_buy_calf_price_and_gate(self):
    s = new_game(T0); s.capacity = 1
    with self.assertRaisesRegex(ValueError, "牧场满了"): s.buy_calf(T0)   # 预留闸门按牛数，非容量-1
def test_sell_price_by_stage(self):            # 牛仔 80 / 青年 160 / 成年 350；total_income 累加
def test_sell_pregnant_cow_removes_fetus(self):  # 卖出孕妇后 cows 无该 id，不发生其生产
def test_sell_last_slot_opens_reservation_gate(self):
    s = new_game(T0); s.capacity = 2; 塞满 2 头（其中 1 孕妇）→ 卖孕妇 → free_slot_left True
def test_machine_prices_sequence(self):        # 300、700、1500，第 4 台抛上限
def test_expand_prices_sequence(self):         # 4→12 共 8 次，价格逐字等于 CAPACITY_PRICES，之后抛上限
```

- [ ] **步骤 2：运行验证失败**。
- [ ] **步骤 3：实现**。
- [ ] **步骤 4：运行验证通过**。
- [ ] **步骤 5：Commit** — `"feat(milkCow): 商店经济：买牛仔/卖牛/饲料/加工器/扩建"`

### 任务 5：奶酪加工 + catch_up 雏形（机器结算）

**文件：** 修改 `cow_core.py`、`test_cow.py`。

**接口：**
- `process(self, machine_index: int, now: float) -> None`：`catch_up` → 越界抛“没有这台加工器”；非空闲抛“加工器正忙”；`warehouse["milk"] < 3` 抛“牛奶不够”；扣 3 奶、`machines[i] = now`。
- `process_all(self, now: float) -> int`：把所有空闲机器按库存排满（每轮 3 奶），返回启动台数。
- `catch_up` 扩展：机器项 `started_at is not None and started_at + CHEESE_TIME <= now` → `warehouse["cheese"] += 1`、置 `None`；然后 `settled_until = max(settled_until, now)`（生产链事件在任务 6 加入同一函数）。

- [ ] **步骤 1：编写失败的测试**（`CheeseTests`）

```python
def test_process_consumes_and_busy(self):      # 投料后 milk-3、机器忙；再投抛“加工器正忙”
def test_cheese_settles_on_catch_up(self):     # now+1199 无奶酪；catch_up(now+1200) 后 cheese+1、机器空闲
def test_cheese_sale_value(self):              # 奶酪卖 75
def test_process_all_fills_machines(self):     # 2 台空闲 + 7 牛奶 → 启动 2 台、剩 1 奶；返回 2
def test_process_requires_milk(self):          # 2 瓶奶时投料抛“牛奶不够”，机器不占用
```

- [ ] **步骤 2：运行验证失败**。
- [ ] **步骤 3：实现**。
- [ ] **步骤 4：运行验证通过**。
- [ ] **步骤 5：Commit** — `"feat(milkCow): 奶酪加工与机器离线结算"`

### 任务 6：繁殖状态机与离线补算（本计划核心风险任务）

**文件：** 修改 `cow_core.py`、`test_cow.py`。

**机制（规格 §6.3，逐条钉死）：**

- `conception_pass(self, at: float) -> None`：所有非孕成年牛按 `(ready_at(cow), id)` 升序，逐个尝试：若 `ready_at(cow) <= at` 且 `free_slot_left(self)` → `pregnant=True, due_at = at + GESTATION`。**注意：受孕时刻 `at` 由调用方给出**（离线补算里是事件时间，在线是操作/结算时间），保证“事件时间锚定”。
- `catch_up(self, now)` 完整算法（替换任务 5 版本，保持机器结算在前）：

```
循环（事件驱动）：
  1. 收集事件时刻集合 E = {cow.due_at | 孕妇} ∪ {cow.ready_at(cow) | 非孕成年且 ready_at ∈ (settled_until, now]}
  2. T = min(E)；若 E 为空 → 跳出
  3. settled_until = T；处理 T 的全部孕妇生产：每头 born_at=T 的孕牛 → pregnant=False、
     due_at=0、recovery_until = T + POSTPARTUM；新生小牛 Cow(id=next_cow_id++, name=NAME_POOL 中
     第一个未被占用名字, born_at=T, last_milked_at=T, 未孕, recovery_until=0)；total_births += 每头
  4. conception_pass(T)
  5. 若 T 后没有任何牛能立即受孕（循环 1 已含），继续循环；settled_until 单调推进 → 循环必然终止
跳出后 settled_until = max(settled_until, now)；若此刻仍有 free_slot_left 且有 ready_at <= now 的
非孕成年牛 → conception_pass(now)
```

- 幂等与夹逼：对同一 `now` 重复调用无新事件；`now < settled_until`（时间回拨）时只做 `max` 夹逼、不产生任何生产/受孕；`due_at < settled_until` 的孕妇（回拨产物）在生产事件处理里 `T = max(T, settled_until)` 归一，不崩溃。
- `new_game` 首头牛受孕发生在**第一次 `catch_up`**（规格：开局立即怀孕）。

- [ ] **步骤 1：编写失败的测试**（`BreedingTests`，前两个是全局验收级）

```python
def test_offline_jump_equals_online_stepping(self):
    """离线一跳 == 在线每 30 分钟一步，12 小时（足够填满容量 4）。"""
    a = new_game(T0)
    b = new_game(T0)
    for k in range(1, 25):                      # 24 步 × 1800s = 12h
        a.catch_up(T0 + k * 1800.0)
    b.catch_up(T0 + 12 * 3600.0)
    self.assertEqual(snapshot(a), snapshot(b))  # snapshot: cows 字段列表(排序)、warehouse、coins、
                                                # total_births、capacity、settled_until 归一后对比
    # 预期轨迹（写进注释供排错）：T0 受孕 → +1h 生 A → 母 +1.5h 再孕 → +4h 满 4 头 → 排队等待

def test_idempotent_catch_up(self):
    s = new_game(T0); s.catch_up(T0 + 3600 * 50)
    snap1 = snapshot(s); s.catch_up(T0 + 3600 * 50)
    self.assertEqual(snap1, snapshot(s))        # 重复结算不改世界；循环终止（离线 50h）

def test_initial_cow_pregnant_at_first_settle(self):   # catch_up(T0) 后 cows[0].pregnant 且 due_at=T0+3600

def test_reservation_gate_blocks_births(self):
    s = new_game(T0); s.capacity = 1; s.catch_up(T0 + 10 * 3600)
    self.assertEqual(len(s.cows), 1)            # 容量 1：初始牛怀不上（无预留位）

def test_pending_queue_conceives_in_order(self):
    # 两头已成年牛在容量 2 里都排队 → 卖一头 → conception_pass 补位的是 ready_at 更早者

def test_two_pregnant_one_slot_chain(self):     # 审查重点 2：构造 2 孕妇 + 差 1 位，链式生产不超员

def test_time_rollback_does_not_crash(self):    # catch_up(T0+7200) 后再 catch_up(T0+600)：无新事件、无负库存
```

- [ ] **步骤 2：运行验证失败**。
- [ ] **步骤 3：实现 `conception_pass` 与新版 `catch_up`**（算法框已给；名字分配“第一个未被占用”用 `set(已用名)`；`sell_cow`/买操作处接到 `conception_pass`）。
- [ ] **步骤 4：运行验证通过** — 全套 `python -m unittest test_cow -v`（含此前任务回归）全绿。
- [ ] **步骤 5：Commit** — `"feat(milkCow): 自动怀孕/生产与离线补算"`

### 任务 7：存档读写与三分类容错

**文件：** 修改 `cow_core.py`、`test_cow.py`。

**接口：**
- `GameState.to_dict() -> dict` / `GameState.from_dict(data) -> GameState`：version=1，逐字段严格校验（风格照抄 `farm_core.FarmState.from_dict`）：`coins/capacity/next_cow_id/total_income/total_births/feed_count` 为合法非负 int（`_is_plain_int`）；`capacity ∈ [4,12]`；`cows` 为 list 且每头字段类型正确、`id` 不重复；`machines` 长度 ≤3、元素为 `null` 或非负数；`warehouse` 只认 `"milk"/"cheese"` 键、值为非负 int，未知键忽略；`settled_until` 数值；任一校验失败抛 `ValueError`（=损坏）。
- `save_state(state, path)`：临时文件 + `os.replace`（照抄 farmer）。
- `load_state(path) -> (GameState, Optional[str])`：不存在→`(new_game(time.time()), None)`；`ValueError`（JSON 或校验）→ 备份 `save.corrupt-<时间戳>.json` 后 `(new_game, "存档损坏，已开始新的一局")`；`OSError` → 抛 `SaveUnreadableError("读取存档失败：…；本次不会保存")`。**注意与 farmer 不同**：新开档时间基准是 `time.time()`（牛龄、孕期全部相对此刻成立）。

- [ ] **步骤 1：编写失败的测试**（`SaveTests`）

```python
def test_roundtrip_preserves_world(self):
    # 造一个含孕妇/小牛/2 台机器(1 忙)/仓库/饲料/expanded 容量的档，save → load → snapshot 相同
def test_missing_file_starts_new_game(self):    # load_state(不存在) → new_game 语义（coins 200、1 牛）
def test_corrupt_json_is_backuped(self):        # 写坏 JSON → 返回消息含“存档损坏”，原文件变 corrupt-*.json，目录里可重开
def test_bad_field_is_corrupt(self):            # coins="abc" / capacity=99 / 重复 id / 负库存 → 均判损坏
def test_unknown_keys_ignored(self):            # 多余字段向前兼容；warehouse 里 {"foo":1} 被忽略
def test_permission_error_raises_unreadable(self):  # mock Path.open 抛 PermissionError → SaveUnreadableError，
                                                    # 且原文件内容未被改动、未生成 corrupt 备份
def test_offline_growth_survives_save(self):    # save 时 T0，load 后人工 catch_up(T0+2h)：牛长大了
```

- [ ] **步骤 2：运行验证失败**。
- [ ] **步骤 3：实现**（`_is_plain_int`/`_is_number`/`_non_negative_or_zero` 辅助函数照抄 `farm_core.py:269-280` 的实现风格）。
- [ ] **步骤 4：运行验证通过**。
- [ ] **步骤 5：Commit** — `"feat(milkCow): 原子存档与三分类容错"`

### 任务 8：GUI 骨架 —— 窗口、顶栏、牧场画布静态绘制、仓库面板、标题

**文件：**
- 创建：`milkCow/cow_gui.py`
- 创建：`milkCow/test_gui_smoke.py`

**接口（全部在 `cow_gui.py`）：**
- 色板与字体常量：仿 `farm_gui.py:14-29`（`BG/HEADER_BG/TEXT/MUTED/GREEN/HIGHLIGHT` + 草地 `GRASS = "#7FB069"`、牛白 `COW_WHITE = "#F4F1EA"`、牛黑斑 `COW_BLACK = "#3A3A3A"`、`FONT/FONT_SMALL/FONT_BOLD/FONT_TITLE`）。
- `format_remaining(seconds) -> str`（MM:SS 或 H:MM:SS）与 `format_duration`：**直接照抄 farmer 的两个函数**（测试也要对比同款实现，别改舍入）。
- `class PastureCanvas(tk.Canvas)`：`WIDTH=760, HEIGHT=460`；背景固定绘制（草地渐变 + 4 条深绿草斑带 + 白色栅栏描边，`_draw_scenery()` 只在构建时画一次）；`render(state, now, positions: Dict[int, Tuple[float, float]])`：清 `cow` tag 重画每头牛；牛是矢量组（身体椭圆 + 黑斑 2 个 + 头 + 耳 + 腿 4 条 + 尾巴线），尺寸系数 牛仔 0.55 / 青年牛 0.75 / 成年牛 1.0，身体长轴基准 56px；名字文字 `anchor="n"` 画在牛下方 `y+26`（字号 9）；满奶→头顶画白色奶滴（小圆+三角），孕妇→画粉色爱心（两圆+三角），标记文字/图形不得越出画布（bbox 校验由任务 11 做）；`texts()` 返回所有 text item（供测试）。
- `class CowApp(tk.Tk)`：`__init__(self, save_path=None, start_loops=True, clock=time.time)`；流程：`load_state`（`SaveUnreadableError` → 状态栏原因 + 本次禁用保存标志 `self._readonly=True`）→ `catch_up(clock())` → `_build_ui()` → `refresh()` → `start_loops` 时启动 `_tick`（1000ms）与 `_autosave`（10000ms）。
- `_build_ui` 布局（规格 §7）：顶栏 Frame（`coins_var`/`cows_var`（如 `牛 3/4（孕1）`）/`ready_var`（可挤奶 n）/`income_var`/扩建按钮 `expand_button`）；中部左右分栏：牧场画布 `self.pasture` + 右侧 `warehouse_frame`（宽 340，`milk_var`/`cheese_var` 两行 + `sell_buttons` dict + `sell_all_button`）；下：操作栏 `action_frame`（默认 `未选中任何牛，点一头试试`，选中后显示名字/阶段/状态/倒计时 + `挤奶`/`喂食（背包 N 份）`/`卖牛 <价>` 三按钮）；再下：商店栏（`buy_calf_button`/`buy_feed_button`/`buy_machine_button` + 加工器行容器 `machine_frame`，每台一行 label + `投料` 按钮，行尾 `全部投料` 按钮）；最底：状态栏 `status_var`。
- `refresh()`：调 `state.catch_up(now)` 后重算全部 label/var、`pasture.render`、`set_operation_buttons`（置灰规则见 §7 各栏）与标题：`"奶牛牧场（N 可挤）"` 或 `"奶牛牧场"`；`set_status(text, seconds=3)` 照抄 farmer 模式。
- `_enable_dpi_awareness()` 与 `main()`：照抄 `farm_gui.py:561-572`。

- [ ] **步骤 1：编写失败的测试**（`test_gui_smoke.py`，仿 farmer 的 `GuiSkeletonTests`）

```python
class GuiSkeletonTests(unittest.TestCase):
    def setUp(self):  # tmp save_path + CowApp(save_path=..., start_loops=False, clock=lambda: self.now)
    def test_window_builds_with_title_and_pasture(self):
        self.assertEqual(self.app.title(), "奶牛牧场")
        self.assertEqual((self.app.pasture.WIDTH, self.app.pasture.HEIGHT), (760, 460))
    def test_initial_cow_drawn_with_name(self):
        self.assertTrue(any("花花" in t for t in self.app.pasture.texts()))
    def test_startup_conceives_initial_cow(self):
        self.assertTrue(self.app.state.cows[0].pregnant)   # 爱心标记出现
        self.app.refresh(); self.assertTrue(any("孕" in v.get() for v in [self.app.cows_var]))
    def test_title_shows_milking_count(self):
        self.app.state.cows[0].last_milked_at = self.now - MILK_INTERVAL - 1; self.app.refresh()
        self.assertEqual(self.app.title(), "奶牛牧场（1 可挤）")
```

- [ ] **步骤 2：运行验证失败**（`ModuleNotFoundError: cow_gui`）。
- [ ] **步骤 3：实现**（中文 label 一律自然宽度 + grid 权重；`pack_propagate(False)` 只允许用于仓库面板定宽 340）。
- [ ] **步骤 4：运行验证通过**。
- [ ] **步骤 5：Commit** — `"feat(milkCow): GUI 骨架与牧场矢量绘制"`

### 任务 9：GUI 交互 —— 点牛、操作栏、商店、加工、卖出全接线

**文件：** 修改 `cow_gui.py`、`test_gui_smoke.py`。

**接口（`CowApp` 方法，测试直接调用、不模拟鼠标）：**
- `_on_cow_click(cow_id)`：`udder_ready` → `_do_milk(cow_id)`（调 `state.milk` + 飘字 `"+1 牛奶"` + refresh）；否则 `_select_cow(cow_id)`（`self.selected_id`，操作栏刷新）。
- `_on_pasture_click(event)`：`canvas.find_closest` 命中牛 tag → 转 `_on_cow_click`；空白 → `self.selected_id = None` 取消选中。
- `_on_milk_all_click()`：`state.milk_all(now)`，0 头时状态栏“没有蓄满奶的牛”。
- `_on_feed_click()` / `_on_sell_cow_click()` / `_on_buy_calf_click()` / `_on_buy_feed_click()` / `_on_buy_machine_click()` / `_on_expand_click()` / `_on_process_click(i)` / `_on_process_all_click()` / `_on_sell_click(item)` / `_on_sell_all_click()`：各自调 core，`except ValueError as exc: set_status(str(exc))`（金币不够/牧场满了等文案直达状态栏，不弹窗）；成功后状态栏反馈具体所得（如“卖出牛奶 ×3，+45 金币”）。
- 操作栏按钮可用性规则（refresh 内计算）：挤奶按钮仅选中且满奶可用；喂食按钮文案 `喂食（背包 N 份）`，成年/超次/冷却/无饲料时置灰并在状态栏给原因；卖牛按钮文案带当前阶段价。
- 商店按钮置灰文案：买牛仔 `牧场满了` / `金币不够`；加工器第 3 台后 `加工器已达上限`；扩建满 12 后 `已全部扩建`（按钮消失，label 替代——照抄 farmer `buy_land` 处理）。
- 飘字：`PastureCanvas.show_float(text, x, y)`，1 秒删除，照抄 farmer `PlotCard.show_float` 模式。
- `_save()` / `_on_close()`：照抄 farmer——`self._readonly` 时跳过一切保存。

- [ ] **步骤 1：编写失败的测试**（`GuiInteractionTests`）

```python
def test_click_full_cow_milks(self):      # last_milked_at 拨旧 → _on_cow_click(1) → warehouse milk=1、金币不变、状态栏含“+1 牛奶”
def test_click_not_full_cow_selects(self):  # 只选中：action_frame 显示“花花”，不产生奶
def test_milk_all_button(self):           # 3 头满奶 → 点击 → milk=3、标题回到“奶牛牧场”
def test_buy_calf_disabled_when_full(self):  # capacity=1：按钮置灰文案“牧场满了”；直调 handler 状态栏给原因
def test_sell_cow_click_adds_coins(self): # 选中成年牛 → _on_sell_cow_click → coins+350、牧场牛数-1
def test_process_click_starts_machine(self):  # 备 3 奶 → _on_process_click(0) → machines[0] 非 None、milk=0
def test_sell_all_totals_in_button_text(self):  # sell_all_button 文案含库存总值（如“全部卖出（165）”）
def test_error_goes_to_status_not_dialog(self): # 金币不足买加工器：status_var 有“金币不够”，无新 messagebox 依赖
```

- [ ] **步骤 2：运行验证失败**。
- [ ] **步骤 3：实现接线**。
- [ ] **步骤 4：运行验证通过** — `python -m unittest test_gui_smoke -v`（含任务 8 回归）。
- [ ] **步骤 5：Commit** — `"feat(milkCow): GUI 交互全接线"`

### 任务 10：自动走动动画

**文件：** 修改 `cow_gui.py`、`test_gui_smoke.py`。

**接口：**
- `CowApp` 新增 `self.positions: Dict[int, Tuple[float, float]]`、`self._targets: Dict[int, ...]`（目标点/速度/停留计时）、`self._rng = random.Random(anim_seed)`；构造参数 `anim_seed: int = 0`。
- 布局区内随机游走：可行走区域 `x ∈ [70, 690]、y ∈ [90, 380]`（避开栅栏描边与名字带），新目标均匀随机；速度：成年 22 px/s、青年 26、牛仔 32（300ms tick 位移 = 速度×0.3）；到达后停留 `rand(2.0, 8.0)` 秒。牛朝向按 `dx` 符号翻转（`scale` 绘制时用正/负 x 系数即可，别引入图片变换）。
- `_animate()`：`after(300, self._animate)`；`start_loops=False` 时不注册；每步只对 `positions` 插值并 `pasture.render(...)`（不重算 label/标题，那是 `refresh` 的事）。
- **纪律：动画只读核心、不写核心**——`positions` 不进 `to_dict`；`_animate` 内禁止调用任何会改 `state` 的方法。
- 牛被卖出/新牛入场时 `positions` 同步增删（新牛落在随机点，用 `_rng`）。

- [ ] **步骤 1：编写失败的测试**（`GuiAnimationTests`）

```python
def test_positions_advance_with_seed(self):
    # start_loops=False；手动调 self.app._animate_step(0.3, 0.3) ×N 次；同 seed 两次运行轨迹一致；牛在区域内
def test_animation_does_not_mutate_state(self):
    snap = snapshot_core(self.app.state); self.app._animate_step(0.3, 0.3); self.assertEqual(snap, snapshot_core(self.app.state))
def test_closed_animation_leaves_cow_still(self):  # start_loops=False 时不 after → positions 不变
def test_sold_cow_position_removed(self):          # 卖牛后 cow_id 不在 positions
```

（把动画推进抽成 `_animate_step(dt: float, dwell: float)` 纯函数式步进以便测试；`_animate` 只是 `after` 循环壳。）

- [ ] **步骤 2：运行验证失败**。
- [ ] **步骤 3：实现**。
- [ ] **步骤 4：运行验证通过**。
- [ ] **步骤 5：Commit** — `"feat(milkCow): 奶牛随机溜达动画（纯装饰层）"`

### 任务 11：DPI 布局回归 + 启动脚本 + README + 全量验证

**文件：**
- 修改：`milkCow/test_gui_smoke.py`（新增子进程 DPI 测试类）
- 创建：`milkCow/run_milkcow.bat`、`milkCow/README.md`

- [ ] **步骤 1：编写失败的测试** — `GuiLayoutTests`：仿 `farmer/test_gui_smoke.py:260-393`：
  - 同进程基础版：窗口 `winfo_reqwidth() <= winfo_width()`；`warehouse_frame` 内每个 label/按钮 `font.measure(text) <= winfo_width()`；商店按钮文字不裁切；操作栏文案完整显示。
  - 子进程真实 DPI 版（`@unittest.skipUnless(sys.platform == "win32", ...)`，脚本内先 `cow_gui._enable_dpi_awareness()` 再 `CowApp(save_path=临时, start_loops=False)`）：塞满 4 头牛（1 孕妇、2 满奶、1 牛仔，通过改 `born_at/last_milked_at` 构造），`refresh/update/update_idletasks` 后逐控件测量；**并遍历 `pasture` 全部 text item：`bbox` 不得越出 760×460**（farmer 踩过的作物名裁切坑，这里对应牛名与爱心/奶滴标记文字）。任何一条问题打印后 `sys.exit(1)`，父测试断言 `returncode == 0`。
- [ ] **步骤 2：运行验证失败**（先只写测试；若骨架已达标可能直接绿——绿了就进下一步，这步允许"无红"，但必须先跑过确认测量代码真的执行了：故意把仓库面板改成 60px 宽跑一次红，再改回）。
- [ ] **步骤 3：** 创建 `run_milkcow.bat`：

```bat
@echo off
cd /d %~dp0
start "" pythonw cow_gui.py
```

- [ ] **步骤 4：** 创建 `README.md`：结构照 farmer README（运行方式、玩法循环、数值表（牛阶段/饲料/怀孕周期/加工/价格全列）、存档说明、测试命令）；数值表逐字用规格 §6 的定稿值。
- [ ] **步骤 5：全量验证** — `python -m unittest test_cow test_gui_smoke -v` 全绿；再**手动走一遍真实启动路径**：双击 bat 打开窗口，确认 150% 缩放下无裁切、牛会走动、把系统时间改到 +2 小时后重开能补齐怀孕/生产/奶酪，然后改回。逐项过规格 §10.3 的 10 条人工验收（短周期项用改时钟/改存档字段模拟，不真等 1 小时）。
- [ ] **步骤 6：Commit** — `"feat(milkCow): DPI 回归测试、启动脚本与说明文档"`

---

## 自检记录

- 规格覆盖度：§3 目标 → 任务 1-11；§6.1-6.7 → 任务 1-7；§7 界面 → 任务 8-11；§8 存档 → 任务 7；§10 测试 → 各任务步骤 1 + 任务 11；§9.3 DPI 纪律 → 任务 11。无遗漏。
- 类型一致性：`catch_up/conception_pass/free_slot_left/udder_ready/ready_at/adult_at/stage_of/new_game/snapshot` 各定义点与引用点已核对（`snapshot` 为测试辅助，任务 6 定义在 `test_cow.py`，任务 7/10 复用 `snapshot_core`（test_gui_smoke 版）需注意导入路径——执行时把公共 helper 放各测试文件各自一份，不跨文件依赖）。
- 比例：代码块仅出现在算法框（catch_up）、bat、测试断言样例；函数体留给实现者。
