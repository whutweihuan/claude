/* 云岫修仙录 V2.0 TASK 6 测试：任务、成就与系统联动
 * 用法：node test/v2-quests.js
 * 覆盖：新任务配置完整性（成长/每日/挑战 × 灵根/功法/秘境/炼丹）/
 *       新任务进度与领取（未达成不可领 / 达成可领 / 奖励精确入账 / 不可重复领取）/
 *       每日任务跨日重置与重开（含旧每日任务回归）/
 *       新成就（五行初窥/功法入门/秘境探索者/丹道初成/百炉丹师/洞天寻宝人）条件与奖励 /
 *       成就奖励不重复发放 / 存档重载后领取与解锁状态一致（联动场景）
 * 每节独立沙盒（test/harness.js）；任务/成就条目按 metric / cond 查找，
 * 数值目标一律从 GameConfig 读取，不在测试里硬编码。
 */
'use strict';
const { createSandbox } = require('./harness.js');

let pass = 0, fail = 0;
function ok(name, cond, extra) {
  if (cond) { pass++; console.log('  ok  ' + name); }
  else { fail++; console.log('FAIL  ' + name + (extra !== undefined ? '  [' + extra + ']' : '')); }
}
function fresh() {
  const ctx = createSandbox();
  if (!ctx.G) { console.error('FAIL: 桥接导出失败'); process.exit(1); }
  ctx.G.GameEngine.stop();
  return ctx;
}
const T0 = Date.now() + 1e9;

/* 新联动条目（API 面）：metric = 新任务指标名；cond = 新成就条件键 */
const NEW = {
  quests: {
    growth: ['rootAwakened', 'techniqueEquipped', 'expeditionCompleted', 'pillsCrafted'],
    daily: ['dailyExpedition', 'dailyHerbs', 'dailyCraft', 'dailyPillUsed'],
    challenge: ['techMaxLevel', 'demonCoresTotal', 'expeditionsUnlocked', 'techniquesUnlocked'],
  },
  conds: ['root1', 'tech1', 'expedition1', 'pill1', 'pill100', 'demon100'],
  achNames: {
    root1: '五行初窥', tech1: '功法入门', expedition1: '秘境探索者',
    pill1: '丹道初成', pill100: '百炉丹师', demon100: '洞天寻宝人',
  },
};
function qByMetric(G, m) { return G.GameConfig.QUESTS.find(q => q.metric === m); }
function aByCond(G, c) { return G.GameConfig.ACHIEVEMENTS.find(a => a.cond === c); }
/* 预解锁全部成就（可排除一个）：隔离奖励干扰，使 quest/成就 测试各自只断言自己的入账。
 * 必须连旧成就一起排除——setup 的 stage/资源可能满足旧条件（如 stage12 → 金丹大道），
 * 而 claim()/select() 内部会触发 checkAll()，其入账会污染“奖励精确入账”断言。 */
function preUnlockAch(G, exceptId) {
  const s = G.GameState.state;
  for (const a of G.GameConfig.ACHIEVEMENTS) {
    if (a.id !== exceptId && s.achievements.unlocked.indexOf(a.id) === -1) s.achievements.unlocked.push(a.id);
  }
}
/* 通用任务用例：未达成拒绝 → setup 达成 → 领取入账精确 → 重复领取拒绝 */
function runQuestCase(G, metric, setup) {
  const s = G.GameState.state;
  const q = qByMetric(G, metric);
  if (!q) { ok('[' + metric + '] 任务存在', false, 'GameConfig.QUESTS 中未找到该 metric'); return; }
  preUnlockAch(G);
  ok('[' + q.name + '] 未达成时不可领取',
    G.QuestSystem.stateOf(q) === 'todo' && G.QuestSystem.claim(q.id) === false);
  setup(s);
  const done = G.QuestSystem.stateOf(q) === 'done';
  ok('[' + q.name + '] 达成', done, 'stateOf=' + G.QuestSystem.stateOf(q) + ' metric=' + q.metric);
  if (!done) return;
  const before = { cult: s.realm.cult, stone: s.resources.stone };
  const rw = { cult: (q.reward.cult || 0), stone: (q.reward.stone || 0) };
  const r = G.QuestSystem.claim(q.id);
  ok('[' + q.name + '] 领取成功且奖励精确入账',
    r === true && s.realm.cult === before.cult + rw.cult && s.resources.stone === before.stone + rw.stone,
    JSON.stringify([r, s.realm.cult, s.resources.stone, rw]));
  const after = { cult: s.realm.cult, stone: s.resources.stone };
  const again = G.QuestSystem.claim(q.id);
  ok('[' + q.name + '] 不可重复领取',
    again === false && s.realm.cult === after.cult && s.resources.stone === after.stone,
    JSON.stringify([again, s.realm.cult, s.resources.stone]));
}
/* 通用成就用例：未达成不解锁 → setup 达成 → checkAll 解锁且入账精确 → 重复 checkAll 不发放 */
function runAchCase(G, cond, setup) {
  const s = G.GameState.state;
  const a = aByCond(G, cond);
  if (!a) { ok('[' + NEW.achNames[cond] + '] 成就存在', false, 'GameConfig.ACHIEVEMENTS 中未找到该 cond'); return; }
  preUnlockAch(G, a.id);
  ok('[' + a.name + '] 未达成不解锁', !G.AchievementSystem.isUnlocked(a.id));
  setup(s);
  const before = { cult: s.realm.cult, stone: s.resources.stone };
  const rw = { cult: (a.reward.cult || 0), stone: (a.reward.stone || 0) };
  const changed = G.AchievementSystem.checkAll();
  ok('[' + a.name + '] 达成后解锁且奖励精确入账',
    changed === true && G.AchievementSystem.isUnlocked(a.id) &&
    s.realm.cult === before.cult + rw.cult && s.resources.stone === before.stone + rw.stone,
    JSON.stringify([changed, s.achievements.unlocked, s.realm.cult, s.resources.stone, rw]));
  const again = G.AchievementSystem.checkAll();
  ok('[' + a.name + '] 重复 checkAll 不再发放',
    again === false && s.realm.cult === before.cult + rw.cult && s.resources.stone === before.stone + rw.stone,
    JSON.stringify([again, s.realm.cult, s.resources.stone]));
}

/* ---------- 1. 新任务/成就配置完整性 ---------- */
console.log('\n== 1. 新任务/成就配置完整性 ==');
{
  const { G } = fresh();
  for (const cat of ['growth', 'daily', 'challenge']) {
    for (const m of NEW.quests[cat]) {
      const q = qByMetric(G, m);
      ok(cat + ' 任务 metric=' + m + ' 存在且字段齐全',
        !!q && q.cat === cat &&
        typeof q.name === 'string' && q.name.length > 0 &&
        typeof q.desc === 'string' && q.desc.length > 0 &&
        Number.isFinite(q.target) && q.target > 0 &&
        q.reward && (q.reward.stone > 0 || q.reward.cult > 0) &&
        Number.isFinite(G.QuestSystem.metric(q.metric)),
        q ? JSON.stringify(q) : '未找到');
    }
  }
  for (const c of NEW.conds) {
    const a = aByCond(G, c);
    ok('成就 ' + NEW.achNames[c] + '（cond=' + c + '）存在且条件可断言',
      !!a && a.name === NEW.achNames[c] &&
      a.reward && (a.reward.stone > 0 || a.reward.cult > 0) &&
      typeof G.AchievementSystem.CONDS[c] === 'function',
      a ? JSON.stringify(a) : '未找到');
  }
}

/* ---------- 2. 新成长任务（真实系统联动驱动） ---------- */
console.log('\n== 2. 新成长任务 ==');
{
  const { G } = fresh();
  runQuestCase(G, 'rootAwakened', s => { G.RootSystem.select('wood'); });
}
{
  const { G } = fresh();
  runQuestCase(G, 'techniqueEquipped', s => {
    s.realm.stage = 2;
    s.resources.fragments = 5;
    G.TechniqueSystem.unlock('qingmu');
  });
}
{
  const { G } = fresh();
  const dur = G.GameConfig.EXPEDITION_DURATIONS.short;
  runQuestCase(G, 'expeditionCompleted', s => {
    s.realm.stage = 2;
    G.ExpeditionSystem.start('lingcaogu', 'short', T0);
    G.ExpeditionSystem.claim(T0 + dur * 1000 + 1);
  });
}
{
  const { G } = fresh();
  const P = G.GameConfig.PILLS;
  runQuestCase(G, 'pillsCrafted', s => {
    s.resources.herbs = P.juqi.cost.herbs;
    G.AlchemySystem.craft('juqi');
  });
}

/* ---------- 3. 新每日任务 ---------- */
console.log('\n== 3. 新每日任务 ==');
{
  const { G } = fresh();
  const dur = G.GameConfig.EXPEDITION_DURATIONS.short;
  runQuestCase(G, 'dailyExpedition', s => {
    s.realm.stage = 2;
    for (let i = 0; i < 2; i++) {
      G.ExpeditionSystem.start('lingcaogu', 'short', T0 + i * 1000);
      G.ExpeditionSystem.claim(T0 + i * 1000 + dur * 1000 + 1);
    }
    ok('两次真实历练：daily.expedition = 2', s.quests.daily.expedition === 2, s.quests.daily.expedition);
  });
}
{
  const { G } = fresh();
  const q = qByMetric(G, 'dailyHerbs');
  if (!q) { ok('每日灵草任务存在', false, '未找到'); }
  else {
    preUnlockAch(G);
    G.ResourceSystem.add('herbs', q.target - 1);
    ok('差 1 株：未达成', G.QuestSystem.stateOf(q) === 'todo', G.QuestSystem.metric('dailyHerbs'));
    G.ResourceSystem.add('herbs', 1);
    runQuestCaseClaimOnly(G, q);
  }
}
{
  const { G } = fresh();
  const P = G.GameConfig.PILLS;
  runQuestCase(G, 'dailyCraft', s => {
    s.resources.herbs = P.juqi.cost.herbs;
    G.AlchemySystem.craft('juqi');
  });
}
{
  const { G } = fresh();
  runQuestCase(G, 'dailyPillUsed', s => {
    s.alchemy.inventory.juqi = 1;
    G.AlchemySystem.use('juqi', T0);
  });
}
/* 跨日重置 + 重开（含旧每日任务 d1 回归） */
{
  const { G } = fresh();
  const q = qByMetric(G, 'dailyExpedition');
  const d1 = G.GameConfig.QUESTS.find(x => x.id === 'd1');
  if (!q) { ok('跨日用例：每日历练任务存在', false, '未找到'); }
  else {
    preUnlockAch(G);
    const s = G.GameState.state;
    s.realm.stage = 2;
    const dur = G.GameConfig.EXPEDITION_DURATIONS.short;
    for (let i = 0; i < q.target; i++) {
      G.ExpeditionSystem.start('lingcaogu', 'short', T0 + i * 1000);
      G.ExpeditionSystem.claim(T0 + i * 1000 + dur * 1000 + 1);
    }
    ok('达成并领取', G.QuestSystem.claim(q.id) === true);
    s.quests.daily.breath = 30;   /* 同时验证旧每日任务 d1 一并重置 */
    s.quests.dailyDate = '1999-01-01';
    G.QuestSystem.refreshDaily();
    ok('跨日：全部每日计数清零（含旧 d1 的 breath）',
      s.quests.daily.expedition === 0 && s.quests.daily.craft === 0 &&
      s.quests.daily.pillUsed === 0 && s.quests.daily.herbs === 0 && s.quests.daily.breath === 0,
      JSON.stringify(s.quests.daily));
    ok('跨日：新/旧每日任务领取标记均清除', s.quests.claimed[q.id] !== true && s.quests.claimed[d1.id] !== true);
    s.quests.daily.expedition = q.target;
    ok('重新达成后可再领取', G.QuestSystem.claim(q.id) === true);
  }
}

/* ---------- 4. 新挑战任务 ---------- */
console.log('\n== 4. 新挑战任务 ==');
{
  const { G } = fresh();
  const q = qByMetric(G, 'techMaxLevel');
  if (!q) { ok('功法大成任务存在', false, '未找到'); }
  else {
    preUnlockAch(G);
    const s = G.GameState.state;
    s.cultivation.techniques.qingmu = { unlocked: true, level: 4 };
    ok('单门 4 级：未达成', G.QuestSystem.stateOf(q) === 'todo', G.QuestSystem.metric('techMaxLevel'));
    s.cultivation.techniques.qingmu = { unlocked: true, level: 3 };
    s.cultivation.techniques.taihu = { unlocked: true, level: 3 };
    ok('两门各 3 级（求和 6）：仍按最高级判定 → 未达成',
      G.QuestSystem.stateOf(q) === 'todo', G.QuestSystem.metric('techMaxLevel'));
    s.cultivation.techniques.qingmu = { unlocked: true, level: 5 };
    runQuestCaseClaimOnly(G, q);
  }
}
{
  const { G } = fresh();
  const q = qByMetric(G, 'demonCoresTotal');
  if (!q) { ok('妖丹百枚任务存在', false, '未找到'); }
  else {
    preUnlockAch(G);
    G.ResourceSystem.add('demonCores', q.target - 1);
    ok('差 1 枚：未达成', G.QuestSystem.stateOf(q) === 'todo', G.QuestSystem.metric('demonCoresTotal'));
    G.ResourceSystem.add('demonCores', 1);
    runQuestCaseClaimOnly(G, q);
  }
}
{
  const { G } = fresh();
  const q = qByMetric(G, 'expeditionsUnlocked');
  if (!q) { ok('秘境全开任务存在', false, '未找到'); }
  else {
    preUnlockAch(G);
    const s = G.GameState.state;
    const E = G.GameConfig.EXPEDITIONS;
    const stages = Object.keys(E).map(id => E[id].unlockStage).sort((a, b) => a - b);
    s.realm.stage = stages[stages.length - 2];
    ok('只解锁 2/3：未达成', G.QuestSystem.stateOf(q) === 'todo', G.QuestSystem.metric('expeditionsUnlocked'));
    s.realm.stage = stages[stages.length - 1];
    runQuestCaseClaimOnly(G, q);
  }
}
{
  const { G } = fresh();
  const q = qByMetric(G, 'techniquesUnlocked');
  if (!q) { ok('功法收藏任务存在', false, '未找到'); }
  else {
    preUnlockAch(G);
    const s = G.GameState.state;
    const ids = Object.keys(G.GameConfig.TECHNIQUES);
    s.cultivation.techniques = {};
    ids.slice(0, ids.length - 1).forEach(id => { s.cultivation.techniques[id] = { unlocked: true, level: 1 }; });
    ok('解锁 2/3：未达成', G.QuestSystem.stateOf(q) === 'todo', G.QuestSystem.metric('techniquesUnlocked'));
    ids.forEach(id => { s.cultivation.techniques[id] = { unlocked: true, level: 1 }; });
    runQuestCaseClaimOnly(G, q);
  }
}
/* 领取入账 + 防重复（上述各用例共用，因 setup 前已部分达成） */
function runQuestCaseClaimOnly(G, q) {
  const s = G.GameState.state;
  ok('[' + q.name + '] 达成', G.QuestSystem.stateOf(q) === 'done', 'metric=' + q.metric);
  if (G.QuestSystem.stateOf(q) !== 'done') return;
  const before = { cult: s.realm.cult, stone: s.resources.stone };
  const rw = { cult: (q.reward.cult || 0), stone: (q.reward.stone || 0) };
  const r = G.QuestSystem.claim(q.id);
  ok('[' + q.name + '] 领取成功且奖励精确入账',
    r === true && s.realm.cult === before.cult + rw.cult && s.resources.stone === before.stone + rw.stone,
    JSON.stringify([r, s.realm.cult, s.resources.stone, rw]));
  const after = { cult: s.realm.cult, stone: s.resources.stone };
  const again = G.QuestSystem.claim(q.id);
  ok('[' + q.name + '] 不可重复领取',
    again === false && s.realm.cult === after.cult && s.resources.stone === after.stone,
    JSON.stringify([again, s.realm.cult, s.resources.stone]));
}

/* ---------- 5. 新成就 ---------- */
console.log('\n== 5. 新成就 ==');
{
  const { G } = fresh();
  runAchCase(G, 'root1', s => { s.cultivation.rootId = 'fire'; });
}
{
  const { G } = fresh();
  runAchCase(G, 'tech1', s => { s.cultivation.techniques.qingmu = { unlocked: true, level: 1 }; });
}
{
  const { G } = fresh();
  runAchCase(G, 'expedition1', s => { s.stats.expeditionsCompleted = 1; });
}
{
  const { G } = fresh();
  runAchCase(G, 'pill1', s => { s.stats.pillsCrafted = 1; });
}
{
  const { G } = fresh();
  const a = aByCond(G, 'pill100');
  if (!a) { ok('百炉丹师存在', false, '未找到'); }
  else {
    const s = G.GameState.state;
    preUnlockAch(G, a.id);
    s.stats.pillsCrafted = 99;
    ok('99 枚：不解锁', G.AchievementSystem.checkAll() === false && !G.AchievementSystem.isUnlocked(a.id));
    s.stats.pillsCrafted = 100;
    const before = { cult: s.realm.cult, stone: s.resources.stone };
    const rw = { cult: (a.reward.cult || 0), stone: (a.reward.stone || 0) };
    ok('100 枚：解锁且奖励精确入账',
      G.AchievementSystem.checkAll() === true && G.AchievementSystem.isUnlocked(a.id) &&
      s.realm.cult === before.cult + rw.cult && s.resources.stone === before.stone + rw.stone,
      JSON.stringify([s.achievements.unlocked, s.realm.cult, s.resources.stone]));
    ok('重复 checkAll 不再发放', G.AchievementSystem.checkAll() === false &&
      s.realm.cult === before.cult + rw.cult && s.resources.stone === before.stone + rw.stone);
  }
}
{
  const { G } = fresh();
  const a = aByCond(G, 'demon100');
  if (!a) { ok('洞天寻宝人存在', false, '未找到'); }
  else {
    const s = G.GameState.state;
    preUnlockAch(G, a.id);
    s.stats.demonCoresTotal = 99;
    ok('99 枚妖丹：不解锁', G.AchievementSystem.checkAll() === false && !G.AchievementSystem.isUnlocked(a.id));
    s.stats.demonCoresTotal = 100;
    const before = { cult: s.realm.cult, stone: s.resources.stone };
    const rw = { cult: (a.reward.cult || 0), stone: (a.reward.stone || 0) };
    ok('100 枚：解锁且奖励精确入账',
      G.AchievementSystem.checkAll() === true && G.AchievementSystem.isUnlocked(a.id) &&
      s.realm.cult === before.cult + rw.cult && s.resources.stone === before.stone + rw.stone,
      JSON.stringify([s.achievements.unlocked, s.realm.cult, s.resources.stone]));
    ok('重复 checkAll 不再发放', G.AchievementSystem.checkAll() === false &&
      s.realm.cult === before.cult + rw.cult && s.resources.stone === before.stone + rw.stone);
  }
}

/* ---------- 6. 联动 + 存档重载一致性 ---------- */
console.log('\n== 6. 联动与存档重载 ==');
{
  const { G } = fresh();
  const q = qByMetric(G, 'rootAwakened');
  const a = aByCond(G, 'root1');
  if (!q || !a) { ok('联动场景：任务+成就均存在', false, '配置缺失'); }
  else {
    const s = G.GameState.state;
    preUnlockAch(G, a.id);   /* 排除被测的 root1（五行初窥），其余成就（含旧成就）全部预解锁 */
    G.RootSystem.select('wood');
    const afterSelect = { stone: s.resources.stone, cult: s.realm.cult };
    ok('觉醒时五行初窥解锁且奖励入账',
      G.AchievementSystem.isUnlocked(a.id) &&
      afterSelect.stone === (a.reward.stone || 0) && afterSelect.cult === (a.reward.cult || 0),
      JSON.stringify([s.achievements.unlocked, afterSelect]));
    ok('领取灵根任务奖励精确入账',
      G.QuestSystem.claim(q.id) === true &&
      s.resources.stone === afterSelect.stone + (q.reward.stone || 0) &&
      s.realm.cult === afterSelect.cult + (q.reward.cult || 0),
      JSON.stringify([s.resources.stone, s.realm.cult]));
    ok('保存成功', G.SaveSystem.save() === true);
    G.GameState.reset();   /* 无返回值，独立语句 */
    G.SaveSystem.load();
    const s2 = G.GameState.state;
    const st = s2.resources.stone, cu = s2.realm.cult;
    ok('重载后灵根保持', s2.cultivation.rootId === 'wood');
    ok('重载后领取标记保留、不可重复领取',
      s2.quests.claimed[q.id] === true && G.QuestSystem.claim(q.id) === false &&
      s2.resources.stone === st && s2.realm.cult === cu,
      JSON.stringify([s2.quests.claimed, s2.resources.stone, s2.realm.cult]));
    ok('重载后 checkAll 不再发放',
      G.AchievementSystem.checkAll() === false && s2.resources.stone === st && s2.realm.cult === cu);
  }
}

/* ---------- 汇总 ---------- */
console.log('\n' + pass + ' passed, ' + fail + ' failed');
process.exit(fail ? 1 : 0);
