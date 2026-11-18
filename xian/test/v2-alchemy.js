/* 云岫修仙录 V2.0 TASK 5 测试：炼丹系统
 * 用法：node test/v2-alchemy.js
 * 覆盖：craft 守卫（材料不足/未知丹药）/ craft 成功（原子扣料+库存+计数）/
 *       use 守卫 / use 成功（扣库存 + 落增益 + 计数语义不重复）/ 刷新不叠加 /
 *       增益接入 Rates 各通道（含真实 breath()、与灵根/功法乘性叠加、过期回退）/
 *       过期清除 / 持久化往返（刷新页面不丢生效中增益）
 * 每节独立沙盒（test/harness.js）；时间戳一律显式传入，不依赖真实时钟。
 * 配方/加成/时长全部从 GameConfig.PILLS 读取，不在测试里硬编码数值。
 * 注意计数语义：stats.pillsUsed 由 BuffSystem.apply 自增，
 * AlchemySystem.use 只自增 quests.daily.pillUsed —— 两者合计各 +1，不许重复计。
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
const T0 = Date.now() + 1e9;   /* 远未来：显式时间戳下增益必然“生效中” */

/* ---------- 1. craft 守卫 ---------- */
console.log('\n== 1. craft 守卫 ==');
{
  const { G } = fresh();
  const AS = G.AlchemySystem;
  const s = G.GameState.state;
  ok('模块存在', !!AS);
  if (AS) {
    const P = G.GameConfig.PILLS;
    ok('未知丹药：拒绝且不落库存', AS.craft('bogus') === false && Object.keys(s.alchemy.inventory).length === 0);
    s.resources.herbs = P.juqi.cost.herbs - 1;
    ok('灵草差 1：拒绝且资源不动',
      AS.craft('juqi') === false && s.resources.herbs === P.juqi.cost.herbs - 1 && Object.keys(s.alchemy.inventory).length === 0,
      JSON.stringify(s.resources));
    /* 混合成本原子性：灵草够、妖丹差 1 → 灵草不得被扣 */
    s.resources.herbs = P.nshen.cost.herbs;
    s.resources.demonCores = (P.nshen.cost.demonCores || 0) - 1;
    ok('凝神丹 妖丹差 1：原子拒绝（灵草不动）',
      AS.craft('nshen') === false && s.resources.herbs === P.nshen.cost.herbs && s.resources.demonCores === (P.nshen.cost.demonCores || 0) - 1);
    s.resources.herbs = P.naling.cost.herbs;
    s.resources.demonCores = P.naling.cost.demonCores - 1;
    ok('纳灵丹 妖丹差 1：原子拒绝',
      AS.craft('naling') === false && s.resources.demonCores === P.naling.cost.demonCores - 1);
  }
}

/* ---------- 2. craft 成功 ---------- */
console.log('\n== 2. craft 成功 ==');
{
  const { G } = fresh();
  const AS = G.AlchemySystem;
  const s = G.GameState.state;
  const P = G.GameConfig.PILLS;
  if (AS) {
    s.resources.herbs = P.juqi.cost.herbs;
    const r = AS.craft('juqi');
    ok('聚气丹：恰好扣光灵草、库存 +1',
      r === true && s.resources.herbs === 0 && (s.alchemy.inventory.juqi || 0) === 1,
      JSON.stringify([s.resources.herbs, s.alchemy.inventory]));
    ok('计数：pillsCrafted +1、daily.craft +1',
      s.stats.pillsCrafted === 1 && s.quests.daily.craft === 1,
      JSON.stringify([s.stats.pillsCrafted, s.quests.daily.craft]));
    ok('炼制不消耗库存（pillsUsed 不动）', s.stats.pillsUsed === 0 && s.quests.daily.pillUsed === 0);

    s.resources.herbs = P.nshen.cost.herbs;
    s.resources.demonCores = P.nshen.cost.demonCores;
    ok('凝神丹：灵草+妖丹全扣、库存 +1',
      AS.craft('nshen') === true && s.resources.herbs === 0 && s.resources.demonCores === 0 && (s.alchemy.inventory.nshen || 0) === 1,
      JSON.stringify(s.resources));
    s.resources.herbs = P.naling.cost.herbs;
    s.resources.demonCores = P.naling.cost.demonCores;
    ok('纳灵丹：混合成本全扣、库存 +1',
      AS.craft('naling') === true && s.resources.herbs === 0 && s.resources.demonCores === 0 && (s.alchemy.inventory.naling || 0) === 1);
    ok('累计计数：pillsCrafted=3、daily.craft=3', s.stats.pillsCrafted === 3 && s.quests.daily.craft === 3,
      JSON.stringify([s.stats.pillsCrafted, s.quests.daily.craft]));
  }
}

/* ---------- 3. use 守卫 ---------- */
console.log('\n== 3. use 守卫 ==');
{
  const { G } = fresh();
  const AS = G.AlchemySystem;
  const s = G.GameState.state;
  if (AS) {
    ok('未知丹药：拒绝', AS.use('bogus', T0) === false && Object.keys(s.alchemy.activeBuffs).length === 0);
    ok('无库存：拒绝且状态不动',
      AS.use('juqi', T0) === false &&
      Object.keys(s.alchemy.activeBuffs).length === 0 &&
      s.stats.pillsUsed === 0 && s.quests.daily.pillUsed === 0,
      JSON.stringify([s.alchemy.activeBuffs, s.stats.pillsUsed, s.quests.daily.pillUsed]));
  }
}

/* ---------- 4. use 成功（计数语义） ---------- */
console.log('\n== 4. use 成功 ==');
{
  const { G } = fresh();
  const AS = G.AlchemySystem;
  const s = G.GameState.state;
  const P = G.GameConfig.PILLS;
  if (AS) {
    s.alchemy.inventory.juqi = 1;
    const r = AS.use('juqi', T0);
    const bf = s.alchemy.activeBuffs[P.juqi.affects];
    ok('返回 true、库存 -1', r === true && s.alchemy.inventory.juqi === 0);
    ok('增益落状态：{pill, expiresAt = now + 配置时长}',
      bf && bf.pill === 'juqi' && bf.expiresAt === T0 + P.juqi.durationMs, JSON.stringify(s.alchemy.activeBuffs));
    ok('计数恰好各 +1（apply 计 pillsUsed，use 计 daily.pillUsed，不重复）',
      s.stats.pillsUsed === 1 && s.quests.daily.pillUsed === 1,
      JSON.stringify([s.stats.pillsUsed, s.quests.daily.pillUsed]));
    ok('倍率 = 1 + bonusPct/100（显式时间戳下生效）',
      near(G.BuffSystem.getMultiplier(P.juqi.affects, T0), 1 + P.juqi.bonusPct / 100),
      G.BuffSystem.getMultiplier(P.juqi.affects, T0));
  }
}

/* ---------- 5. 同类增益刷新不叠加（规则 7/8） ---------- */
console.log('\n== 5. 刷新不叠加 ==');
{
  const { G } = fresh();
  const AS = G.AlchemySystem;
  const s = G.GameState.state;
  const P = G.GameConfig.PILLS;
  if (AS) {
    s.alchemy.inventory.juqi = 2;
    AS.use('juqi', T0);
    const first = s.alchemy.activeBuffs.cult.expiresAt;
    const t2 = T0 + 100000;
    AS.use('juqi', t2);
    const bf = s.alchemy.activeBuffs.cult;
    ok('再次使用：刷新到期时间（而非叠加第二条）',
      bf.expiresAt === t2 + P.juqi.durationMs && bf.expiresAt !== first,
      JSON.stringify(bf));
    ok('倍率仍为单份（不允许无限乘算）',
      near(G.BuffSystem.getMultiplier('cult', t2), 1 + P.juqi.bonusPct / 100) &&
      Math.abs(G.BuffSystem.getMultiplier('cult', t2) - (1 + P.juqi.bonusPct / 100) ** 2) > 1e-9,
      G.BuffSystem.getMultiplier('cult', t2));
    ok('两次使用：pillsUsed=2、daily.pillUsed=2',
      s.stats.pillsUsed === 2 && s.quests.daily.pillUsed === 2 && s.alchemy.inventory.juqi === 0,
      JSON.stringify([s.stats.pillsUsed, s.quests.daily.pillUsed, s.alchemy.inventory.juqi]));
    /* 不同丹药走不同通道，互不覆盖 */
    s.alchemy.inventory.nshen = 1;
    AS.use('nshen', t2);
    ok('凝神丹落 breath 通道，cult 通道保持原到期时间',
      s.alchemy.activeBuffs.breath && s.alchemy.activeBuffs.breath.pill === 'nshen' &&
      s.alchemy.activeBuffs.cult.expiresAt === t2 + P.juqi.durationMs,
      JSON.stringify(s.alchemy.activeBuffs));
  }
}

/* ---------- 6. 增益接入 Rates（独立于 AlchemySystem：直接落增益状态） ---------- */
console.log('\n== 6. 增益 → Rates 各通道 ==');
{
  const { G } = fresh();
  const s = G.GameState.state;
  const P = G.GameConfig.PILLS;
  const GC = G.GameConfig;
  ok('基线（无增益）：1.0 / 0.5 / 20 / 4',
    near(G.Rates.cultPerSec(), 1.0) && near(G.Rates.stonePerSec(), 0.5) &&
    near(G.Rates.breathCult(), 20) && near(G.Rates.breathStone(), 4),
    JSON.stringify([G.Rates.cultPerSec(), G.Rates.stonePerSec(), G.Rates.breathCult(), G.Rates.breathStone()]));

  s.alchemy.activeBuffs.cult = { pill: 'juqi', expiresAt: T0 + P.juqi.durationMs };
  const mj = 1 + P.juqi.bonusPct / 100;
  ok('聚气丹：修为/秒 ×' + mj + '（显式 T0）', near(G.Rates.cultPerSec(T0), 1.0 * mj), G.Rates.cultPerSec(T0));
  ok('聚气丹：灵石/秒、吐纳不受影响', near(G.Rates.stonePerSec(T0), 0.5) && near(G.Rates.breathCult(T0), 20));

  s.alchemy.activeBuffs.breath = { pill: 'nshen', expiresAt: T0 + P.nshen.durationMs };
  const mn = 1 + P.nshen.bonusPct / 100;
  ok('凝神丹：吐纳修为 ×' + mn, near(G.Rates.breathCult(T0), 20 * mn), G.Rates.breathCult(T0));
  ok('凝神丹：吐纳灵石 ×' + mn, near(G.Rates.breathStone(T0), 4 * mn), G.Rates.breathStone(T0));
  ok('凝神丹：修为/秒、灵石/秒不受影响', near(G.Rates.cultPerSec(T0), 1.0 * mj) && near(G.Rates.stonePerSec(T0), 0.5));

  s.alchemy.activeBuffs.stone = { pill: 'naling', expiresAt: T0 + P.naling.durationMs };
  const ml = 1 + P.naling.bonusPct / 100;
  ok('纳灵丹：灵石/秒 ×' + ml, near(G.Rates.stonePerSec(T0), 0.5 * ml), G.Rates.stonePerSec(T0));

  /* 真实吐纳（内部走默认 now = 真实时钟；T0 远未来 → 增益必然生效） */
  delete s.alchemy.activeBuffs.cult; delete s.alchemy.activeBuffs.stone;
  s.alchemy.activeBuffs.breath = { pill: 'nshen', expiresAt: T0 + P.nshen.durationMs };
  const b = G.CultivationSystem.breath();
  ok('实际 breath()：{cult: 20×' + mn + ', stone: 4×' + mn + '}',
    b && near(b.cult, 20 * mn) && near(b.stone, 4 * mn), JSON.stringify(b));

  /* 过期 → 回基准（显式时间戳） */
  const after = T0 + P.juqi.durationMs + 1000;
  s.alchemy.activeBuffs = {
    cult: { pill: 'juqi', expiresAt: T0 + P.juqi.durationMs },
    breath: { pill: 'nshen', expiresAt: T0 + P.nshen.durationMs },
    stone: { pill: 'naling', expiresAt: T0 + P.naling.durationMs },
  };
  ok('过期后（T0+时长+1s）：全部回到基准',
    near(G.Rates.cultPerSec(after), 1.0) && near(G.Rates.stonePerSec(after), 0.5) &&
    near(G.Rates.breathCult(after), 20) && near(G.Rates.breathStone(after), 4),
    JSON.stringify([G.Rates.cultPerSec(after), G.Rates.stonePerSec(after), G.Rates.breathCult(after), G.Rates.breathStone(after)]));
}
{
  const { G } = fresh();
  const s = G.GameState.state;
  const P = G.GameConfig.PILLS;
  s.cultivation.rootId = 'wood';
  s.alchemy.activeBuffs.cult = { pill: 'juqi', expiresAt: T0 + P.juqi.durationMs };
  ok('与木灵根乘性叠加：修为/秒 = 1×1.12×(1+bonus)',
    near(G.Rates.cultPerSec(T0), 1.0 * 1.12 * (1 + P.juqi.bonusPct / 100)), G.Rates.cultPerSec(T0));
  s.cultivation.rootId = null;
  s.cultivation.techniques = { taihu: { unlocked: true, level: 1 } };
  s.cultivation.equippedTechnique = 'taihu';
  s.alchemy.activeBuffs.breath = { pill: 'nshen', expiresAt: T0 + P.nshen.durationMs };
  const tb = 1 + G.GameConfig.TECHNIQUES.taihu.bonuses[0] / 100;
  ok('与太虚 Lv1 乘性叠加：吐纳修为 = 20×' + tb + '×(1+bonus)',
    near(G.Rates.breathCult(T0), 20 * tb * (1 + P.nshen.bonusPct / 100)), G.Rates.breathCult(T0));
}

/* ---------- 7. 过期清除（BuffSystem.update） ---------- */
console.log('\n== 7. 过期清除 ==');
{
  const { G } = fresh();
  const s = G.GameState.state;
  const P = G.GameConfig.PILLS;
  s.alchemy.activeBuffs.cult = { pill: 'juqi', expiresAt: T0 + P.juqi.durationMs };
  G.BuffSystem.update(T0 + P.juqi.durationMs + 1);
  ok('update 到期后清除', Object.keys(s.alchemy.activeBuffs).length === 0, JSON.stringify(s.alchemy.activeBuffs));
  ok('清除后倍率 = 1、Rates 回基准',
    near(G.BuffSystem.getMultiplier('cult', T0 + P.juqi.durationMs + 1), 1) && near(G.Rates.cultPerSec(T0 + P.juqi.durationMs + 1), 1.0));
  s.alchemy.activeBuffs.cult = { pill: 'juqi', expiresAt: T0 + P.juqi.durationMs };
  G.BuffSystem.update(T0 + 1000);
  ok('未到期不清除', s.alchemy.activeBuffs.cult && s.alchemy.activeBuffs.cult.expiresAt === T0 + P.juqi.durationMs);
}

/* ---------- 8. 持久化往返（刷新页面不丢生效中增益） ---------- */
console.log('\n== 8. 持久化 ==');
{
  const { G } = fresh();
  const AS = G.AlchemySystem;
  if (AS) {
    const s = G.GameState.state;
    const P = G.GameConfig.PILLS;
    s.alchemy.inventory.juqi = 2;
    AS.use('juqi', T0);
    const saved = {
      inv: (s.alchemy.inventory.juqi || 0),
      bf: JSON.stringify(s.alchemy.activeBuffs),
    };
    const svd = G.SaveSystem.save() === true;
    G.GameState.reset();   /* 注意：reset() 无返回值，独立语句 */
    const wiped = (G.GameState.state.alchemy.inventory.juqi || 0) === 0 && Object.keys(G.GameState.state.alchemy.activeBuffs).length === 0;
    G.SaveSystem.load();   /* load() 返回 state 对象 */
    const s2 = G.GameState.state;
    ok('库存 + 生效增益：保存 → 重置 → 读回保留',
      svd && wiped && (s2.alchemy.inventory.juqi || 0) === saved.inv && JSON.stringify(s2.alchemy.activeBuffs) === saved.bf,
      JSON.stringify([saved, s2.alchemy]));
    ok('读回后增益仍在生效窗口内（ Rates 保持倍率）',
      near(G.Rates.cultPerSec(T0), 1.0 * (1 + P.juqi.bonusPct / 100)), G.Rates.cultPerSec(T0));
    ok('读回后可继续使用（库存 1 → 0，刷新到期时间）',
      AS.use('juqi', T0 + 50000) === true && s2.alchemy.inventory.juqi === 0 &&
      s2.alchemy.activeBuffs.cult.expiresAt === T0 + 50000 + P.juqi.durationMs,
      JSON.stringify(s2.alchemy));
  }
}

/* ---------- 汇总 ---------- */
console.log('\n' + pass + ' passed, ' + fail + ' failed');
process.exit(fail ? 1 : 0);
