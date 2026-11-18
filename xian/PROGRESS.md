# 云岫修仙录 V2.0 进度状态

- 当前任务包：TASK 7 UI 集成与视觉打磨
- 已完成：
  - TASK 0 审计 + 基线（smoke 71/71）+ 3 个遗留 bug 修复回归
  - TASK 1 数据层（配置/状态/迁移/ResourceSystem/BuffSystem，v2 79/79）
  - TASK 2 灵根（RootSystem 一次性选择 + Rates 各通道倍率 + 土建筑成本 + 水离线 + 持久化/旧档补选，v2-roots 28/28）
  - TASK 3 功法（TechniqueSystem 解锁/装备/升级≤5 + Rates 功法倍率，v2-techniques 36/36）
  - TASK 4 秘境（ExpeditionSystem start/claim/progress + 奖励快照 + 一次一个 + 确定性种子，v2-expeditions 30/30）
  - TASK 5 炼丹（AlchemySystem craft/use + BuffSystem 接入 Rates 四通道 + 计数语义 + 引擎过期清除，v2-alchemy 38/38）
  - TASK 6 任务/成就联动（6 新成就 + 12 新任务条目 + 每日/挑战 + 联动重载一致性，v2-quests 96/96）
- 下一步：TASK 7 UI 集成与视觉打磨 —— 底部导航扩 4 页签（洞府/历练/成就/日志 → 增加 功法/秘境/丹房 或合并入口）、
  灵根觉醒弹窗、功法/秘境/丹房面板（卡片/状态标签/进度条/空状态/错误提示）、手机端排版、所有按钮真实可点；
  验收：无空白面板、无错位、无假按钮；完成后全量跑套件保持 378/378
- 全量验证命令：`node test/smoke.js && node test/v2.js && node test/v2-roots.js && node test/v2-techniques.js && node test/v2-expeditions.js && node test/v2-alchemy.js && node test/v2-quests.js`（当前 71+79+28+36+30+38+96 = 378/378 全绿）
- 纪律：TDD 红→绿；每片全量跑套件；不并行改同一 HTML
- 记录：TASK 2 绿灯阶段修正了 4 处测试期望（非生产 bug）：reset() 无返回值改为独立语句；
  补选 fire 触发 a3(time1h) 延迟发放 +1000 灵石属既有成就行为，断言改为 stone≥500；
  breathCult 恒含境界倍率（stage2×1.5），期望改为 20×1.5×1.2=36。
  TASK 4 设计：奖励确定性 = FNV-1a(id:durKey) ^ startedAt → xorshift32，逐项 1±0.1 抖动，
  境界倍率 min(2.5, 1+0.02×开始境界)；claim 后 active=null（规格「领取后清除任务状态」），
  结构上不可能重复领取；入账按快照：stone 直接加 resources/stats.totalStone，
  灵草/妖丹/残卷走 ResourceSystem.add（add 只认 TYPES，会拒绝 'stone'）。
  TASK 5 设计：计数语义 = stats.pillsUsed 只由 BuffSystem.apply 自增、
  AlchemySystem.use 只补记 quests.daily.pillUsed、craft 自增 pillsCrafted + daily.craft，三者互不重复；
  Rates 四通道加可选 now 参数（缺省真实时钟，旧调用点零改动）并乘 buffMult(affects, now)；
  BuffSystem.update() 接入 Game.init（启动）与 GameEngine.advance（每 tick）两处，过期增益自动清除。
  TASK 6 记录：v2-quests.js 先行红灯（12 新任务/6 新成就均缺配置），最小实现补配置+CONDS+metric 后转绿；
  绿灯阶段修复 4 处既有测试（v2-roots 2 处、v2-expeditions 2 处）：新成就 a9(root1)/a11(expedition1)
  经系统方法内部 checkAll() 级联发放奖励，污染精确入账断言——属既有成就发放行为，
  用 preUnlockAch(G, exceptId) 预解锁隔离（与 v2-techniques/v2-quests 既有模式一致），非生产 bug；
  v2-roots 旧档补选用 exceptId='a3' 保留 a3(time1h) 按测试本意发放。
- 交付物：index.html（开发）→ 云岫修仙录_V2.0.html（交付副本）+ 开发报告
- 风险：单文件大改动，UI 渲染函数必须在 DOM 桩下安全运行

## 本次续作（2026-11-17）
- TASK 7：已接入功法/秘境/丹房三个导航面板；灵根觉醒界面含一次性确认；卡片、库存、条件、倒计时、进度条与按钮禁用状态接入真实系统。
- 统一事件委托调用原系统，操作后检查任务成就并保存；复用资源成本显示及提示反馈；新增响应式卡片布局。
- 验证：原七套回归 378/378 通过；新增 test/v2-ui.js 集成流程通过。
- 尚待完成：TASK 7 实际浏览器视觉、键盘与手机验收；TASK 8 浏览器全流程、离线 Buff 分段收益审计、最终交付副本与开发报告。当前不标记最终验收完成。


## 审计与集成验证续作
- 复核 TASK 0–6 回归：378/378 通过，未重写既有系统。
- 修复离线/后台跨丹药到期时遗漏有效增益：Rates.integrate 按时间分段；启动时先离线结算再清理增益；待领收益保留原金额。
- 新增离线到期失败回归，修复后通过；UI 集成流程通过。
- Chrome 实际 file:// 启动并输出已渲染 DOM。
- 已生成 云岫修仙录_V2.0.html 与 开发报告.md；开发和交付副本一致。
- TASK 8 尚缺真实移动设备与完整浏览器点击/视觉及长期平衡验收，不能宣称最终验收全部通过。


## 启动卡住修复
- 修复 V2 渲染将浏览器序列化 innerHTML 与源串比较导致每 tick 重建 DOM：缓存原始标记，未变化时保留按钮节点。
- 灵根觉醒取消 window.confirm 阻塞调用，改为页内确认与返回，确认界面跨 tick 保持稳定。
- 新增 test/v2-render.js：模拟浏览器规范化标记，验证重绘、确认和取消稳定性；七套 378 项及 UI/离线/渲染测试通过。
- 已同步更新交付 HTML，保留原存档。


## 滚动流畅性优化
- 自动 DOM 刷新从每 100ms 改为最多每 300ms；捕获被动 scroll 事件，滚动期间延迟自动重绘，停止 180ms 后下次 tick 补绘。主动操作立即渲染，资源计算频率不变。
- 降低大面积云朵模糊开销；滚动时暂停背景/进度装饰动画，触屏停用背景粒子动画与 backdrop-filter，并支持 reduced-motion。
- 新增 test/v2-scroll.js 验证滚动延迟、恢复、节流与资源持续增长；378 项回归及四个新增集成脚本通过。尚无真实设备 FPS 量测。
- 已同步交付文件。


## 趣味玩法扩展：历练策略与机缘
- 仅维护 index.html，遵循用户删除 V2.0 副本的要求，不重新生成交付副本。
- 三种历练策略：原有均衡、寻药材料路线、访古残卷路线；策略在出发前选择，历练中锁定，倍率与时长集中 GameConfig。
- 特殊路线完成后触发三种机缘之一，可稳妥领取或冒险探查；失败不扣原奖励，聚气丹增加成功率。事件与结果种子持久化，禁止重复领取。
- 新增成长任务「机缘由心」，按真实解决事件计数推进。
- exploration 默认补全与迁移校验，保存路线、待决事件和解决次数；旧档保持均衡原玩法。
- 回归：378/378 全通过；UI/离线/稳定渲染/滚动回归均通过；新增 v2-exploration 验证倍率、时长、锁定、存档、重复领取、失败/丹药增益与任务指标。

