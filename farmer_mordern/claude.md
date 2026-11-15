# CLAUDE.md

本文件为 Claude Code 提供项目上下文与开发约定。修改本项目前请先阅读全文。

## 项目概述

**Prism Farm（棱镜农场）** —— 一款现代 UI 风格的**农场种植放置（Idle / Incremental）单机游戏**。

核心循环：**种植 → 等待生长 → 收获 → 升级/解锁 → 更快地种植**。
时间是最重要的资源：玩家离线期间作物继续生长，回来领取收益。

**产品定位：纯单机。**
- 无服务端、无账号、无云存档、无排行榜、无内购、无埋点、无任何网络请求。
- 打包后必须**可完全离线运行**（断网、`file://` 双击 `dist/index.html` 均可用）。
- 存档存在玩家本地浏览器（`localStorage`），并提供**本地文件导入/导出**作为备份手段。

- 视觉风格：深色玻璃拟态 + 有机生长感，柔和呼吸动效 + 收获反馈。
- 目标平台：桌面浏览器优先（≥1280px），移动端自适应（≥375px）。
- 产品调性：**低压力、高正反馈**。无失败状态（无敌人/生命/Game Over）。

## 技术栈

| 层 | 技术 |
|---|---|
| 构建 | Vite 5（配置 `base: './'` 以支持 `file://` 直接打开） |
| 语言 | TypeScript 5（`strict: true`，禁止 `any`） |
| UI | React 18 + Tailwind CSS v3 |
| 状态 | Zustand + `immer` + `persist` 中间件 |
| 动效 | Framer Motion（UI 层）+ CSS `@keyframes`（环境动画） |
| 大数 | **break_infinity.js**（`Decimal`） |
| 背景氛围层 | Canvas 2D（仅粒子/光斑，非游戏逻辑） |
| 音效 | Howler.js（音频资源打包进产物，默认静音） |
| 字体 | 本地 `woff2` 自托管（**禁止**引入 Google Fonts 等外部 CDN） |
| 测试 | Vitest（覆盖 `game/systems`、`Formatter`、`OfflineCalc`、存档迁移） |
| 代码质量 | ESLint + Prettier |

**不要引入**：Phaser / PixiJS / Three.js / Redux / styled-components / axios / fetch 封装 / 任何后端 SDK / 任何分析 SDK / 任何外部字体或图标 CDN。

**必须使用 `Decimal`**：所有金币、产量、累计收益字段一律是 `Decimal`，禁止用 `number` 参与金额运算。

## 常用命令

```bash
npm run dev        # 开发服务器
npm run build      # 生产构建（含 tsc 检查），输出 dist/ 可直接 file:// 打开
npm run preview    # 预览产物
npm run test       # Vitest
npm run lint       # ESLint
npm run format     # Prettier