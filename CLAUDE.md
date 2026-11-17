<!-- superpowers-zh:begin (do not edit between these markers) -->
# Superpowers-ZH 中文增强版

本项目已安装 superpowers-zh 技能框架（17 个 skills）。

## 核心规则

1. **收到任务时，先检查是否有匹配的 skill** — 哪怕只有 1% 的可能性也要检查
2. **设计先于编码** — 收到功能需求时，先用 brainstorming skill 做需求分析
3. **测试先于实现** — 写代码前先写测试（TDD）
4. **验证先于完成** — 声称完成前必须运行验证命令

## 可用 Skills

Skills 位于 `.claude/skills/` 目录（17 个），完整清单以系统注入的技能列表为准，不要在此重复维护。高频率使用的：

- **规划**：brainstorming、writing-plans、executing-plans
- **实现**：test-driven-development、systematic-debugging、using-git-worktrees、subagent-driven-development
- **收尾**：verification-before-completion、requesting-code-review、finishing-a-development-branch
- **排障**：diagnosing-superpowers
- **中文参考**：chinese-code-review、chinese-documentation（仅在显式调用时加载）

## 如何使用

当任务匹配某个 skill 时，使用 `Skill` 工具加载对应 skill 并严格遵循其流程。绝不要用 Read 工具读取 SKILL.md 文件。

如果你认为哪怕只有 1% 的可能性某个 skill 适用于你正在做的事情，你必须调用该 skill 检查。
<!-- superpowers-zh:end -->

## 项目经验

见 `.claude/CLAUDE.md`：Tkinter/Windows DPI 布局、存档安全、Git 卫生。
