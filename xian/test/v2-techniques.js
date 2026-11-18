/* 云岫修仙录 V2.0 TASK 3 测试：功法系统
 * 用法：node test/v2-techniques.js
 * 覆盖：TechniqueSystem 解锁（境界+残卷）/ 装备与自由切换 / 升级≤5（4 档成本）/
 *       Rates 功法倍率（状态 → 数值，含与境界/灵根叠加）/ 持久化往返
 * 每节独立沙盒（test/harness.js）。
 * 解锁门槛与升级成本一律从 GameConfig 读取，不在测试里硬编码数值。
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
/* 预解锁全部成就：隔离成就奖励干扰，使成本断言只测成本扣除。
 * TechniqueSystem 的 unlock/equip/upgrade 内部都会调用 AchievementSystem.checkAll()
 * （见 index.html），首次解锁即触发 a10 功法入门（tech1 → +500 灵石）等成就，
 * 其入账会污染“总成本恰好扣光”类精确断言。 */
function preUnlockAch(G) {
  const s = G.GameState.state;
  for (const a of G.GameConfig.ACHIEVEMENTS) {
    if (s.achievements.unlocked.indexOf(a.id) === -1) s.achievements.unlocked.push(a.id);
  }
}

/* ---------- 1. 解锁（境界 + 残卷） ---------- */
console.log('\n== 1. 功法解锁 ==');
{
  const { G } = fresh();
  const TS = G.TechniqueSystem;
  const s = G.GameState.state;
  ok('模块存在', !!TS);
  if (TS) {
    preUnlockAch(G);
    const t = G.GameConfig.TECHNIQUES.qingmu;
    ok('境界不足：拒绝解锁且状态不动',
      TS.unlock('qingmu') === false && s.cultivation.techniques.qingmu === undefined,
      'stage=' + s.realm.stage);
    s.realm.stage = t.unlockStage;
    s.resources.fragments = 4;
    ok('残卷不足：拒绝解锁且不扣残卷',
      TS.unlock('qingmu') === false && s.resources.fragments === 4 && s.cultivation.techniques.qingmu === undefined);
    s.resources.fragments = 5;
    ok('解锁成功：level=1、自动装备、残卷扣 5',
      TS.unlock('qingmu') === true &&
      s.cultivation.techniques.qingmu && s.cultivation.techniques.qingmu.unlocked === true && s.cultivation.techniques.qingmu.level === 1 &&
      s.cultivation.equippedTechnique === 'qingmu' &&
      s.resources.fragments === 0,
      JSON.stringify({ tech: s.cultivation.techniques, eq: s.cultivation.equippedTechnique, frag: s.resources.fragments }));
    ok('重复解锁被拒（不重复扣残卷）', TS.unlock('qingmu') === false && s.resources.fragments === 0);
    ok('未知功法被拒', TS.unlock('bogus') === false);
  }
}
{
  const { G } = fresh();
  const TS = G.TechniqueSystem;
  const s = G.GameState.state;
  if (TS) {
    preUnlockAch(G);
    const t = G.GameConfig.TECHNIQUES.taihu;
    s.realm.stage = t.unlockStage - 1;
    s.resources.fragments = 99;
    ok('太虚：差一境界时拒绝解锁', TS.unlock('taihu') === false && s.cultivation.techniques.taihu === undefined, 'stage=' + s.realm.stage);
    s.realm.stage = t.unlockStage;
    s.resources.fragments = t.unlockFragments;
    ok('太虚：门槛处解锁、残卷恰好扣光',
      TS.unlock('taihu') === true && s.resources.fragments === 0 && s.cultivation.equippedTechnique === 'taihu');
    const q = G.GameConfig.TECHNIQUES.qingmu;
    s.resources.fragments = q.unlockFragments;
    ok('高阶境界下低门槛功法亦可解锁', TS.unlock('qingmu') === true && s.resources.fragments === 0);
    ok('后解锁者接管装备槽（自动装备）', s.cultivation.equippedTechnique === 'qingmu', s.cultivation.equippedTechnique);
  }
}

/* ---------- 2. 装备 / 自由切换 ---------- */
console.log('\n== 2. 功法装备与切换 ==');
{
  const { G } = fresh();
  const TS = G.TechniqueSystem;
  const s = G.GameState.state;
  if (TS) {
    preUnlockAch(G);
    s.realm.stage = 12;
    s.resources.fragments = 100;
    TS.unlock('qingmu');
    TS.unlock('thoutu');
    const snap = { stone: s.resources.stone, frag: s.resources.fragments, herbs: s.resources.herbs, cores: s.resources.demonCores };
    ok('已解锁功法可自由切换', TS.equip('qingmu') === true && TS.equip('thoutu') === true && s.cultivation.equippedTechnique === 'thoutu');
    ok('自由切换不消耗任何资源',
      s.resources.stone === snap.stone && s.resources.fragments === snap.frag && s.resources.herbs === snap.herbs && s.resources.demonCores === snap.cores,
      JSON.stringify(snap));
    ok('装备未知功法被拒', TS.equip('bogus') === false && s.cultivation.equippedTechnique === 'thoutu');
    ok('装备未解锁功法被拒', TS.equip('taihu') === false && s.cultivation.equippedTechnique === 'thoutu');
    ok('装备槽唯一（始终只有一门）', Object.keys(s.cultivation.techniques).length >= 2 && typeof s.cultivation.equippedTechnique === 'string');
  }
}

/* ---------- 3. 升级（≤5，4 档成本，多资源原子性） ---------- */
console.log('\n== 3. 功法升级 ==');
{
  const { G } = fresh();
  const TS = G.TechniqueSystem;
  const s = G.GameState.state;
  if (TS) {
    preUnlockAch(G);
    const GC = G.GameConfig;
    const c = GC.TECH_UPGRADE_COSTS;
    const t = GC.TECHNIQUES.qingmu;
    s.realm.stage = t.unlockStage;
    s.resources.fragments = t.unlockFragments;
    TS.unlock('qingmu');
    ok('升级未解锁/未知功法 → null', TS.upgrade('bogus') === null && TS.upgrade('taihu') === null);
    /* 档 1：1→2 */
    s.resources.stone = c[0].stone - 1; s.resources.herbs = c[0].herbs;
    ok('档1 灵石差 1 → 拒绝且状态不动',
      TS.upgrade('qingmu') === null && s.resources.stone === c[0].stone - 1 && s.resources.herbs === c[0].herbs);
    s.resources.stone = c[0].stone;
    const u1 = TS.upgrade('qingmu');
    ok('档1：1→2 成功且成本恰好扣光',
      u1 && u1.level === 2 && s.cultivation.techniques.qingmu.level === 2 && s.resources.stone === 0 && s.resources.herbs === 0,
      JSON.stringify([u1, s.resources.stone, s.resources.herbs]));
    /* 档 2：2→3（多资源原子性） */
    s.resources.stone = c[1].stone; s.resources.herbs = c[1].herbs - 1; s.resources.demonCores = c[1].demonCores;
    ok('档2 灵草差 1 → 原子拒绝（灵石/妖丹不动）',
      TS.upgrade('qingmu') === null && s.resources.stone === c[1].stone && s.resources.herbs === c[1].herbs - 1 && s.resources.demonCores === c[1].demonCores);
    s.resources.herbs = c[1].herbs;
    const u2 = TS.upgrade('qingmu');
    ok('档2：2→3 成功（灵石+灵草+妖丹全扣）',
      u2 && u2.level === 3 && s.resources.stone === 0 && s.resources.herbs === 0 && s.resources.demonCores === 0);
    /* 档 3 / 档 4 */
    s.resources.stone = c[2].stone; s.resources.herbs = c[2].herbs; s.resources.demonCores = c[2].demonCores;
    ok('档3：3→4 成功', TS.upgrade('qingmu') !== null && s.cultivation.techniques.qingmu.level === 4 && s.resources.stone === 0);
    s.resources.stone = c[3].stone; s.resources.herbs = c[3].herbs; s.resources.demonCores = c[3].demonCores;
    const u4 = TS.upgrade('qingmu');
    ok('档4：4→5 成功', u4 && u4.level === 5 && s.cultivation.techniques.qingmu.level === 5);
    s.resources.stone = 99999; s.resources.herbs = 99999; s.resources.demonCores = 99999;
    ok('满级 5：拒绝升级且资源不动',
      TS.upgrade('qingmu') === null && s.cultivation.techniques.qingmu.level === 5 && s.resources.stone === 99999);
  }
}
{
  const { G } = fresh();
  const TS = G.TechniqueSystem;
  if (TS) {
    preUnlockAch(G);
    const s = G.GameState.state;
    const GC = G.GameConfig;
    const t = GC.TECHNIQUES.taihu;
    const total = { stone: 0, herbs: 0, demonCores: 0 };
    for (const tier of GC.TECH_UPGRADE_COSTS) for (const k of Object.keys(total)) total[k] += (tier[k] || 0);
    s.realm.stage = t.unlockStage;
    s.resources.fragments = t.unlockFragments;
    s.resources.stone = total.stone; s.resources.herbs = total.herbs; s.resources.demonCores = total.demonCores;
    TS.unlock('taihu');
    let all = true;
    for (let lv = 1; lv < GC.TECH_MAX_LEVEL; lv++) { if (!TS.upgrade('taihu')) { all = false; break; } }
    ok('连升 4 级：总成本恰好扣光、满级 5',
      all && s.cultivation.techniques.taihu.level === 5 && s.resources.stone === 0 && s.resources.herbs === 0 && s.resources.demonCores === 0,
      JSON.stringify(s.resources));
  }
}

/* ---------- 4. 功法 → Rates 倍率（状态 → 数值） ---------- */
console.log('\n== 4. 功法 → Rates 倍率 ==');
{
  const { G } = fresh();
  const s = G.GameState.state;
  s.cultivation.techniques = {
    qingmu: { unlocked: true, level: 1 },
    taihu:  { unlocked: true, level: 2 },
    thoutu: { unlocked: true, level: 3 },
  };
  const q = G.GameConfig.TECHNIQUES.qingmu, th = G.GameConfig.TECHNIQUES.taihu, tt = G.GameConfig.TECHNIQUES.thoutu;
  s.cultivation.equippedTechnique = 'qingmu';
  ok('青木 Lv1：修为/秒 ×(1+' + q.bonuses[0] + '%)', near(G.Rates.cultPerSec(), 1.0 * (1 + q.bonuses[0] / 100)), G.Rates.cultPerSec());
  ok('青木：灵石/秒不受影响', near(G.Rates.stonePerSec(), 0.5));
  s.cultivation.equippedTechnique = 'thoutu';
  ok('厚土 Lv3：灵石/秒 ×(1+' + tt.bonuses[2] + '%)', near(G.Rates.stonePerSec(), 0.5 * (1 + tt.bonuses[2] / 100)), G.Rates.stonePerSec());
  ok('厚土：修为/秒不受影响', near(G.Rates.cultPerSec(), 1.0));
  s.cultivation.equippedTechnique = 'taihu';
  ok('太虚 Lv2：吐纳修为/灵石 ×(1+' + th.bonuses[1] + '%)',
    near(G.Rates.breathCult(), 20 * (1 + th.bonuses[1] / 100)) && near(G.Rates.breathStone(), 4 * (1 + th.bonuses[1] / 100)),
    JSON.stringify([G.Rates.breathCult(), G.Rates.breathStone()]));
  s.cultivation.equippedTechnique = null;
  ok('未装备：已解锁功法不生效', near(G.Rates.cultPerSec(), 1.0) && near(G.Rates.stonePerSec(), 0.5) && near(G.Rates.breathCult(), 20));
  s.cultivation.equippedTechnique = 'qingmu';
  s.cultivation.techniques.qingmu.level = 5;
  ok('青木 Lv5：×(1+' + q.bonuses[4] + '%)', near(G.Rates.cultPerSec(), 1.0 * (1 + q.bonuses[4] / 100)), G.Rates.cultPerSec());
  s.realm.stage = 2;
  ok('与境界叠加（乘性，stage2 ×1.5）', near(G.Rates.cultPerSec(), 1.0 * 1.5 * (1 + q.bonuses[4] / 100)), G.Rates.cultPerSec());
  s.realm.stage = 0;
  s.cultivation.rootId = 'wood';
  ok('与木灵根叠加（×1.12）', near(G.Rates.cultPerSec(), 1.0 * 1.12 * (1 + q.bonuses[4] / 100)), G.Rates.cultPerSec());
}

/* ---------- 5. 持久化往返 ---------- */
console.log('\n== 5. 持久化 ==');
{
  const { G } = fresh();
  const TS = G.TechniqueSystem;
  if (TS) {
    preUnlockAch(G);
    const s = G.GameState.state;
    const t = G.GameConfig.TECHNIQUES.qingmu;
    s.realm.stage = t.unlockStage;
    s.resources.fragments = t.unlockFragments;
    const unlocked = TS.unlock('qingmu') === true;
    const svd = G.SaveSystem.save() === true;
    G.GameState.reset();   /* 注意：reset() 无返回值，独立语句 */
    const freshEmpty = G.GameState.state.cultivation.techniques.qingmu === undefined && G.GameState.state.cultivation.equippedTechnique === null;
    G.SaveSystem.load();   /* load() 返回 state 对象 */
    const s2 = G.GameState.state;
    ok('解锁+自动装备：保存 → 重置 → 读回保留',
      unlocked && svd && freshEmpty &&
      s2.cultivation.techniques.qingmu && s2.cultivation.techniques.qingmu.unlocked === true && s2.cultivation.techniques.qingmu.level === 1 &&
      s2.cultivation.equippedTechnique === 'qingmu',
      JSON.stringify(s2.cultivation));
    /* 读回后：qingmu Lv1，资源全 0（残卷在解锁时已扣）→ 档 1 成本买不起，必须拒绝且等级不变 */
    ok('读回后 Lv1 且资源为 0：升级被拒、等级不变',
      TS.upgrade('qingmu') === null && s2.cultivation.techniques.qingmu.level === 1,
      JSON.stringify(s2.resources));
    s2.cultivation.techniques.qingmu.level = 4;
    s2.resources.stone = G.GameConfig.TECH_UPGRADE_COSTS[3].stone;
    s2.resources.herbs = G.GameConfig.TECH_UPGRADE_COSTS[3].herbs;
    s2.resources.demonCores = G.GameConfig.TECH_UPGRADE_COSTS[3].demonCores;
    const u = TS.upgrade('qingmu');
    ok('读回后升级链路正常（4→5）', u && u.level === 5 && s2.cultivation.techniques.qingmu.level === 5, JSON.stringify(u));
  }
}

/* ---------- 汇总 ---------- */
console.log('\n' + pass + ' passed, ' + fail + ' failed');
process.exit(fail ? 1 : 0);
