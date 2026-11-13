# warrior_web

杀戮尖塔（Slay the Spire 1）铁甲战士的网页复刻——个人研究项目。设计文档见 `docs/superpowers/specs/`，实现计划见 `docs/superpowers/plans/`。

## 启动三步曲

```bash
npm install                 # 装依赖（esbuild 的 postinstall 需批准一次）
npx playwright install chromium   # 装 e2e 浏览器内核
npm run dev                 # http://localhost:5173
```

## 测试

```bash
npm test        # Vitest：engine/data/sim 纯逻辑
npm run e2e     # Playwright：真实浏览器战斗屏（自动起 vite preview）
```

## 版本基线

Node 26.13 / npm 11.20；vite 5.4.21、vitest 2.1.9、@playwright/test 1.65.0、typescript 5.9.3、react 18.3.1、zod 3.25.76。

## 结构

- `src/engine/` 纯逻辑战斗状态机（零 DOM，动作返回 `GameEvent[]`）
- `src/data/` cards.json 校验与加载
- `src/ui/` React 展示层（只消费 snapshot）
- `src/sim/` 无头自动对战
- `scripts/` wiki 抓取与审计校验
