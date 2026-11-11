# 小菜园（桌面种田挂机游戏）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 subagent-driven-development（推荐）或 executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 用 Python + Tkinter 做一个可挂机的桌面种田小游戏：种菜、等真实时间生长、收获进仓库、卖钱买种子和地。

**架构：** `farm_core.py` 放纯逻辑（作物表、地块、仓库、经济、存档），不依赖 Tkinter，时间以参数注入；`farm_gui.py` 只负责界面、绘制和每秒刷新。核心逻辑先测后写，GUI 做冒烟测试。

**技术栈：** Python 3.8.3、Tkinter 8.6、标准库（`dataclasses`、`json`、`unittest`、`pathlib`），零第三方依赖。

**规格：** `farmer/docs/superpowers/specs/2026-11-11-farmer-game-design.md`

## 全局约束

- 只用 Python 标准库；不引入 Pillow、pygame 或任何第三方包。
- 目标平台 Windows 10/11，从 `farmer/` 目录运行。
- 界面中文，字体用 `Microsoft YaHei UI`；不使用 emoji，作物全部用 Canvas 绘制。
- 所有面向玩家的提示文案为中文。
- 存档固定为程序同目录的 `save.json`，运行时生成，不提交 git。
- 核心逻辑中所有时间参数由调用方传入；核心代码不得直接调用 `time.time()`，只有 `to_dict` 写 `saved_at` 和 `load_state` 生成损坏备份文件名时例外。
- 测试命令在 `farmer/` 目录下执行：`python -m unittest test_farm -v`、`python -m unittest test_gui_smoke -v`。
- 每个任务结束前测试必须全绿，并单独提交。
- 每个 commit message 末尾加：`Co-Authored-By: Claude Code <noreply@anthropic.com>`。
- 执行前从 `main` 建分支 `feat/farmer-game`；只提交 `farmer/` 下的文件，不碰工作区里其他项目的改动。

## 审查重点（Review Focus）

1. 系统时间回拨导致“已生长时长”为负：应按 0 处理，作物不会瞬间成熟或报错。由任务 2 的 `test_clock_rollback_counts_zero_elapsed` 覆盖。
2. 存档字段类型错误（`coins` 是字符串、`plots` 不是列表）：应备份原文件并重开一局，不能崩溃。由任务 7 的 `test_load_invalid_types_resets` 覆盖。
3. 存档里出现未知作物 id：该地块按空地处理，仓库里的未知作物丢弃，不能崩溃。由任务 7 的 `test_unknown_crop_is_dropped` 覆盖。
4. 保存时磁盘错误或文件被占用：界面继续运行并在状态栏提示，不能崩溃或阻止关闭。由任务 11 的 `test_save_failure_does_not_crash` 覆盖。
5. 点击浇水按钮时不能同时触发地块的种植/收获：浇水是独立控件，不冒泡到地块点击。由任务 9 的 `test_water_click_does_not_plant_or_harvest` 覆盖。

## 执行前准备

- 从 `main` 建分支 `feat/farmer-game`：`git switch -c feat/farmer-game main`。
- 先提交设计文档和本计划，再开始任务 1：

```bash
git add farmer/docs/superpowers/specs/2026-11-11-farmer-game-design.md farmer/docs/superpowers/plans/2026-11-11-farmer-game.md
git commit -m "docs: 添加小菜园设计与实现计划" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### 任务 1：核心数据模型与作物表

**文件：**
- 创建：`farmer/farm_core.py`
- 测试：`farmer/test_farm.py`

**接口：** `CROPS: Dict[str, Crop]`、`LAND_PRICES: Tuple[int, ...]`、`Plot`、`FarmState`，以及常量 `MAX_PLOTS=8`、`INITIAL_PLOTS=4`、`INITIAL_COINS=60`、`WATER_RATIO=0.10`、`WATER_MAX=3`、`WATER_COOLDOWN=600`。

- [ ] **步骤 1：编写失败的测试**

```python
# farmer/test_farm.py
import unittest

from farm_core import (
    CROPS, INITIAL_COINS, INITIAL_PLOTS, LAND_PRICES, MAX_PLOTS, FarmState,
)


class InitialStateTests(unittest.TestCase):
    def test_initial_state(self):
        state = FarmState()
        self.assertEqual(state.coins, 60)
        self.assertEqual(state.unlocked_plots, 4)
        self.assertEqual(len(state.plots), 8)
        self.assertTrue(all(p is None for p in state.plots))
        self.assertEqual(state.warehouse, {})
        self.assertEqual(state.total_harvests, 0)
        self.assertEqual(state.total_income, 0)
        self.assertEqual(state.selected_crop, "xiaobaicai")

    def test_crop_table_matches_design(self):
        expected = {
            "xiaobaicai": ("小白菜", 1800, 10, 25),
            "huluobo": ("胡萝卜", 3600, 25, 65),
            "fanqie": ("番茄", 7200, 45, 135),
            "yumi": ("玉米", 14400, 80, 260),
            "nangua": ("南瓜", 28800, 140, 480),
        }
        for crop_id, values in expected.items():
            crop = CROPS[crop_id]
            self.assertEqual(
                (crop.name, crop.grow_seconds, crop.seed_price, crop.sell_price),
                values,
            )
        self.assertEqual(LAND_PRICES, (200, 500, 1000, 1800))
        self.assertEqual((MAX_PLOTS, INITIAL_PLOTS, INITIAL_COINS), (8, 4, 60))
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd farmer && python -m unittest test_farm -v`  
预期：FAIL，`ModuleNotFoundError: No module named 'farm_core'`

- [ ] **步骤 3：实现 `farmer/farm_core.py` 的基础结构**

定义以下内容，函数体留空或按最小实现：

```python
from dataclasses import dataclass, field
from pathlib import Path
import json
import os
import time
from typing import Dict, List, Optional, Tuple, Union

MAX_PLOTS = 8
INITIAL_PLOTS = 4
INITIAL_COINS = 60
LAND_PRICES = (200, 500, 1000, 1800)
WATER_RATIO = 0.10
WATER_MAX = 3
WATER_COOLDOWN = 10 * 60

@dataclass(frozen=True)
class Crop:
    crop_id: str
    name: str
    grow_seconds: int
    seed_price: int
    sell_price: int
    leaf_color: str
    fruit_color: str

CROPS: Dict[str, Crop] = {
    "xiaobaicai": Crop("xiaobaicai", "小白菜", 30 * 60, 10, 25, "#4F9D4F", "#8BD17C"),
    "huluobo":    Crop("huluobo", "胡萝卜", 60 * 60, 25, 65, "#4F9D4F", "#E07B39"),
    "fanqie":     Crop("fanqie", "番茄", 120 * 60, 45, 135, "#3F8F3F", "#E04A3F"),
    "yumi":       Crop("yumi", "玉米", 240 * 60, 80, 260, "#5A9E3A", "#F2C94C"),
    "nangua":     Crop("nangua", "南瓜", 480 * 60, 140, 480, "#4A8F3A", "#E8912D"),
}

@dataclass
class Plot:
    crop_id: str
    planted_at: float
    water_count: int = 0
    last_water_at: float = 0.0

@dataclass
class FarmState:
    coins: int = INITIAL_COINS
    unlocked_plots: int = INITIAL_PLOTS
    selected_crop: str = "xiaobaicai"
    total_harvests: int = 0
    total_income: int = 0
    warehouse: Dict[str, int] = field(default_factory=dict)
    plots: List[Optional[Plot]] = field(default_factory=lambda: [None] * MAX_PLOTS)
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd farmer && python -m unittest test_farm -v`  
预期：PASS（2 个测试）

- [ ] **步骤 5：Commit**

```bash
git add farmer/farm_core.py farmer/test_farm.py
git commit -m "feat: 添加小菜园核心状态与作物表" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### 任务 2：种植与生长计算

**文件：**
- 修改：`farmer/farm_core.py`
- 测试：`farmer/test_farm.py`

**接口：** `FarmState.plant(index, crop_id, now) -> None`、`remaining_seconds(index, now) -> float`、`progress(index, now) -> float`、`is_mature(index, now) -> bool`。

- [ ] **步骤 1：编写失败的测试**

```python
class PlantAndGrowthTests(unittest.TestCase):
    def setUp(self):
        self.state = FarmState()
        self.t0 = 1_700_000_000.0

    def test_plant_deducts_coins_and_records_plot(self):
        self.state.plant(0, "xiaobaicai", self.t0)
        self.assertEqual(self.state.coins, 50)
        self.assertEqual(self.state.plots[0].crop_id, "xiaobaicai")
        self.assertEqual(self.state.plots[0].planted_at, self.t0)

    def test_plant_rejects_occupied_plot(self):
        self.state.plant(0, "xiaobaicai", self.t0)
        with self.assertRaisesRegex(ValueError, "已经有作物"):
            self.state.plant(0, "huluobo", self.t0)

    def test_plant_rejects_locked_plot(self):
        with self.assertRaisesRegex(ValueError, "还没开垦"):
            self.state.plant(4, "xiaobaicai", self.t0)

    def test_plant_rejects_unknown_crop(self):
        with self.assertRaisesRegex(ValueError, "未知作物"):
            self.state.plant(0, "unknown", self.t0)

    def test_plant_rejects_insufficient_coins(self):
        state = FarmState(coins=5)
        with self.assertRaisesRegex(ValueError, "金币不够"):
            state.plant(0, "xiaobaicai", self.t0)

    def test_progress_halfway(self):
        self.state.plant(0, "xiaobaicai", self.t0)
        self.assertAlmostEqual(self.state.progress(0, self.t0 + 900), 0.5)
        self.assertAlmostEqual(self.state.remaining_seconds(0, self.t0 + 900), 900)

    def test_progress_clamps_and_matures(self):
        self.state.plant(0, "xiaobaicai", self.t0)
        self.assertEqual(self.state.progress(0, self.t0 + 99999), 1.0)
        self.assertEqual(self.state.remaining_seconds(0, self.t0 + 99999), 0.0)
        self.assertTrue(self.state.is_mature(0, self.t0 + 1800))
        self.assertFalse(self.state.is_mature(0, self.t0 + 1799))

    def test_clock_rollback_counts_zero_elapsed(self):
        self.state.plant(0, "xiaobaicai", self.t0)
        self.assertEqual(self.state.progress(0, self.t0 - 3600), 0.0)
        self.assertAlmostEqual(self.state.remaining_seconds(0, self.t0 - 3600), 1800)
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd farmer && python -m unittest test_farm -v`  
预期：FAIL，`AttributeError: 'FarmState' object has no attribute 'plant'`

- [ ] **步骤 3：实现种植与生长方法**

在 `FarmState` 中实现：

- `_require_index(index)`：索引不在 `0..MAX_PLOTS-1` 时抛 `ValueError("地块不存在")`。
- `plant`：依次校验索引、已开垦（`index < unlocked_plots`）、空地、作物 id、金币，然后扣种子价并写入 `Plot(crop_id, now)`。
- `saved_seconds(plot)`：返回 `plot.water_count * CROPS[plot.crop_id].grow_seconds * WATER_RATIO`。
- `elapsed(plot, now)`：返回 `max(0.0, now - plot.planted_at) + saved_seconds(plot)`。
- `remaining_seconds`：空地返回 `0.0`；否则 `max(0.0, grow_seconds - elapsed)`。
- `progress`：空地返回 `0.0`；否则 `min(1.0, elapsed / grow_seconds)`。
- `is_mature`：`remaining_seconds(...) == 0.0` 且该地块有作物。

错误文案必须与测试一致：`"这块地已经有作物了"`、`"这块地还没开垦"`、`"未知作物"`、`"金币不够"`。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd farmer && python -m unittest test_farm -v`  
预期：PASS（10 个测试）

- [ ] **步骤 5：Commit**

```bash
git add farmer/farm_core.py farmer/test_farm.py
git commit -m "feat: 实现种菜与真实时间生长" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### 任务 3：浇水

**文件：**
- 修改：`farmer/farm_core.py`
- 测试：`farmer/test_farm.py`

**接口：** `FarmState.water(index, now) -> None`、`FarmState.can_water(index, now) -> bool`。

- [ ] **步骤 1：编写失败的测试**

```python
class WateringTests(unittest.TestCase):
    def setUp(self):
        self.state = FarmState()
        self.state.coins = 1000
        self.t0 = 1_700_000_000.0
        self.state.plant(0, "xiaobaicai", self.t0)   # 1800 秒

    def test_water_reduces_remaining_by_ten_percent_of_total(self):
        self.state.water(0, self.t0 + 60)
        self.assertAlmostEqual(
            self.state.remaining_seconds(0, self.t0 + 60), 1800 - 60 - 180
        )
        self.assertEqual(self.state.plots[0].water_count, 1)

    def test_water_has_ten_minute_cooldown(self):
        self.state.water(0, self.t0 + 60)
        with self.assertRaisesRegex(ValueError, "冷却"):
            self.state.water(0, self.t0 + 659)
        self.state.water(0, self.t0 + 660)  # 冷却刚好结束

    def test_water_limited_to_three_times(self):
        long_state = FarmState(coins=1000)
        long_state.plant(0, "nangua", self.t0)
        for offset in (0, 600, 1200):
            long_state.water(0, self.t0 + offset)
        with self.assertRaisesRegex(ValueError, "3 次"):
            long_state.water(0, self.t0 + 1800)

    def test_water_rejects_empty_plot(self):
        with self.assertRaisesRegex(ValueError, "没有作物"):
            self.state.water(3, self.t0)

    def test_water_rejects_mature_crop(self):
        with self.assertRaisesRegex(ValueError, "已经成熟"):
            self.state.water(0, self.t0 + 1800)

    def test_can_water_reflects_cooldown(self):
        self.assertTrue(self.state.can_water(0, self.t0))
        self.state.water(0, self.t0)
        self.assertFalse(self.state.can_water(0, self.t0 + 599))
        self.assertTrue(self.state.can_water(0, self.t0 + 600))
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd farmer && python -m unittest test_farm -v`  
预期：FAIL，`AttributeError: 'FarmState' object has no attribute 'water'`

- [ ] **步骤 3：实现浇水**

- `water`：校验有作物、未成熟、`water_count < WATER_MAX`、`now - last_water_at >= WATER_COOLDOWN`；通过后 `water_count += 1`、`last_water_at = now`。
- `can_water`：同样的条件返回布尔值，不抛异常。
- 错误文案：`"这块地没有作物"`、`"作物已经成熟"`、`"已经浇过 3 次水了"`、`"浇水冷却中"`。
- 每次浇水节省的时间由任务 2 的 `saved_seconds` 自动计算，不需要改生长公式。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd farmer && python -m unittest test_farm -v`  
预期：PASS（16 个测试）

- [ ] **步骤 5：Commit**

```bash
git add farmer/farm_core.py farmer/test_farm.py
git commit -m "feat: 添加浇水加速与冷却限制" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### 任务 4：收获与仓库

**文件：**
- 修改：`farmer/farm_core.py`
- 测试：`farmer/test_farm.py`

**接口：** `FarmState.harvest(index, now) -> str`、`FarmState.harvest_all(now) -> int`；仓库为 `Dict[str, int]`。

- [ ] **步骤 1：编写失败的测试**

```python
class HarvestTests(unittest.TestCase):
    def setUp(self):
        self.state = FarmState()
        self.state.coins = 1000
        self.t0 = 1_700_000_000.0

    def test_harvest_rejects_unripe_crop(self):
        self.state.plant(0, "xiaobaicai", self.t0)
        with self.assertRaisesRegex(ValueError, "还没成熟"):
            self.state.harvest(0, self.t0 + 10)

    def test_harvest_puts_crop_in_warehouse_and_clears_plot(self):
        self.state.plant(0, "xiaobaicai", self.t0)
        coins_before = self.state.coins
        crop_id = self.state.harvest(0, self.t0 + 1800)
        self.assertEqual(crop_id, "xiaobaicai")
        self.assertEqual(self.state.warehouse, {"xiaobaicai": 1})
        self.assertIsNone(self.state.plots[0])
        self.assertEqual(self.state.coins, coins_before)
        self.assertEqual(self.state.total_harvests, 1)
        self.assertEqual(self.state.total_income, 0)

    def test_harvest_all_counts_only_ripe_crops(self):
        self.state.plant(0, "xiaobaicai", self.t0)
        self.state.plant(1, "xiaobaicai", self.t0)
        self.state.plant(2, "huluobo", self.t0)
        harvested = self.state.harvest_all(self.t0 + 1800)
        self.assertEqual(harvested, 2)
        self.assertEqual(self.state.warehouse, {"xiaobaicai": 2})
        self.assertIsNotNone(self.state.plots[2])
        self.assertEqual(self.state.harvest_all(self.t0 + 1800), 0)
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd farmer && python -m unittest test_farm -v`  
预期：FAIL，`AttributeError: 'FarmState' object has no attribute 'harvest'`

- [ ] **步骤 3：实现收获**

- `harvest`：校验地块有作物且已成熟，否则抛 `ValueError`；把对应作物数量加进 `warehouse`，清空地块，`total_harvests += 1`，返回作物 id。未成熟文案 `"还没成熟"`。
- `harvest_all`：遍历所有地块，对成熟地块执行收获，返回收获份数；不抛异常。
- 收获不加金币，也不改 `total_income`。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd farmer && python -m unittest test_farm -v`  
预期：PASS（19 个测试）

- [ ] **步骤 5：Commit**

```bash
git add farmer/farm_core.py farmer/test_farm.py
git commit -m "feat: 实现收获入仓库" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### 任务 5：卖出与统计

**文件：**
- 修改：`farmer/farm_core.py`
- 测试：`farmer/test_farm.py`

**接口：** `FarmState.sell(crop_id) -> int`、`FarmState.sell_all() -> int`、`FarmState.warehouse_value() -> int`。

- [ ] **步骤 1：编写失败的测试**

```python
class SellingTests(unittest.TestCase):
    def setUp(self):
        self.state = FarmState()
        self.state.warehouse = {"xiaobaicai": 3, "fanqie": 1}

    def test_sell_returns_value_and_clears_that_crop(self):
        amount = self.state.sell("xiaobaicai")
        self.assertEqual(amount, 75)
        self.assertEqual(self.state.coins, 60 + 75)
        self.assertEqual(self.state.total_income, 75)
        self.assertEqual(self.state.warehouse, {"fanqie": 1})

    def test_sell_empty_or_unknown_returns_zero(self):
        self.assertEqual(self.state.sell("yumi"), 0)
        self.assertEqual(self.state.sell("unknown"), 0)
        self.assertEqual(self.state.coins, 60)

    def test_sell_all_sums_known_crops_and_clears(self):
        self.assertEqual(self.state.warehouse_value(), 75 + 135)
        amount = self.state.sell_all()
        self.assertEqual(amount, 210)
        self.assertEqual(self.state.coins, 270)
        self.assertEqual(self.state.total_income, 210)
        self.assertEqual(self.state.warehouse, {})
        self.assertEqual(self.state.sell_all(), 0)
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd farmer && python -m unittest test_farm -v`  
预期：FAIL，`AttributeError: 'FarmState' object has no attribute 'sell'`

- [ ] **步骤 3：实现卖出**

- `sell`：取库存数量；为 0 或作物未知时返回 0；否则 `amount = count * sell_price`，`coins += amount`，`total_income += amount`，库存清零，返回 `amount`。
- `sell_all`：按 `CROPS` 顺序累加所有库存价值，一次加金币并清空仓库，返回总额。
- `warehouse_value`：只计算已知作物，未知键忽略。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd farmer && python -m unittest test_farm -v`  
预期：PASS（22 个测试）

- [ ] **步骤 5：Commit**

```bash
git add farmer/farm_core.py farmer/test_farm.py
git commit -m "feat: 实现仓库卖出与收入统计" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### 任务 6：开垦新地

**文件：**
- 修改：`farmer/farm_core.py`
- 测试：`farmer/test_farm.py`

**接口：** `FarmState.buy_land() -> int`，返回开垦后的土地数量。

- [ ] **步骤 1：编写失败的测试**

```python
class LandTests(unittest.TestCase):
    def test_buy_land_deducts_price_and_unlocks_next(self):
        state = FarmState(coins=1000)
        self.assertEqual(state.buy_land(), 5)
        self.assertEqual(state.coins, 800)
        self.assertEqual(state.buy_land(), 6)
        self.assertEqual(state.coins, 300)

    def test_buy_land_rejects_insufficient_coins(self):
        state = FarmState(coins=199)
        with self.assertRaisesRegex(ValueError, "金币不够"):
            state.buy_land()

    def test_buy_land_stops_at_eight(self):
        state = FarmState(coins=100000)
        for expected in (5, 6, 7, 8):
            self.assertEqual(state.buy_land(), expected)
        with self.assertRaisesRegex(ValueError, "全部开垦"):
            state.buy_land()
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd farmer && python -m unittest test_farm -v`  
预期：FAIL，`AttributeError: 'FarmState' object has no attribute 'buy_land'`

- [ ] **步骤 3：实现开垦**

- `unlocked_plots >= MAX_PLOTS` 时抛 `ValueError("土地已经全部开垦")`。
- 价格取 `LAND_PRICES[unlocked_plots - INITIAL_PLOTS]`。
- 金币不足抛 `ValueError("金币不够")`；否则扣钱、`unlocked_plots += 1`、返回新数量。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd farmer && python -m unittest test_farm -v`  
预期：PASS（25 个测试）

- [ ] **步骤 5：Commit**

```bash
git add farmer/farm_core.py farmer/test_farm.py
git commit -m "feat: 实现金币开垦新地" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### 任务 7：存档读写与容错

**文件：**
- 修改：`farmer/farm_core.py`
- 测试：`farmer/test_farm.py`

**接口：** `FarmState.to_dict() -> dict`、`FarmState.from_dict(data) -> FarmState`（类方法）、`save_state(state, path) -> None`、`load_state(path) -> Tuple[FarmState, Optional[str]]`。

- [ ] **步骤 1：编写失败的测试**

```python
import json
import tempfile
from pathlib import Path

from farm_core import Plot, load_state, save_state


class SaveLoadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "save.json"
        self.t0 = 1_700_000_000.0

    def tearDown(self):
        self.tmp.cleanup()

    def test_roundtrip_preserves_state(self):
        state = FarmState()
        state.plant(0, "fanqie", self.t0)
        state.water(0, self.t0 + 60)
        state.plots[1] = Plot("xiaobaicai", self.t0 + 10)
        state.coins = 123
        state.total_harvests = 7
        state.total_income = 456
        state.warehouse = {"fanqie": 3}
        save_state(state, self.path)
        loaded, warning = load_state(self.path)
        self.assertIsNone(warning)
        self.assertEqual(loaded.coins, 123)
        self.assertEqual(loaded.total_harvests, 7)
        self.assertEqual(loaded.total_income, 456)
        self.assertEqual(loaded.warehouse, {"fanqie": 3})
        self.assertEqual(loaded.plots[0].crop_id, "fanqie")
        self.assertEqual(loaded.plots[0].water_count, 1)
        self.assertEqual(loaded.plots[1].crop_id, "xiaobaicai")
        self.assertIsNone(loaded.plots[2])

    def test_offline_growth_uses_real_timestamps(self):
        state = FarmState()
        state.plant(0, "xiaobaicai", self.t0)
        save_state(state, self.path)
        loaded, _ = load_state(self.path)
        self.assertTrue(loaded.is_mature(0, self.t0 + 3600))

    def test_missing_file_starts_new_game(self):
        loaded, warning = load_state(self.path)
        self.assertIsNone(warning)
        self.assertEqual(loaded.coins, 60)
        self.assertEqual(loaded.unlocked_plots, 4)

    def test_corrupt_json_is_backed_up(self):
        self.path.write_text("{not json", encoding="utf-8")
        loaded, warning = load_state(self.path)
        self.assertEqual(warning, "存档损坏，已开始新的一局")
        self.assertEqual(loaded.coins, 60)
        self.assertTrue(list(Path(self.tmp.name).glob("save.corrupt-*.json")))

    def test_load_invalid_types_resets(self):
        self.path.write_text(
            json.dumps({"coins": "many", "unlocked_plots": 4, "plots": [None] * 8}),
            encoding="utf-8",
        )
        loaded, warning = load_state(self.path)
        self.assertEqual(warning, "存档损坏，已开始新的一局")
        self.assertEqual(loaded.coins, 60)

    def test_missing_optional_fields_use_defaults(self):
        self.path.write_text(
            json.dumps({"coins": 100, "unlocked_plots": 4, "plots": [None] * 8}),
            encoding="utf-8",
        )
        loaded, warning = load_state(self.path)
        self.assertIsNone(warning)
        self.assertEqual(loaded.coins, 100)
        self.assertEqual(loaded.warehouse, {})
        self.assertEqual(loaded.total_harvests, 0)
        self.assertEqual(loaded.selected_crop, "xiaobaicai")

    def test_unknown_crop_is_dropped(self):
        self.path.write_text(
            json.dumps({
                "coins": 100,
                "unlocked_plots": 4,
                "plots": [{"crop": "unknown", "planted_at": 100.0}] + [None] * 7,
                "warehouse": {"unknown": 5, "fanqie": 2},
            }),
            encoding="utf-8",
        )
        loaded, warning = load_state(self.path)
        self.assertIsNone(warning)
        self.assertIsNone(loaded.plots[0])
        self.assertEqual(loaded.warehouse, {"fanqie": 2})
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd farmer && python -m unittest test_farm -v`  
预期：FAIL，`ImportError: cannot import name 'load_state'`

- [ ] **步骤 3：实现存档**

- `to_dict`：输出 `version: 1`、`coins`、`unlocked_plots`、`selected_crop`、`total_harvests`、`total_income`、`warehouse`、`plots`（长度 8，元素为 `None` 或 `{crop, planted_at, water_count, last_water_at}`）、`saved_at`（`time.time()`）。
- `from_dict`：严格校验：
  - 必须是 dict；
  - `coins` 必须是非负 int（`bool` 不算 int）；
  - `unlocked_plots` 必须是 `INITIAL_PLOTS..MAX_PLOTS` 的 int；
  - `plots` 必须是长度 8 的 list，元素为 `None` 或含合法 `crop`、`planted_at` 的 dict；
  - 不合法时抛 `ValueError`；
  - `warehouse` 缺失按 `{}`；必须是 dict，值必须是非负 int；未知作物键丢弃；
  - `selected_crop` 缺失或未知时用 `"xiaobaicai"`；统计字段缺失按 0，非法负数按 0；
  - 未知多余字段忽略；存档里的未知作物地块按 `None`。
- `save_state`：先写 `path.name + ".tmp"`，再用 `os.replace` 原子替换；`ensure_ascii=False`、`indent=2`；异常向上抛。
- `load_state`：文件不存在返回 `(FarmState(), None)`；解析或校验失败时把原文件重命名为 `save.corrupt-<int(time.time())>.json`（重命名失败也忽略），返回 `(FarmState(), "存档损坏，已开始新的一局")`。读文件本身的其它 `OSError`（被占用、权限不足）不得当作损坏：抛 `SaveUnreadableError`，由 GUI 进入本次不写盘模式，绝不覆盖原档。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd farmer && python -m unittest test_farm -v`  
预期：PASS（32 个测试）

- [ ] **步骤 5：Commit**

```bash
git add farmer/farm_core.py farmer/test_farm.py
git commit -m "feat: 添加存档读写与损坏恢复" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### 任务 8：主窗口与菜地渲染

**文件：**
- 创建：`farmer/farm_gui.py`
- 测试：`farmer/test_gui_smoke.py`

**接口：** `FarmApp(save_path=None, start_loops=True, clock=time.time)`、`PlotCard(master, index, on_click, on_water)`、`PlotCard.render(state, index, now)`、`PlotCard.texts() -> List[str]`、`FarmApp.refresh()`。

- [ ] **步骤 1：编写失败的测试**

```python
# farmer/test_gui_smoke.py
import tempfile
import unittest
from pathlib import Path

import farm_gui
from farm_core import CROPS


class GuiSkeletonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.save_path = Path(self.tmp.name) / "save.json"
        self.now = 1_700_000_000.0
        self.app = farm_gui.FarmApp(
            save_path=self.save_path,
            start_loops=False,
            clock=lambda: self.now,
        )
        self.app.update_idletasks()

    def tearDown(self):
        self.app.destroy()
        self.tmp.cleanup()

    def test_window_builds_eight_plot_cards(self):
        self.assertEqual(len(self.app.plot_cards), 8)
        self.assertEqual(self.app.title(), "小菜园")

    def test_unlocked_empty_plot_shows_empty_text(self):
        self.assertIn("空地", self.app.plot_cards[0].texts())

    def test_locked_plot_shows_locked_text(self):
        self.assertIn("未开垦", self.app.plot_cards[4].texts())

    def test_planted_plot_shows_crop_name_and_countdown(self):
        self.app.state.plant(0, "xiaobaicai", self.now)
        self.app.refresh()
        texts = self.app.plot_cards[0].texts()
        self.assertTrue(any("小白菜" in t for t in texts))
        self.assertTrue(any("还需" in t for t in texts))
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd farmer && python -m unittest test_gui_smoke -v`  
预期：FAIL，`ModuleNotFoundError: No module named 'farm_gui'`

- [ ] **步骤 3：实现窗口骨架与菜地卡片**

- `FarmApp.__init__`：设置标题“小菜园”、几何尺寸 `1260x680`；用 `load_state` 读取存档，警告文案稍后显示；构建顶栏占位、8 个 `PlotCard`（4 列 2 行）、种子栏占位、状态栏、右侧仓库面板占位；最后调用 `refresh()`。
- `start_loops=True` 时启动 `after(1000, ...)` 刷新循环和 `after(10000, ...)` 自动保存循环；`False` 时不启动，供测试使用。
- `PlotCard`：继承 `tk.Frame`，内部一个 `tk.Canvas`（约 200×120）和一个“浇水” `tk.Button`；Canvas 绑定 `<Button-1>` 调用 `on_click(index)`；按钮调用 `on_water(index)`。
- `PlotCard.render`：清空 Canvas 后按状态绘制：
  - 未开垦：灰色土块 + 文本“未开垦”；
  - 空地：棕色土块 + 文本“空地”；
  - 生长中：土块 + 茎叶/果实形状 + 作物名 + `还需 MM:SS`（超过 1 小时显示 `H:MM:SS`）+ 进度条；
  - 成熟：土块 + 饱满果实 + 作物名 + “可收获”，地块高亮描边。
- `PlotCard.texts()`：返回 Canvas 上所有 text item 的文本列表，供测试断言。
- 浇水按钮只在生长中且 `can_water` 为真时可用，否则 `state="disabled"`。
- `FarmApp.refresh()`：用 `clock()` 取当前时间，更新 8 张卡片的 `render`。
- 字体统一使用 `("Microsoft YaHei UI", 10)`；标题/作物名可用更大字号。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd farmer && python -m unittest test_gui_smoke -v`  
预期：PASS（4 个测试）

- [ ] **步骤 5：Commit**

```bash
git add farmer/farm_gui.py farmer/test_gui_smoke.py
git commit -m "feat: 添加小菜园主窗口与菜地渲染" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### 任务 9：种子栏、种植与浇水交互

**文件：**
- 修改：`farmer/farm_gui.py`
- 测试：`farmer/test_gui_smoke.py`

**接口：** `FarmApp.seed_buttons: Dict[str, tk.Button]`、`FarmApp._on_seed_click(crop_id)`、`FarmApp._on_plot_click(index)`、`FarmApp._on_water_click(index)`、`FarmApp.set_status(text, seconds=3)`、`FarmApp.status_var: tk.StringVar`。

- [ ] **步骤 1：编写失败的测试**

```python
class GuiInteractionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.save_path = Path(self.tmp.name) / "save.json"
        self.now = 1_700_000_000.0
        self.app = farm_gui.FarmApp(
            save_path=self.save_path,
            start_loops=False,
            clock=lambda: self.now,
        )
        self.app.update_idletasks()

    def tearDown(self):
        self.app.destroy()
        self.tmp.cleanup()

    def test_select_seed_updates_state_and_highlight(self):
        self.app._on_seed_click("huluobo")
        self.assertEqual(self.app.state.selected_crop, "huluobo")
        self.assertEqual(str(self.app.seed_buttons["huluobo"].cget("relief")), "sunken")

    def test_plot_click_plants_selected_seed(self):
        self.app._on_seed_click("huluobo")
        self.app._on_plot_click(0)
        self.assertEqual(self.app.state.plots[0].crop_id, "huluobo")
        self.assertEqual(self.app.state.coins, 35)
        self.assertIn("种下了胡萝卜", self.app.status_var.get())

    def test_plot_click_on_locked_plot_shows_message(self):
        self.app._on_plot_click(6)
        self.assertIn("还没开垦", self.app.status_var.get())
        self.assertIsNone(self.app.state.plots[6])

    def test_water_click_increases_water_count(self):
        self.app._on_plot_click(0)
        coins_after_plant = self.app.state.coins
        self.app._on_water_click(0)
        self.assertEqual(self.app.state.plots[0].water_count, 1)
        self.assertEqual(self.app.state.coins, coins_after_plant)
        self.assertIn("浇水", self.app.status_var.get())

    def test_water_click_does_not_plant_or_harvest(self):
        self.app._on_plot_click(0)
        plot_before = self.app.state.plots[0]
        coins_before = self.app.state.coins
        self.app._on_water_click(0)
        self.assertIs(self.app.state.plots[0], plot_before)
        self.assertEqual(self.app.state.coins, coins_before)
        self.assertEqual(self.app.state.warehouse, {})
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd farmer && python -m unittest test_gui_smoke -v`  
预期：FAIL，`AttributeError: 'FarmApp' object has no attribute '_on_seed_click'`

- [ ] **步骤 3：实现种子栏与交互**

- 种子栏用 5 个 `tk.Button`，显示 `${name} ${分钟/小时} / ${价格}`，例如 `小白菜 30分/10`；金币不足的按钮置灰但仍可点击。
- `_on_seed_click`：更新 `state.selected_crop`，刷新按钮高亮（选中项 `relief="sunken"`），状态栏提示 `已选择${name}`。
- `_on_plot_click`：
  - 未开垦 → 状态栏“这块地还没开垦”；
  - 空地 → `plant(index, selected_crop, clock())`，成功后状态栏 `种下了${name}`；
  - 成熟 → 调 `harvest`，状态栏 `收获了${name}`（仓库数量稍后由任务 10 展示）；
  - 生长中 → 状态栏显示 `还需 ...`。
  - 任何 `ValueError` 都只显示 `str(e)`，不弹窗。
- `_on_water_click`：调用 `state.water(index, clock())`，成功提示 `浇水成功，生长加快`，失败显示错误文案；不触发种植或收获。
- 每次成功操作后调用 `self._save()`（任务 11 实现；此任务可先定义一个只写文件的空壳方法）并 `refresh()`。
- `set_status`：设置 `status_var` 并取消上一次的恢复定时器，3 秒后恢复默认文案“选一种种子，点空地种下”。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd farmer && python -m unittest test_gui_smoke -v`  
预期：PASS（9 个测试）

- [ ] **步骤 5：Commit**

```bash
git add farmer/farm_gui.py farmer/test_gui_smoke.py
git commit -m "feat: 添加种子栏与种植浇水交互" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### 任务 10：收获、仓库、卖出、开垦与标题

**文件：**
- 修改：`farmer/farm_gui.py`
- 测试：`farmer/test_gui_smoke.py`

**接口：** `FarmApp._on_harvest_all_click()`、`FarmApp._on_sell_click(crop_id)`、`FarmApp._on_sell_all_click()`、`FarmApp._on_buy_land_click()`；属性 `warehouse_vars: Dict[str, tk.StringVar]`、`sell_buttons: Dict[str, tk.Button]`、`sell_all_button`、`harvest_all_button`、`land_button`。

- [ ] **步骤 1：编写失败的测试**

```python
class GuiEconomyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.save_path = Path(self.tmp.name) / "save.json"
        self.now = 1_700_000_000.0
        self.app = farm_gui.FarmApp(
            save_path=self.save_path,
            start_loops=False,
            clock=lambda: self.now,
        )
        self.app.update_idletasks()

    def tearDown(self):
        self.app.destroy()
        self.tmp.cleanup()

    def _plant_ripe(self, index=0, crop_id="xiaobaicai"):
        planted_at = self.now - CROPS[crop_id].grow_seconds - 1
        self.app.state.plant(index, crop_id, planted_at)
        self.app.refresh()

    def test_harvest_click_fills_warehouse(self):
        self._plant_ripe()
        coins_before = self.app.state.coins
        self.app._on_plot_click(0)
        self.assertEqual(self.app.state.warehouse, {"xiaobaicai": 1})
        self.assertEqual(self.app.state.coins, coins_before)
        self.assertIn("×1", self.app.warehouse_vars["xiaobaicai"].get())

    def test_sell_click_adds_coins_and_clears_row(self):
        self._plant_ripe()
        self.app._on_plot_click(0)
        self.app._on_sell_click("xiaobaicai")
        self.assertEqual(self.app.state.coins, 50 + 25)
        self.assertEqual(self.app.state.warehouse, {})
        self.assertIn("卖出小白菜", self.app.status_var.get())
        self.assertTrue(self.app.sell_buttons["xiaobaicai"].cget("state") == "disabled")

    def test_harvest_all_then_sell_all(self):
        self._plant_ripe(0, "xiaobaicai")
        self._plant_ripe(1, "fanqie")
        self.app._on_harvest_all_click()
        self.assertEqual(self.app.state.warehouse, {"xiaobaicai": 1, "fanqie": 1})
        self.assertIn("2", self.app.status_var.get())
        total_text = self.app.sell_all_button.cget("text")
        self.assertIn("160", total_text)
        self.app._on_sell_all_click()
        self.assertEqual(self.app.state.coins, 5 + 25 + 135)
        self.assertEqual(self.app.state.warehouse, {})

    def test_buy_land_click_unlocks_plot(self):
        self.app.state.coins = 300
        self.app.refresh()
        self.app._on_buy_land_click()
        self.assertEqual(self.app.state.unlocked_plots, 5)
        self.assertEqual(self.app.state.coins, 100)
        self.assertIn("第 5 块", self.app.status_var.get())
        self.assertIn("开垦 500", self.app.land_button.cget("text"))

    def test_title_shows_ripe_count(self):
        self._plant_ripe()
        self.app.refresh()
        self.assertEqual(self.app.title(), "小菜园（1 可收）")
        self.app._on_plot_click(0)
        self.app.refresh()
        self.assertEqual(self.app.title(), "小菜园")
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd farmer && python -m unittest test_gui_smoke -v`  
预期：FAIL，`AttributeError: 'FarmApp' object has no attribute 'warehouse_vars'`

- [ ] **步骤 3：实现经济循环界面**

- 顶栏：金币、累计收获、累计收入三个标签；开垦按钮文字 `开垦 ${price}`，8 块后改为 `已全部开垦` 并禁用。
- 右侧仓库面板：5 行，每行 `名称`、`×数量`、`单价`、`小计`、`卖出`按钮；`warehouse_vars[crop_id]` 的文本格式为 `×N`；库存为 0 时整行变淡、按钮禁用。
- 底部 `全部卖出（${total} 金币）`，总价为 0 时禁用。
- 种子栏旁放 `一键收获` 按钮；没有成熟作物时禁用。
- 回调：
  - `_on_harvest_all_click`：调 `harvest_all`，状态栏 `收获了 ${n} 份作物` 或 `没有可收获的作物`；
  - 收获成功后在地块上方显示约 1 秒的“+1 作物名”飘字；一键收获对每个实际收获的地块都显示；
  - `_on_sell_click`：调 `sell`，成功提示 `卖出${name}，+${amount} 金币`，库存为 0 时提示 `仓库里没有${name}`；
  - `_on_sell_all_click`：调 `sell_all`，提示 `全部卖出，+${amount} 金币`；
  - `_on_buy_land_click`：调 `buy_land`，提示 `已开垦第 ${n} 块地`，失败显示错误文案。
- 所有回调捕获 `ValueError`，只更新状态栏；成功后 `_save()` 并 `refresh()`。
- `refresh()` 额外更新：顶部三个标签、仓库各行与卖出按钮、全部卖出总价、一键收获按钮、开垦按钮、窗口标题（`小菜园（N 可收）`，N 为当前成熟地块数，0 时不加后缀）。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd farmer && python -m unittest test_gui_smoke -v`  
预期：PASS（14 个测试）

- [ ] **步骤 5：Commit**

```bash
git add farmer/farm_gui.py farmer/test_gui_smoke.py
git commit -m "feat: 添加仓库卖出、一键收获与开垦界面" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### 任务 11：自动保存、关闭保存、启动脚本与文档

**文件：**
- 修改：`farmer/farm_gui.py`
- 修改：`farmer/test_gui_smoke.py`
- 创建：`farmer/run_farmer.bat`
- 创建：`farmer/README.md`
- 创建：`farmer/.gitignore`

**接口：** `FarmApp._save() -> None`、`FarmApp._on_close() -> None`、`FarmApp._tick()`、`FarmApp._autosave()`；模块级 `main()`。

- [ ] **步骤 1：编写失败的测试**

```python
import tkinter as tk
from unittest import mock


class GuiPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.save_path = Path(self.tmp.name) / "save.json"
        self.now = 1_700_000_000.0
        self.app = farm_gui.FarmApp(
            save_path=self.save_path,
            start_loops=False,
            clock=lambda: self.now,
        )
        self.app.update_idletasks()

    def tearDown(self):
        try:
            self.app.destroy()
        except tk.TclError:
            pass
        self.tmp.cleanup()

    def test_close_saves_state(self):
        self.app._on_plot_click(0)
        self.app._on_close()
        self.assertTrue(self.save_path.exists())
        data = self.save_path.read_text(encoding="utf-8")
        self.assertIn("xiaobaicai", data)

    def test_save_failure_does_not_crash(self):
        with mock.patch.object(farm_gui, "save_state", side_effect=OSError("磁盘忙")):
            self.app._save()
        self.assertIn("保存失败", self.app.status_var.get())

    def test_app_starts_from_existing_save(self):
        self.app.state.coins = 777
        self.app._save()
        app2 = farm_gui.FarmApp(
            save_path=self.save_path,
            start_loops=False,
            clock=lambda: self.now,
        )
        try:
            self.assertEqual(app2.state.coins, 777)
        finally:
            app2.destroy()
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd farmer && python -m unittest test_gui_smoke -v`  
预期：FAIL，`test_save_failure_does_not_crash` 失败（异常未被捕获）

- [ ] **步骤 3：实现保存与启动**

- `_save`：调用 `save_state(self.state, self.save_path)`；捕获 `OSError`，状态栏显示 `保存失败：${e}`，不抛出。
- `_tick`：`refresh()`；若 `start_loops` 为真，`after(1000, self._tick)`；窗口销毁后停止。
- `_autosave`：`_save()`；若 `start_loops` 为真，`after(10000, self._autosave)`。
- `_on_close`：`_save()` 后 `destroy()`；保存失败也不能阻止关闭。
- 构造时若 `load_state` 返回警告，状态栏显示该警告。
- `main()`：尝试 `ctypes.windll.shcore.SetProcessDpiAwareness(1)`，失败忽略；创建 `FarmApp()` 并 `mainloop()`。
- `run_farmer.bat`：

```bat
@echo off
cd /d "%~dp0"
start "" pythonw farm_gui.py
```

- `.gitignore`：

```
__pycache__/
save.json
save.json.tmp
save.corrupt-*.json
```

- `README.md` 写清：玩法一句话、运行方式、五种作物表格、浇水规则、存档位置、测试命令。

- [ ] **步骤 4：运行测试验证通过**

运行：`cd farmer && python -m unittest test_gui_smoke -v`  
预期：PASS（17 个测试）  
运行：`cd farmer && python -m unittest test_farm -v`  
预期：PASS（32 个测试）

- [ ] **步骤 5：实际启动程序做人工验收**

运行：`cd farmer && python farm_gui.py`  
按规格第 13 节逐条走一遍“种下 → 等待/浇水 → 收获 → 卖出 → 开垦”，确认窗口标题、状态栏和右键仓库面板正常。

- [ ] **步骤 6：Commit**

```bash
git add farmer/farm_gui.py farmer/test_gui_smoke.py farmer/run_farmer.bat farmer/README.md farmer/.gitignore
git commit -m "feat: 完成自动保存、启动脚本与使用说明" -m "Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## 完成定义

- `python -m unittest test_farm -v` 全部通过。
- `python -m unittest test_gui_smoke -v` 全部通过。
- 实际启动 `python farm_gui.py`，完整走通“种下 → 浇水 → 收获 → 卖出 → 开垦”。
- 关掉程序一分钟再打开，进度按真实时间推进，仓库内容保留。
- 所有提交只涉及 `farmer/` 目录。
