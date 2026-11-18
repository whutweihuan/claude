/* 云岫修仙录 V2.0 TASK 2 测试：五行灵根
 * 用法：node test/v2-roots.js
 * 覆盖：RootSystem 一次性选择 / Rates 各通道倍率 / 吐纳收益 /
 *       建筑成本 / 离线收益 / 持久化 / 旧存档补选
 * 每节独立沙盒（test/harness.js）。
 * Rates/离线/购买断言直接落 rootId 到状态，独立于 RootSystem 模块验证
 * 「状态 → 数值」链路；select() 语义单独成节。
 */
'use strict';
const { createSandbox } = require('./harness.js');

let pass = 0, fail = 0;
function ok(name, cond, extra) {
  if (cond) { pass++; console.log('  ok  ' + name); }
  else { fail++; console.log('FAIL  ' + name + (extra !== undefined ? '  [' + extra + ']' : '')); }
}
const near = (a, b) => Math.abs(a - b) < 1e-9;
function fresh() {
  const ctx = createSandbox();
  if (!ctx.G) { console.error('FAIL: 桥接导出失败'); process.exit(1); }
  ctx.G.GameEngine.stop();
  return ctx;
}
/* 预解锁全部成就（可排除一个）：隔离成就奖励干扰，使购买/补选断言只测自己的入账。
 * RootSystem.select / UpgradeSystem.buy 内部都会调用 AchievementSystem.checkAll()
 * （见 index.html），觉醒灵根即触发 a9 五行初窥（root1 → +300 灵石/+300 修为），
 * 其入账会污染「灵石恰好扣光」与「进度无损（修为不变）」类精确断言。 */
function preUnlockAch(G, exceptId) {
  const s = G.GameState.state;
  for (const a of G.GameConfig.ACHIEVEMENTS) {
    if (a.id !== exceptId && s.achievements.unlocked.indexOf(a.id) === -1) s.achievements.unlocked.push(a.id);
  }
}

/* ---------- 1. RootSystem 一次性选择 ---------- */
console.log('\n== 1. RootSystem 一次性选择 ==');
{
  const { G } = fresh();
  const s = G.GameState.state;
  const RS = G.RootSystem;
  ok('模块存在', !!RS);
  if (RS) {
    ok('select(wood) 成功且 rootId 落状态', RS.select('wood') === true && s.cultivation.rootId === 'wood', s.cultivation && s.cultivation.rootId);
    ok('select 拒绝未知灵根', RS.select('bogus') === false && s.cultivation.rootId === 'wood');
    ok('select 拒绝 null/undefined', RS.select(null) === false && RS.select(undefined) === false && s.cultivation.rootId === 'wood');
    ok('已觉醒后拒绝改选（一次性）', RS.select('metal') === false && s.cultivation.rootId === 'wood');
    ok('选择后资源状态未被破坏', [s.resources.stone, s.realm.cult].every(Number.isFinite) && s.resources.stone >= 0);
  }
  const { G: G2 } = fresh();
  ok('全新存档：未觉醒 rootId = null', G2.GameState.state.cultivation.rootId === null);
}

/* ---------- 2. 各灵根对 Rates 通道的倍率（状态 → 数值） ---------- */
console.log('\n== 2. 灵根 → Rates 倍率 ==');
{
  const { G } = fresh();
  const s = G.GameState.state;
  s.cultivation.rootId = 'wood';
  ok('木灵根：修为/秒 ×1.12', near(G.Rates.cultPerSec(), 1.0 * 1.12), G.Rates.cultPerSec());
  ok('木灵根：灵石/秒 不受影响', near(G.Rates.stonePerSec(), 0.5), G.Rates.stonePerSec());
  s.cultivation.rootId = 'metal';
  ok('金灵根：灵石/秒 ×1.12', near(G.Rates.stonePerSec(), 0.5 * 1.12), G.Rates.stonePerSec());
  ok('金灵根：修为/秒 不受影响', near(G.Rates.cultPerSec(), 1.0), G.Rates.cultPerSec());
  s.cultivation.rootId = 'fire';
  ok('火灵根：吐纳修为/灵石 ×1.2', near(G.Rates.breathCult(), 20 * 1.2) && near(G.Rates.breathStone(), 4 * 1.2), JSON.stringify([G.Rates.breathCult(), G.Rates.breathStone()]));
  s.cultivation.rootId = 'earth';
  ok('土灵根：建筑成本 ×0.9（10→9）', G.Rates.buildingCost('array') === 9, G.Rates.buildingCost('array'));
  s.cultivation.rootId = 'water';
  ok('水灵根：在线速率不变（只加离线）', near(G.Rates.cultPerSec(), 1.0) && near(G.Rates.stonePerSec(), 0.5), JSON.stringify([G.Rates.cultPerSec(), G.Rates.stonePerSec()]));
  s.pendingOffline = null; // 独立验证未觉醒离线场景，排除上一场景待领收益。
  s.cultivation.rootId = null;
  ok('未觉醒：速率回到基准', near(G.Rates.cultPerSec(), 1.0) && G.Rates.buildingCost('array') === 10, JSON.stringify([G.Rates.cultPerSec(), G.Rates.buildingCost('array')]));
}

/* ---------- 3. 火灵根：吐纳实际入账 ---------- */
console.log('\n== 3. 火灵根 → breath() 实际收益 ==');
{
  const { G } = fresh();
  G.GameState.state.cultivation.rootId = 'fire';
  const r = G.CultivationSystem.breath();
  ok('breath 返回 {cult:24, stone:4.8}', r && near(r.cult, 24) && near(r.stone, 4.8), JSON.stringify(r));
}

/* ---------- 4. 水灵根：离线收益 ×1.15 ---------- */
console.log('\n== 4. 水灵根 → 离线收益 ==');
{
  const { G } = fresh();
  const s = G.GameState.state;
  s.cultivation.rootId = 'water';
  const baseCultRate = G.Rates.cultPerSec(); // 水灵根不影响在线速率
  const baseStoneRate = G.Rates.stonePerSec();
  s.lastSaved = Date.now() - 3600 * 1000;    // 1 小时前
  const off = G.SaveSystem.computeOffline((s.lastSaved + 3600 * 1000) / 1000);
  ok('离线 1h：seconds = 3600', off && off.seconds === 3600, off && off.seconds);
  ok('离线 1h：修为 = 基准速率×时长×1.15', off && near(off.cult, baseCultRate * off.seconds * 1.15), off && off.cult);
  ok('离线 1h：灵石 = 基准速率×时长×1.15', off && near(off.stone, baseStoneRate * off.seconds * 1.15), off && off.stone);
  s.pendingOffline = null; // 独立验证未觉醒离线场景，排除上一场景待领收益。
  s.cultivation.rootId = null;
  s.lastSaved = Date.now() - 1800 * 1000;
  const off0 = G.SaveSystem.computeOffline((s.lastSaved + 1800 * 1000) / 1000);
  ok('未觉醒：离线收益无加成', off0 && near(off0.cult, baseCultRate * off0.seconds) && near(off0.stone, baseStoneRate * off0.seconds), JSON.stringify(off0 && [off0.cult, off0.stone]));
}

/* ---------- 5. 土灵根：建筑购买按折后成本结算 ---------- */
console.log('\n== 5. 土灵根 → 建筑购买 ==');
{
  const { G } = fresh();
  const s = G.GameState.state;
  preUnlockAch(G);   /* 隔离 a9（觉醒即触发）奖励干扰，使「灵石恰好扣光」只测购买入账 */
  s.cultivation.rootId = 'earth';
  ok('折后成本 = 9 灵石', G.Rates.buildingCost('array') === 9, G.Rates.buildingCost('array'));
  s.resources.stone = 8;
  ok('8 灵石不足 → 购买拒绝', G.UpgradeSystem.buy('array') === null);
  s.resources.stone = 9;
  const b = G.UpgradeSystem.buy('array');
  ok('9 灵石恰好购买成功（cost=9）', b && b.level === 1 && b.cost === 9 && near(s.resources.stone, 0), JSON.stringify(b));
}

/* ---------- 6. 持久化 + 旧存档补选 ---------- */
console.log('\n== 6. 持久化 / 旧存档补选 ==');
{
  const { G } = fresh();
  if (G.RootSystem) {
    const selOk = G.RootSystem.select('wood') === true;
    const svd = G.SaveSystem.save() === true;
    G.GameState.reset();   /* 注意：reset() 无返回值，必须作为独立语句，不能进 && 链 */
    const freshNull = G.GameState.state.cultivation.rootId === null;
    G.SaveSystem.load();   /* load() 返回 state 对象 */
    ok('select 后保存 → 重置 → 读回仍为 wood',
      selOk && svd && freshNull && G.GameState.state.cultivation.rootId === 'wood');
    ok('读回后仍为一次性（拒绝改选）', G.RootSystem.select('metal') === false && G.GameState.state.cultivation.rootId === 'wood');
  }
  const { G: Gv, store } = fresh();
  const v1 = {
    version: 1,
    realm: { stage: 2, cult: 888.5 },
    resources: { stone: 500 },
    buildings: { array: 2, vein: 1, alchemy: 0 },
    stats: { totalCult: 5000, totalStone: 1200, breathCount: 30, upgradeCount: 5, breakthroughCount: 2, playTimeSec: 7200 },
    quests: { claimed: { g1: true }, dailyDate: '2000-1-1', daily: { breath: 3, cult: 90, upgrade: 1 } },
    achievements: { unlocked: ['a1', 'a2'] },
    settings: { sound: true },
    pendingOffline: null,
    log: [],
    lastSaved: Date.now() - 60000,
  };
  store[Gv.GameConfig.SAVE_KEY] = JSON.stringify(v1);
  Gv.SaveSystem.load();
  ok('旧存档：迁移后未觉醒', Gv.GameState.state.cultivation.rootId === null);
  if (Gv.RootSystem) {
    preUnlockAch(Gv, 'a3');   /* 其余成就（含新 a9）全部预解锁以隔离奖励；仅保留旧 a3(time1h) 按测试本意发放 */
    const r = Gv.RootSystem.select('fire');
    const s2 = Gv.GameState.state;
    /* 注意：select() 会触发 checkAll()，V1 存档 playTimeSec=7200 满足 a3(time1h)
     * 而 a3 未解锁 → 延迟发放 +1000 灵石。这是既有成就发放行为，非进度丢失，
     * 故只断言「不少于 500」（无损失不变式）。 */
    ok('旧存档补选 fire 成功且进度无损',
      r === true && s2.cultivation.rootId === 'fire' &&
      s2.realm.stage === 2 && near(s2.realm.cult, 888.5) && s2.resources.stone >= 500 && s2.buildings.array === 2,
      s2.resources.stone);
    /* breathCult 恒含境界倍率：stage2 → ×1.5；火灵根再 ×1.2 → 20*1.5*1.2 = 36 */
    ok('补选后火灵根立即生效（breathCult = 20×境界×1.2）',
      near(Gv.Rates.breathCult(), 20 * (1 + 2 * Gv.GameConfig.REALM_MULT_PER_STAGE) * 1.2), Gv.Rates.breathCult());
  }
}

/* ---------- 汇总 ---------- */
console.log('\n' + pass + ' passed, ' + fail + ' failed');
process.exit(fail ? 1 : 0);
