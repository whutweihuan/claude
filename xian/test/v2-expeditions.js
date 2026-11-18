/* 云岫修仙录 V2.0 TASK 4 测试：秘境历练
 * 用法：node test/v2-expeditions.js
 * 覆盖：start 守卫（境界/单次一个）/ start 成功（真实时间戳 + 奖励快照）/
 *       奖励确定性（以 startedAt 为种子，领取不重掷）/ claim 守卫（禁重复领取）/
 *       claim 成功（按快照精确入账 + 计数 + 清状态）/ 持久化往返 / progress
 * 每节独立沙盒（test/harness.js）；时间戳一律显式传入，不依赖真实时钟。
 * 奖励数值全部从 GameConfig 读取，不在测试里硬编码数值。
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
const T0 = Date.now() + 1e9;
const posInts = (o) => o && typeof o === 'object' && Object.keys(o).length > 0 && Object.values(o).every(v => Number.isInteger(v) && v > 0);
/* 预解锁全部成就：隔离成就奖励干扰，使「按快照精确入账」断言只测快照扣减。
 * ExpeditionSystem.start/claim 内部都会调用 AchievementSystem.checkAll()（见 index.html），
 * 完成首次秘境即触发 a11 秘境探索者（expedition1 → +400 灵石/+400 修为），
 * 高境界 start 还会触发旧境界成就，其入账会污染「资源恰增快照量」精确断言。 */
function preUnlockAch(G) {
  const s = G.GameState.state;
  for (const a of G.GameConfig.ACHIEVEMENTS) {
    if (s.achievements.unlocked.indexOf(a.id) === -1) s.achievements.unlocked.push(a.id);
  }
}

/* ---------- 1. start 守卫 ---------- */
console.log('\n== 1. start 守卫 ==');
{
  const { G } = fresh();
  const ES = G.ExpeditionSystem;
  const s = G.GameState.state;
  ok('模块存在', !!ES);
  if (ES) {
    ok('未知秘境：拒绝且不落记录', ES.start('bogus', 'short', T0) === false && s.expedition.active === null);
    ok('非法时长档：拒绝', ES.start('lingcaogu', 'eternal', T0) === false && s.expedition.active === null);
    s.realm.stage = 1;
    ok('境界不足：拒绝', ES.start('lingcaogu', 'short', T0) === false && s.expedition.active === null);
    s.realm.stage = 2;
    ok('境界达标：开始成功', ES.start('lingcaogu', 'short', T0) === true && s.expedition.active !== null);
    ok('一次一个：进行中阻挡再次开始', ES.start('lingcaogu', 'mid', T0 + 1000) === false && s.expedition.active.startedAt === T0);
    ok('完成未领取：仍阻挡开始新历练', ES.start('lingcaogu', 'long', T0 + 100000) === false && s.expedition.active.startedAt === T0);
  }
}

/* ---------- 2. start 成功：真实时间戳 + 奖励快照 ---------- */
console.log('\n== 2. start 成功 ==');
{
  const { G } = fresh();
  const ES = G.ExpeditionSystem;
  const s = G.GameState.state;
  if (ES) {
    s.realm.stage = 9;
    ES.start('guxiu', 'mid', T0);
    const a = s.expedition.active;
    const cfgDur = G.GameConfig.EXPEDITION_DURATIONS.mid;
    ok('startedAt = 显式时间戳', a && a.startedAt === T0, a && a.startedAt);
    ok('endsAt = 开始 + 配置时长（秒→毫秒）', a && a.endsAt === T0 + cfgDur * 1000, a && a.endsAt);
    const base = G.GameConfig.EXPEDITIONS.guxiu.rewards.mid;
    ok('奖励键与配置一致', a && Object.keys(a.rewards).sort().join(',') === Object.keys(base).sort().join(','), a && JSON.stringify(a.rewards));
    ok('奖励快照：全为正整数', a && posInts(a.rewards), a && JSON.stringify(a.rewards));
    ok('claimed=false；开始不计完成数', a && a.claimed === false && s.expedition.completedCount === 0 && s.stats.expeditionsCompleted === 0);
  }
}

/* ---------- 3. 奖励确定性（以 startedAt 为固定种子） ---------- */
console.log('\n== 3. 奖励确定性 ==');
{
  const { G } = fresh();
  const ES = G.ExpeditionSystem;
  const s = G.GameState.state;
  if (ES) {
    s.realm.stage = 2;
    ES.start('lingcaogu', 'mid', T0);
    const r1 = JSON.stringify(G.GameState.state.expedition.active.rewards);
    const { G: G2 } = fresh();
    G2.GameState.state.realm.stage = 2;
    G2.ExpeditionSystem.start('lingcaogu', 'mid', T0);
    const r2 = JSON.stringify(G2.GameState.state.expedition.active.rewards);
    ok('同参数：奖励可精确复现', r1 === r2, r1 + ' vs ' + r2);
    /* 不同 startedAt → 不同种子 → 奖励应不同（取最大基数 youshan/long，抖动必然产生可见差异） */
    const { G: G3 } = fresh();
    G3.GameState.state.realm.stage = 12;
    G3.ExpeditionSystem.start('youshan', 'long', T0);
    const b1 = JSON.stringify(G3.GameState.state.expedition.active.rewards);
    const { G: G4 } = fresh();
    G4.GameState.state.realm.stage = 12;
    G4.ExpeditionSystem.start('youshan', 'long', T0 + 1000);
    const b2 = JSON.stringify(G4.GameState.state.expedition.active.rewards);
    ok('不同 startedAt：奖励不同（非同一组数）', b1 !== b2, b1 + ' vs ' + b2);
    /* 奖励范围：base × 境界倍率 × (1±jitter) */
    const GC = G.GameConfig;
    const sc = GC.EXPEDITION_REALM_SCALE;
    const stage = 2;
    const m = Math.min(sc.cap, 1 + sc.perStage * stage);
    const base = GC.EXPEDITIONS.lingcaogu.rewards.mid;
    const rw = JSON.parse(r1);
    let inRange = true;
    for (const k of Object.keys(base)) {
      const lo = Math.max(1, base[k] * m * (1 - sc.jitter) - 1);
      const hi = base[k] * m * (1 + sc.jitter) + 1;
      if (!(rw[k] >= lo && rw[k] <= hi)) inRange = false;
    }
    ok('每项奖励落在 base×境界×(1±jitter) 范围内', inRange, r1);
  }
}

/* ---------- 4. claim 守卫 ---------- */
console.log('\n== 4. claim 守卫 ==');
{
  const { G } = fresh();
  const ES = G.ExpeditionSystem;
  const s = G.GameState.state;
  if (ES) {
    ok('无进行中：claim 返回 null', ES.claim(T0) === null);
    s.realm.stage = 2;
    ES.start('lingcaogu', 'short', T0);
    const endsAt = s.expedition.active.endsAt;
    ok('未完成：拒绝领取且记录保留', ES.claim(endsAt - 1) === null && s.expedition.active !== null && s.expedition.active.startedAt === T0);
    ES.claim(endsAt);
    const after = s.resources.stone;
    ok('重复领取：第二次返回 null 且不再入账', ES.claim(endsAt + 1000) === null && s.resources.stone === after);
  }
}

/* ---------- 5. claim 成功：按快照入账 + 计数 + 清状态 ---------- */
console.log('\n== 5. claim 成功 ==');
{
  const { G } = fresh();
  const ES = G.ExpeditionSystem;
  const s = G.GameState.state;
  if (ES) {
    preUnlockAch(G);   /* 隔离 a11（首次完成触发）及旧境界成就奖励，使「恰增快照量」只测入账 */
    s.realm.stage = 12;
    ES.start('youshan', 'short', T0);
    const a = s.expedition.active;
    const snap = { herbs: a.rewards.herbs || 0, demonCores: a.rewards.demonCores || 0, fragments: a.rewards.fragments || 0, stone: a.rewards.stone || 0 };
    const before = {
      herbs: s.resources.herbs, cores: s.resources.demonCores, frag: s.resources.fragments, stone: s.resources.stone,
      done: s.expedition.completedCount, stats: s.stats.expeditionsCompleted, daily: s.quests.daily.expedition,
    };
    const r = ES.claim(a.endsAt);   /* 恰好到点即可领取 */
    ok('返回 {id, 奖励快照}', r && r.id === 'youshan' && JSON.stringify(r.rewards) === JSON.stringify(a.rewards), JSON.stringify(r));
    ok('按快照入账：灵草/妖丹/残卷/灵石各增恰好快照量',
      s.resources.herbs === before.herbs + snap.herbs &&
      s.resources.demonCores === before.cores + snap.demonCores &&
      s.resources.fragments === before.frag + snap.fragments &&
      s.resources.stone === before.stone + snap.stone,
      JSON.stringify([before, snap, s.resources]));
    ok('领取记录：三个计数各 +1',
      s.expedition.completedCount === before.done + 1 &&
      s.stats.expeditionsCompleted === before.stats + 1 &&
      s.quests.daily.expedition === before.daily + 1,
      JSON.stringify([s.expedition.completedCount, s.stats.expeditionsCompleted, s.quests.daily.expedition]));
    ok('领取后清除任务状态（active = null）', s.expedition.active === null);
  }
}

/* ---------- 6. 持久化：奖励快照已保存，领取时不重掷 ---------- */
console.log('\n== 6. 持久化 ==');
{
  const { G } = fresh();
  const ES = G.ExpeditionSystem;
  if (ES) {
    const s = G.GameState.state;
    preUnlockAch(G);   /* 隔离 a11（首次完成触发）奖励，使读回后「按快照入账」只测入账 */
    s.realm.stage = 9;
    ES.start('guxiu', 'mid', T0);
    const savedRewards = JSON.stringify(s.expedition.active.rewards);
    const endsAt = s.expedition.active.endsAt;
    const svd = G.SaveSystem.save() === true;
    G.GameState.reset();   /* 注意：reset() 无返回值，独立语句 */
    const wiped = G.GameState.state.expedition.active === null && G.GameState.state.expedition.completedCount === 0;
    G.SaveSystem.load();   /* load() 返回 state 对象 */
    const s2 = G.GameState.state;
    ok('进行中 + 奖励快照：保存 → 重置 → 读回保留',
      svd && wiped && s2.expedition.active && s2.expedition.active.id === 'guxiu' &&
      s2.expedition.active.startedAt === T0 && JSON.stringify(s2.expedition.active.rewards) === savedRewards,
      s2.expedition.active && JSON.stringify(s2.expedition.active));
    const stoneBefore = s2.resources.stone;
    const r = ES.claim(endsAt);
    ok('读回后领取：按已保存快照入账（不重掷）',
      r && JSON.stringify(r.rewards) === savedRewards && s2.resources.stone === stoneBefore + (r.rewards.stone || 0),
      JSON.stringify(r));
    ok('读回领取后：状态清除、计数 +1', s2.expedition.active === null && s2.expedition.completedCount === 1);
  }
}

/* ---------- 7. progress（UI 进度条/剩余时间数据源） ---------- */
console.log('\n== 7. progress ==');
{
  const { G } = fresh();
  const ES = G.ExpeditionSystem;
  if (ES) {
    ok('无进行中：progress → null', ES.progress(T0) === null);
    const s = G.GameState.state;
    s.realm.stage = 2;
    ES.start('lingcaogu', 'short', T0);
    const p0 = ES.progress(T0);
    ok('刚出发：0%、剩余 60 秒', p0 && p0.done === false && p0.fraction === 0 && p0.remainingSec === G.GameConfig.EXPEDITION_DURATIONS.short, JSON.stringify(p0));
    const pm = ES.progress(T0 + 30000);
    ok('过半：50%、剩余 30 秒', pm && pm.fraction === 0.5 && pm.remainingSec === 30 && pm.done === false, JSON.stringify(pm));
    const pe = ES.progress(T0 + 60000);
    ok('到点：100%、剩余 0、可完成', pe && pe.done === true && pe.remainingSec === 0 && pe.fraction === 1, JSON.stringify(pe));
    const pl = ES.progress(T0 + 100000);
    ok('超时：夹取不越界', pl && pl.done === true && pl.fraction === 1 && pl.remainingSec === 0, JSON.stringify(pl));
  }
}

/* ---------- 汇总 ---------- */
console.log('\n' + pass + ' passed, ' + fail + ' failed');
process.exit(fail ? 1 : 0);
