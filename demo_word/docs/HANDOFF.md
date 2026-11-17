# 地下城游戏 — 新会话交接（2026-11-17）

**本次唯一目标**：第 1 层完整可玩——选角色 → 探索 → 互动 → 遭遇怪 → 打赢 → 进入第 2 层，并用 headless 冒烟测试锁住。

## 现状
- `game-logic.js`：完成，`node --test tests/` 预期 38/38 通过。
- `game-ui.js`：能渲染角色选择/楼层/面板/日志；所有 `.opt-btn` 与 `.free-btn` 没有 click handler。
- 缺：探索/互动/自由输入接线、战斗视图、胜负结局、`build.mjs`。

## 接口
- 状态：`GL.newGame(type)`；楼层内容：`GL.getFloorContent(floor)`（UI 已按层缓存）。
- 战斗：`GL.newBattle(state, monster)` → 每回合 `GL.startPlayerTurn(battle)` → `GL.playerAction(battle, id)` → `GL.monsterTurn(battle)`；结束 `GL.endCombat(battle)`（回满法力）。
- 技能：`GL.SKILLS[charType]`（id → `{name, cost}`）；奖励：`GL.rollReward/applyReward`；进层：`GL.advanceFloor`；胜负：`GL.checkVictory/checkDefeat`。
- 互动：`openBox / solvePuzzle / playRps / crossTrap / scoutTrap / explorationFailPenalty / explorationSuccessReward`。

## 验收（必须自动）
写 `tests/ui.smoke.test.js`（jsdom 或 headless Edge），断言：选角色 → 出现“第 1 层” → 点一个探索选项 → 日志/面板变化 → 进入战斗 → 打完 → 出现“第 2 层”。
完成 = 冒烟测试通过 + 旧 38 个测试不回归。

## 规则
先写失败的冒烟测试 → 再接线 → 才提交；一次只做一个垂直切片。
**不要**重读/重写 `docs/superpowers/` 的计划与裁决；不要先补 20 层；不要把集成留到最后。
