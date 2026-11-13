# 勇士冒险 GUI 窗口界面实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 subagent-driven-development（推荐）或 executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 给已完成的终端 roguelike 加一层纯鼠标 Tkinter 界面：点卡牌、点敌人、点按钮完成整局，键盘零操作；规则内核零改动。

**架构：** 新增 `gui.py`（单类 `WarriorGUI`，容器重建式换屏，每屏一组按钮回调直接调 core 公开接口）；`main.py` 分流（默认 GUI，`--text` 走现有终端会话）；`test_gui.py` 双层测试：无显示依赖的回调级单测 + farmer 验证过的子进程真实 DPI 布局回归。

**技术栈：** Python 3.8.3 标准库（tkinter/ttk、ctypes、subprocess、unittest）。

**规格：** `warrior/docs/superpowers/specs/2026-11-13-warrior-gui-design.md`（另参照终端版规格与既有代码 core.py/ui.py/records.py；执行者两份都读）

## 全局约束

- Python 3.8 兼容、仅标准库；不引图片/字体/第三方。
- `core.py`/`content.py`/`records.py` 规则零改动；`gui.py` 不实现任何游戏规则，一切状态来自 `combat.snapshot()` / Run 公开方法。
- 视觉朴素：ttk 原生控件 + Canvas 矩形血条；无动画、无自绘主题。
- 窗口 1000×660、`minsize(900, 620)`；文本全中文；按钮文本用 `wraplength` 换行不截断。
- DPI 纪律（规格 5 节，逐条）：GUI 路径先 `gui._enable_dpi_awareness()` 再建 `Tk()`；布局回归必须在子进程内先设同一 DPI；中文控件自然宽度；子控件宽度断言逐项；Canvas 文字正边距。
- 战绩语义不变：win/dead 计入，中退(aborted/X 关闭)不写盘。
- 测试在 `warrior/` 运行；`test_gui.py` 全部用例在无 Tk/无显示环境 skip。
- `test_gui.py` 走图辅助直接复用：`from test_run import find_node, force_node, win_and_collect, to_shop`（这些已在终端版测试中实现并稳定）。
- 每任务 commit，消息 `feat(warrior): gui …`。

## 审查重点（Review Focus）

- **战斗已结束瞬间再点牌/敌人按钮**（双击竞态）：应无动作无异常，界面停在本步结果——任务 2 `test_click_after_combat_over_ignored` 钉住。
- **真实 DPI(×2.33) 下 12 张手牌、3 敌人、长日志同屏**：不得横向溢出窗口、不得裁字——任务 7 子进程回归钉住。
- **战绩文件被占用（io_error）**：结算屏不弹窗崩溃，显示"写入失败（原文件未破坏）"——任务 6 `test_on_finish_io_error_hint` 钉住。
- **"再来一局"必须换新种子**：不得静默复用上一局种子（修掉终端版已知 Minor）——任务 6 `test_replay_uses_new_seed` 钉住。
- **战斗中途按窗口 X 关闭**：干净退出、不写战绩、无 traceback——任务 6 `test_close_midrun_no_record` 钉住。

---

## 文件结构

| 文件 | 职责 | 任务 |
|---|---|---|
| `warrior/gui.py`（新） | WarriorGUI 全部窗口逻辑 + `_enable_dpi_awareness()` + `_flow_layout()` 辅助 | 1~6 |
| `warrior/test_gui.py`（新） | 回调级单测 + 子进程 DPI 回归 | 1~7 |
| `warrior/main.py`（改） | `run_mode(argv)`、GUI 启动、`apply_result_to_records` 复用、终端路径不动 | 1、6 |

`gui.py` 钉死的公开接口（后续任务一致引用）：

```python
def _enable_dpi_awareness(): ...          # shcore(1)→user32 回退，各自 try/except
def _flow_layout(container, widgets, max_width): ...
    # 自然宽度流式排布：按行排入 grid，返回行号列表；先 update_idletasks 量宽

class WarriorGUI:
    WINDOW_W = 1000; WINDOW_H = 660
    def __init__(self, root, on_finish=None):
        # on_finish(result: dict) -> 'ok'|'io_error'|None；win/dead 时恰好调用一次
    def run(self): ...                    # mainloop（测试不调）
    def show_title(self): ...
    def start_run(self, seed): ...        # 建 core.Run、清屏、show_map
    def show_map(self): ...
    def show_screen(self): ...            # 按当前节点态分发：战斗/奖励/火堆/事件/商店/宝箱/结算
    def show_combat(self): ...
    def show_campfire(self): ...
    def show_event(self): ...
    def show_shop(self): ...
    def show_chest(self): ...
    def show_rewards(self): ...
    def show_end(self): ...
    # 测试可见属性：self.game(core.Run)、self.hand_buttons、self.enemy_buttons、
    # self.cancel_btn、self.log_text、self.status_var(StringVar)、self.root、
    # self._pending_card(选目标态的牌位或 None)、self._pending_potion(药水槽或 None)
```

节点分发规则（`show_screen`，任务 1 定、后续复用）：`game.finished→show_end`；`game.pending→show_rewards`；`game.active→show_combat`；否则按当前节点 kind：campfire/event/shop/chest；`node_done 或 current None→show_map`。

## 任务

### 任务 1：骨架——标题屏、地图屏、状态栏、main 分流与 DPI 开关

**文件：** 创建 `gui.py`、`test_gui.py`；修改 `main.py`

- [ ] **步骤 1：编写失败的测试**（`test_gui.py`，模块级 `TK_OK = tkinter 可建根窗口`，全部 `@unittest.skipUnless(TK_OK, ...)`；辅助 `make_app(seed)`：建隐藏根 + WarriorGUI + `start_run(seed)`，不调 mainloop）

```python
def test_title_then_start_shows_map(self):
    # show_title() 后有“开始”按钮与种子 Entry；Entry 填 '7' 点击开始
    # → app.game 是 core.Run 且 app.game.seed==7；地图屏入口节点按钮 == len(entry_ids)，state==NORMAL
def test_map_disabled_nodes(self):
    # 地图屏上：不在 game.choices() 的节点按钮 state==DISABLED；visited 的也是
def test_run_mode_dispatch(self):
    # main.run_mode(['--text'])=='text'; main.run_mode([])== 'gui'
def test_status_bar_shows_core_state(self):
    # start_run 后 status_var 含 '生命 80/80' 与 '金币 0'
```

- [ ] **步骤 2：运行验证失败**：`python -m unittest test_gui -v` → FAIL（无 gui 模块）
- [ ] **步骤 3：实现** `_enable_dpi_awareness`（ctypes.windll.shcore.SetProcessDpiAwareness(1)，AttributeError 回退 user32.SetProcessDPIAware，全程 try/except）、`_flow_layout`、WarriorGUI 骨架（单一容器 Frame，每次换屏 destroy+重建）、标题/地图/状态栏、`show_screen` 分发；`main.py`：抽 `apply_result_to_records(result, path)`（现有 session 里的更新+保存逻辑挪来共用），`run_mode(argv)`，GUI 分支：`_enable_dpi_awareness()` → `Tk()` → `WarriorGUI(root, on_finish=...).run()`。地图按钮文本：`'%s·%s' % (图例字, KIND_NAME[kind])`，visited 前缀 `✓`，current 前缀 `▶`。
- [ ] **步骤 4：运行验证通过**：`python -m unittest test_gui -v` → PASS；`python -m unittest discover` 全套仍绿
- [ ] **步骤 5：Commit**：`feat(warrior): gui 骨架与标题/地图屏`

### 任务 2：战斗屏——渲染、直接出牌、结束回合、日志

**文件：** 修改 `gui.py`、`test_gui.py`

- [ ] **步骤 1：编写失败的测试**（辅助 `to_first_combat(app)`：`app.game.go(entry_id)` + `enter()` 后 `show_screen()`）

```python
def test_combat_widgets_render(self):
    # 手牌按钮数==len(game.active.hand)；snapshot 不可打出的牌 state==DISABLED；
    # 敌人按钮文本含 '意图'；log_text 含“遭遇”
def test_click_card_plays(self):
    # 记下 snapshot 敌人 hp；force 一张可打 strike 的按钮 invoke()
    # → 敌人 hp 少 6（goblin 场景）、能量 -1、log 含“打击”
def test_end_turn_button(self):  # invoke 后 game.active.turn 增加且手牌重抽 5 张
def test_click_after_combat_over_ignored(self):
    # 把 enemies 全置 hp=0 并 status='win' 后 invoke 手牌按钮 → 无异常、hp 不变
def test_win_click_lands_on_rewards(self):
    # kill 最后一击后 show_screen 落在奖励屏（pending 非 None）
```

- [ ] **步骤 2：运行验证失败**
- [ ] **步骤 3：实现 `show_combat`**：敌人一排按钮（文本 `名\nHP a/b 意图…`，血条 Canvas 在按钮下方另排一行），手牌 `_flow_layout`（按钮文本两行：`名(费)` / 效果 text，`wraplength=170`），动作行按钮：`结束回合`、每瓶药水一枚、`详情`（弹窗 Toplevel 列遗物/卡组，朴素文本即可）；日志 `ScrolledText height=7`，`_log(lines)` 追加并 see(end)。回调 `_on_card(idx)`：本任务先走"无需目标直接打"分支 + 存 `self._pending_card=None`（任务 3 补选目标）。出牌/回合结束一律：调 core → `_log` → `game.combat_finished()`（若 status 变化）→ `show_screen()`。
- [ ] **步骤 4：运行验证通过**
- [ ] **步骤 5：Commit**：`feat(warrior): gui 战斗屏直接出牌与日志`

### 任务 3：目标选择——单体牌/药水、取消、高亮

**文件：** 修改 `gui.py`、`test_gui.py`

- [ ] **步骤 1：编写失败的测试**（用 `app.game.active` 手动布双敌 `start_event_combat(['goblin','wolf'])`）

```python
def test_single_target_card_enters_targeting(self):
    # invoke strike 按钮（双敌）→ app._pending_card 非 None、app.cancel_btn visible、
    # 敌人按钮 relief 变化（用 bg/cget 判定，实现自选其一）
def test_target_click_hits_only_chosen(self):  # 点敌人按钮2 → 只有 2 号掉血；_pending_card 归 None
def test_cancel_returns_to_plain(self):        # 点 cancel → 无任何伤害、按钮恢复
def test_reclick_same_card_cancels(self):      # 再点同一张牌=取消
def test_aoe_no_target_needed(self):           # cleave 双敌：invoke 直接全掉血，不进选目标态
def test_potion_targeted_uses_targeting(self): # p_acid 双敌：药水按钮→选目标→敌人掉 12
```

- [ ] **步骤 2：运行验证失败**
- [ ] **步骤 3：实现** `needs_target(effects)`：effects 含 `damage/pierce/execute/vulnerable/poison/bonus_if_vulnerable` 任一 **且** alive 敌人数 >1 → True（`damage_all/vulnerable_all/poison_all` 不算单体）。`_on_card`：先判 needs_target→设 `_pending_card`；`_on_enemy(i)`：有 pending 牌则 `play_card(pending, i)`，有 pending 药水则 `use_potion(slot, i)`，否则无操作。所有出牌路径完成后统一走 `show_screen()`（自然重算高亮）。
- [ ] **步骤 4：运行验证通过**
- [ ] **步骤 5：Commit**：`feat(warrior): gui 目标选择与取消`

### 任务 4：火堆、事件、宝箱、奖励四屏

**文件：** 修改 `gui.py`、`test_gui.py`

- [ ] **步骤 1：编写失败的测试**

```python
def test_campfire_buttons_state(self):
    # 满血：sleep 按钮 DISABLED；点击 sharpen → game.hero.weapon_sharpen==1 且已回到地图屏
def test_campfire_forge_grid(self):
    # 点“锻造”→ 出现卡组按钮；点 strike 那张 → deck 出现 ('strike',True)
def test_event_option_disabled_and_apply(self):
    # gambler 事件 gold=0：押注按钮 DISABLED；点“不赌”→ node_done、回地图
def test_event_followup_opens_combat(self):   # mimic 事件选“识破”→ show_combat 出现
def test_chest_take_or_leave(self):
    # 装备 → hero.weapon 变；只拿金币分支 weapon 不变、gold 增加
def test_rewards_take_and_skip(self):
    # 三张牌按钮点第 2 张 → deck+1；skip 按钮 → pending None 回地图
def test_rewards_relic_choice(self):          # relic_choices 按钮 → hero.relics 增加
```

- [ ] **步骤 2：运行验证失败**
- [ ] **步骤 3：实现四屏**（全部复用任务 1 的 `show_screen` 分发与各 show_*；文本区 Label + wraplength，按钮走 core；奖励屏按 `pending['relic_choices']` 优先于 `card_choices`）
- [ ] **步骤 4：运行验证通过**
- [ ] **步骤 5：Commit**：`feat(warrior): gui 火堆/事件/宝箱/奖励屏`

### 任务 5：商店屏与删牌服务

**文件：** 修改 `gui.py`、`test_gui.py`

- [ ] **步骤 1：编写失败的测试**

```python
def test_shop_slots_and_buy(self):
    # to_shop 辅助布到商店节点 show_screen；槽按钮文本含价格；gold 充足点击 weapon 槽
    # → hero.weapon 变、该按钮 DISABLED、gold 减 price
def test_shop_unaffordable_disabled(self):   # gold=0 时全部商品按钮 DISABLED
def test_discount_shows_base_price(self):
    # hag_hat：槽文本同时出现原价与现价（'原价 100' 子串）
def test_remove_card_service(self):          # 点删牌 → 卡组按钮网格 → 点一张 → deck -1、gold -remove_cost
def test_close_shop(self):                   # 离开按钮 → node_done、回地图
```

- [ ] **步骤 2：运行验证失败**
- [ ] **步骤 3：实现 `show_shop`**（每次点击后整体重建该屏以刷新金币态——朴素但一致）
- [ ] **步骤 4：运行验证通过**
- [ ] **步骤 5：Commit**：`feat(warrior): gui 商店屏与删牌服务`

### 任务 6：结算屏、再来一局、战绩回调与关窗行为

**文件：** 修改 `gui.py`、`main.py`、`test_gui.py`

- [ ] **步骤 1：编写失败的测试**（`make_app` 支持传 on_finish 记录调用）

```python
def test_on_finish_called_once_per_run(self):
    # 布 boss 胜：game 走到 win → show_end；on_finish 收到 {'outcome':'win', depth==11}，且只调一次
def test_replay_uses_new_seed(self):
    # 结算屏“再来一局”invoke → app.game.seed != 旧 seed
def test_leave_button_destroys_root(self):   # invoke 后 root 已 destroy（winfo_exists False）
def test_on_finish_io_error_hint(self):
    # on_finish 返回 'io_error' → 结算屏文本含 '写入失败'
def test_close_midrun_no_record(self):
    # 未完局直接调 app._on_close()：on_finish 未被调用、无异常
def test_apply_result_to_records_aborted_skipped(self):
    # main.apply_result_to_records({'outcome':'aborted'}, tmp) → 文件不创建
```

- [ ] **步骤 2：运行验证失败**
- [ ] **步骤 3：实现 `show_end`**（stats 文本 + 再来一局/离开按钮；再来一局 `start_run(_default_seed 风格的新随机种子)`；`_finished_notified` 标志保证 on_finish 恰好一次；`WM_DELETE_WINDOW → _on_close`：game.finished 则照常，否则直接 destroy 不通知）；`main.py` GUI 分支的 on_finish 用 `apply_result_to_records` 并返回其状态字符串。
- [ ] **步骤 4：运行验证通过**
- [ ] **步骤 5：Commit**：`feat(warrior): gui 结算/重开/战绩回写`

### 任务 7：子进程真实 DPI 布局回归 + 人工验收

**文件：** 修改 `test_gui.py`

- [ ] **步骤 1：编写失败的测试**

```python
def test_layout_fits_with_real_dpi_awareness(self):
    # subprocess.run([sys.executable,'-c',script], cwd=warrior, timeout=60, encoding utf-8)
    # script 内：gui._enable_dpi_awareness(); Tk(); WarriorGUI;
    # game=start_run(7) 后手工布 12 张手牌（deck 换成 12 张再 enter 战斗，
    #   relics=['horn'] 使首回合抽 7）、start_event_combat(['goblin','wolf','slime'])、
    #   _log('这是一条足够长的战斗日志用来验证换行与宽度…'*4); show_combat(); update();
    # 断言收集 problems：
    #   1) 每个按钮/label：font(...).measure(text 首行) <= widget.winfo_width()
    #   2) 每个 hand/enemy 按钮：x+width <= 父容器 width；行容器总高 <= WINDOW_H-顶栏
    #   3) 血条 Canvas 文本 bbox 不越出 canvas
    #   4) root.winfo_reqwidth() <= 1000+1
    # problems 非空 → print + sys.exit(1)
    # 外层 assertEqual(returncode, 0, stdout+stderr)
```

- [ ] **步骤 2：运行验证失败**（首跑大概率暴露 wraplength/列数问题——属预期 RED，按输出调）
- [ ] **步骤 3：调 `_flow_layout` 列数与 `wraplength`**（列数=按实测按钮宽动态取 `max(3, min(6, 可用宽//按钮需求宽))`；wraplength 传参统一走一个模块常量 `WRAP_PX = 170`），重跑至 PASS
- [ ] **步骤 4：全套 + 真机验收**：`python -m unittest discover` 全绿；`python main.py` 真机鼠标打一小局（cmd 与 Windows Terminal 各一眼：无溢出、点击响应、结算正常），记入完成说明
- [ ] **步骤 5：Commit**：`test(warrior): gui 子进程 DPI 布局回归`

---

## 规格覆盖对照

| 规格条目 | 任务 |
|---|---|
| §3 完整循环各屏 | 1(标题/地图) 2/3(战斗) 4(火堆/事件/宝箱/奖励) 5(商店) 6(结算/重开) |
| §3 战绩回调 / X 关闭语义 | 6 |
| §5 DPI 纪律 1~7 | 1(awareness) 2/3(flow+wrap) 7(子进程回归) |
| §6 结构（main 分流、core 零改动） | 1、6 |
| §7 风险（回调级测试局限/手牌溢出） | 7 子进程冒烟 + 手牌 12 张断言 |
