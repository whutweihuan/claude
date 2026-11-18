/* 云岫修仙录 V2.0 数据层测试（TASK 1）
 * 用法：node test/v2.js
 * 覆盖：配置完整性 / 全新状态默认值 / ResourceSystem / BuffSystem /
 *       V1 存档迁移 / 脏数据净化 / V2 存档往返 / 存档失败反馈
 * 每节独立沙盒（test/harness.js），避免状态串扰；时间戳断言一律显式传入。
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
const toList = (x) => Array.isArray(x) ? x : (x && typeof x === 'object' ? Object.values(x) : []);
const posNums = (o) => o && typeof o === 'object' && Object.keys(o).length > 0 && Object.values(o).every(v => Number.isFinite(v) && v > 0);

/* ---------- 1. 配置完整性 ---------- */
console.log('\n== 1. 配置完整性 ==');
{
  const { G } = fresh();
  const GC = G.GameConfig;
  ok('SAVE_KEY 保持不变', GC.SAVE_KEY === 'yunxiu_xiuxian_save_v1', GC.SAVE_KEY);
  ok('SAVE_VERSION 提升到 2', GC.SAVE_VERSION === 2, GC.SAVE_VERSION);

  const roots = toList(GC.SPIRIT_ROOTS);
  ok('灵根：共 5 个', roots.length === 5, roots.length);
  ok('灵根：均有 name/affects/pct/color', roots.length === 5 && roots.every(r => r && typeof r.name === 'string' && typeof r.affects === 'string' && Number.isFinite(r.pct) && r.pct > 0 && typeof r.color === 'string'));
  const rootAffects = new Set(roots.map(r => r && r.affects));
  ok('灵根：效果覆盖 stone/cult/offline/breath/buildCost', ['stone', 'cult', 'offline', 'breath', 'buildCost'].every(k => rootAffects.has(k)), Array.from(rootAffects).join(','));

  const techs = toList(GC.TECHNIQUES);
  ok('功法：共 3 个', techs.length === 3, techs.length);
  ok('功法：5 级加成表均为正数', techs.length === 3 && techs.every(t => Array.isArray(t.bonuses) && t.bonuses.length === 5 && t.bonuses.every(b => Number.isFinite(b) && b > 0)));
  ok('功法：解锁门槛（境界 + 残卷>0）', techs.length === 3 && techs.every(t => Number.isFinite(t.unlockStage) && t.unlockStage >= 0 && Number.isFinite(t.unlockFragments) && t.unlockFragments > 0));
  ok('功法：TECH_MAX_LEVEL = 5', GC.TECH_MAX_LEVEL === 5, GC.TECH_MAX_LEVEL);
  ok('功法：升级成本 4 档且均为正数', Array.isArray(GC.TECH_UPGRADE_COSTS) && GC.TECH_UPGRADE_COSTS.length === 4 && GC.TECH_UPGRADE_COSTS.every(c => posNums(c)), JSON.stringify(GC.TECH_UPGRADE_COSTS));

  const exps = toList(GC.EXPEDITIONS);
  ok('秘境：共 3 个', exps.length === 3, exps.length);
  ok('秘境：三档时长奖励齐全且为正数', exps.length === 3 && exps.every(e => e && e.rewards && ['short', 'mid', 'long'].every(k => posNums(e.rewards[k]))));
  ok('秘境：解锁境界为 2/9/12 三个档', exps.length === 3 && [2, 9, 12].every(stg => exps.some(e => e.unlockStage === stg)), JSON.stringify(exps.map(e => e && e.unlockStage)));
  const dur = GC.EXPEDITION_DURATIONS;
  ok('秘境：时长 60/300/900 秒', dur && dur.short === 60 && dur.mid === 300 && dur.long === 900, JSON.stringify(dur));

  const pills = toList(GC.PILLS);
  ok('丹药：共 3 种', pills.length === 3, pills.length);
  ok('丹药：cost/效果类型/加成/10 分钟时限齐全', pills.length === 3 && pills.every(p => p && posNums(p.cost) && ['cult', 'breath', 'stone'].includes(p.affects) && Number.isFinite(p.bonusPct) && p.bonusPct > 0 && p.durationMs === 600000), JSON.stringify(pills));
}

/* ---------- 2. 全新状态默认值 ---------- */
console.log('\n== 2. 全新状态默认值 ==');
{
  const { G } = fresh();
  const s = G.GameState.state;
  ok('version = 2', s.version === 2, s.version);
  ok('资源：灵草/妖丹/功法残卷 = 0', s.resources.herbs === 0 && s.resources.demonCores === 0 && s.resources.fragments === 0, JSON.stringify(s.resources));
  ok('灵根：未觉醒 rootId = null', s.cultivation ? s.cultivation.rootId === null : false, JSON.stringify(s.cultivation));
  ok('功法：空表且未装备', s.cultivation && s.cultivation.equippedTechnique === null && typeof s.cultivation.techniques === 'object' && Object.keys(s.cultivation.techniques).length === 0);
  ok('丹房：库存与增益均为空', s.alchemy && Object.keys(s.alchemy.inventory).length === 0 && Object.keys(s.alchemy.activeBuffs).length === 0);
  ok('秘境：无进行中，完成计数 0', s.expedition && s.expedition.active === null && s.expedition.completedCount === 0);
  const stats0 = ['herbsTotal', 'demonCoresTotal', 'fragmentsTotal', 'expeditionsCompleted', 'pillsCrafted', 'pillsUsed'];
  ok('统计：6 个新计数 = 0', stats0.every(k => s.stats[k] === 0), JSON.stringify(stats0.map(k => k + ':' + s.stats[k])));
  const daily0 = ['expedition', 'herbs', 'craft', 'pillUsed'];
  ok('每日：4 个新计数 = 0', daily0.every(k => s.quests.daily[k] === 0), JSON.stringify(s.quests.daily));
}

/* ---------- 3. ResourceSystem ---------- */
console.log('\n== 3. ResourceSystem ==');
{
  const { G } = fresh();
  const s = G.GameState.state;
  const RS = G.ResourceSystem;
  ok('模块存在', !!RS);
  if (RS) {
    ok('add(灵草,5)：入账 + 统计 + 每日计数', RS.add('herbs', 5) === true && s.resources.herbs === 5 && s.stats.herbsTotal === 5 && s.quests.daily.herbs === 5, JSON.stringify([s.resources.herbs, s.stats.herbsTotal, s.quests.daily.herbs]));
    ok('add 拒绝 NaN/负数/Infinity', RS.add('herbs', NaN) === false && RS.add('herbs', -3) === false && RS.add('herbs', Infinity) === false && s.resources.herbs === 5);
    ok('add 拒绝未知资源', RS.add('bogus', 1) === false);
    ok('canAfford：单资源够/不够', RS.canAfford({ herbs: 5 }) === true && RS.canAfford({ herbs: 6 }) === false);
    RS.add('demonCores', 2);
    ok('canAfford：跨资源组合判定', RS.canAfford({ herbs: 3, demonCores: 2 }) === true && RS.canAfford({ herbs: 3, demonCores: 3 }) === false);
    ok('spendCosts：混合扣除成功', RS.spendCosts({ herbs: 3, demonCores: 1 }) === true && s.resources.herbs === 2 && s.resources.demonCores === 1);
    s.resources.herbs = 7; s.resources.demonCores = 1;
    ok('spendCosts：妖丹不足时原子拒绝（灵草不动）', RS.spendCosts({ herbs: 3, demonCores: 5 }) === false && s.resources.herbs === 7 && s.resources.demonCores === 1);
    ok('spend：单资源扣除', RS.spend('herbs', 2) === true && s.resources.herbs === 5);
    ok('costText：含资源名', /灵草/.test(RS.costText({ herbs: 3 })) && /妖丹/.test(RS.costText({ demonCores: 2 })), RS.costText({ herbs: 3, demonCores: 2 }));
  }
}

/* ---------- 4. BuffSystem ---------- */
console.log('\n== 4. BuffSystem ==');
{
  const { G } = fresh();
  const s = G.GameState.state;
  const BS = G.BuffSystem;
  ok('模块存在', !!BS);
  if (BS && s.alchemy) {
    const T0 = Date.now() + 1e9;   // 显式未来时间戳，断言确定化
    s.alchemy.inventory.juqi = 3;
    ok('apply：消耗 1 库存并写入 expiresAt', BS.apply('juqi', T0) === true && s.alchemy.inventory.juqi === 2 && s.alchemy.activeBuffs.cult && near(s.alchemy.activeBuffs.cult.expiresAt, T0 + 600000), JSON.stringify(s.alchemy.activeBuffs));
    ok('getMultiplier：生效窗口内 +30%', near(BS.getMultiplier('cult', T0), 1.3), BS.getMultiplier('cult', T0));
    ok('getMultiplier：无关类型不受影响', near(BS.getMultiplier('stone', T0), 1));
    ok('重复使用：expiresAt 整体刷新且不叠加', BS.apply('juqi', T0 + 100000) === true && near(s.alchemy.activeBuffs.cult.expiresAt, T0 + 100000 + 600000) && near(BS.getMultiplier('cult', T0 + 100000), 1.3), JSON.stringify(s.alchemy.activeBuffs));
    ok('过期后：倍率回落为 1', near(BS.getMultiplier('cult', T0 + 700000), 1), BS.getMultiplier('cult', T0 + 700000));
    BS.update(T0 + 700000);
    ok('update：过期条目被清除', !s.alchemy.activeBuffs.cult, JSON.stringify(s.alchemy.activeBuffs));
    s.alchemy.inventory.nshen = 0;
    ok('库存为 0 时 apply 拒绝', BS.apply('nshen', T0) === false && !s.alchemy.activeBuffs.breath);
    s.alchemy.inventory.nshen = 1;
    ok('breath 类丹药：+50% 生效', BS.apply('nshen', T0) === true && near(BS.getMultiplier('breath', T0), 1.5), BS.getMultiplier('breath', T0));
  }
}

/* ---------- 5. V1 存档迁移 ---------- */
console.log('\n== 5. V1 存档迁移 ==');
{
  const { G, store } = fresh();
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
    lastSaved: Date.now() - 60000
  };
  store[G.GameConfig.SAVE_KEY] = JSON.stringify(v1);
  G.SaveSystem.load();
  const s = G.GameState.state;
  ok('迁移：版本号升为 2', s.version === 2, s.version);
  ok('迁移：旧进度保留（境界/修为/灵石/建筑）', s.realm.stage === 2 && near(s.realm.cult, 888.5) && s.resources.stone === 500 && s.buildings.array === 2 && s.buildings.vein === 1);
  ok('迁移：统计保留', s.stats.totalCult === 5000 && s.stats.breathCount === 30 && s.stats.playTimeSec === 7200);
  ok('迁移：任务领取记录保留', !!s.quests.claimed.g1);
  ok('迁移：旧每日计数保留', s.quests.daily.breath === 3 && s.quests.daily.cult === 90 && s.quests.daily.upgrade === 1);
  ok('迁移：新每日计数补 0', s.quests.daily.expedition === 0 && s.quests.daily.herbs === 0 && s.quests.daily.craft === 0 && s.quests.daily.pillUsed === 0);
  ok('迁移：成就保留', s.achievements.unlocked.includes('a1') && s.achievements.unlocked.includes('a2'));
  ok('迁移：新资源补 0', s.resources.herbs === 0 && s.resources.demonCores === 0 && s.resources.fragments === 0);
  ok('迁移：灵根未觉醒', s.cultivation ? s.cultivation.rootId === null : false);
  ok('迁移：功法空表', s.cultivation && s.cultivation.equippedTechnique === null && Object.keys(s.cultivation.techniques).length === 0);
  ok('迁移：丹房空', s.alchemy && Object.keys(s.alchemy.inventory).length === 0 && Object.keys(s.alchemy.activeBuffs).length === 0);
  ok('迁移：秘境空闲', s.expedition && s.expedition.active === null && s.expedition.completedCount === 0);
}

/* ---------- 6. 脏数据净化 ---------- */
console.log('\n== 6. 脏数据净化 ==');
{
  const { G, store } = fresh();
  const now = Date.now();
  const dirty = {
    version: 2,
    realm: { stage: 2, cult: 100 },
    resources: { stone: 500, herbs: null, demonCores: -5, fragments: 'x' },
    buildings: { array: 1, vein: 0, alchemy: 0 },
    stats: { totalCult: 1, totalStone: 1, breathCount: 1, upgradeCount: 0, breakthroughCount: 0, playTimeSec: 1, herbsTotal: NaN, pillsCrafted: -2 },
    cultivation: { rootId: 'bogus', equippedTechnique: 'taihu', techniques: { qingmu: { unlocked: true, level: 99 }, taihu: { unlocked: false, level: 2 }, thoutu: { unlocked: true, level: 'bad' } } },
    alchemy: { inventory: { juqi: -1, nshen: 2.7 }, activeBuffs: { cult: { pill: 'juqi', expiresAt: now + 600000 }, breath: { pill: 'ghost', expiresAt: now + 600000 } } },
    expedition: { completedCount: -3, active: { id: 'ghost', durKey: 'mid', startedAt: 1, endsAt: 2, rewards: { herbs: 1 }, claimed: true } },
    quests: { claimed: {}, dailyDate: '2000-1-1', daily: { breath: 2 } },
    achievements: { unlocked: [] },
    log: [],
    lastSaved: now
  };
  store[G.GameConfig.SAVE_KEY] = JSON.stringify(dirty);
  G.SaveSystem.load();
  const s = G.GameState.state;
  ok('净化：合法灵石保留，脏资源归 0', s.resources.stone === 500 && s.resources.herbs === 0 && s.resources.demonCores === 0 && s.resources.fragments === 0, JSON.stringify(s.resources));
  ok('净化：统计 NaN/负数归 0', s.stats.herbsTotal === 0 && s.stats.pillsCrafted === 0, JSON.stringify([s.stats.herbsTotal, s.stats.pillsCrafted]));
  ok('净化：非法灵根 → null', s.cultivation ? s.cultivation.rootId === null : false, JSON.stringify(s.cultivation));
  ok('净化：功法等级夹取 1..5，未解锁剔除', s.cultivation && s.cultivation.techniques && s.cultivation.techniques.qingmu && s.cultivation.techniques.qingmu.level === 5 && !('taihu' in s.cultivation.techniques) && s.cultivation.techniques.thoutu && s.cultivation.techniques.thoutu.level === 1, JSON.stringify(s.cultivation && s.cultivation.techniques));
  ok('净化：装备了未解锁功法 → null', s.cultivation ? s.cultivation.equippedTechnique === null : false, s.cultivation && s.cultivation.equippedTechnique);
  ok('净化：丹药库存负数剔除、小数取整', s.alchemy && s.alchemy.inventory && !('juqi' in s.alchemy.inventory) && s.alchemy.inventory.nshen === 2, JSON.stringify(s.alchemy && s.alchemy.inventory));
  ok('净化：合法增益保留、幽灵丹药增益剔除', s.alchemy && s.alchemy.activeBuffs && s.alchemy.activeBuffs.cult && s.alchemy.activeBuffs.cult.pill === 'juqi' && !('breath' in s.alchemy.activeBuffs), JSON.stringify(s.alchemy && s.alchemy.activeBuffs));
  ok('净化：秘境计数与进行中归空', s.expedition && s.expedition.completedCount === 0 && s.expedition.active === null);
  ok('净化：关键数值全部有限', [s.resources.stone, s.resources.herbs, s.stats.totalCult, s.stats.playTimeSec].every(Number.isFinite));
}

/* ---------- 7. V2 存档往返 ---------- */
console.log('\n== 7. V2 存档往返 ==');
{
  const { G } = fresh();
  const s = G.GameState.state;
  const hasV2 = s.cultivation && s.alchemy && s.expedition && s.resources.herbs !== undefined;
  ok('V2 状态字段齐备', !!hasV2);
  if (hasV2) {
    const now = Date.now();
    s.realm.stage = 3; s.realm.cult = 42.5;
    s.resources.stone = 999; s.resources.herbs = 7; s.resources.demonCores = 2; s.resources.fragments = 3;
    s.cultivation.rootId = 'wood';
    s.cultivation.techniques = { qingmu: { unlocked: true, level: 3 } };
    s.cultivation.equippedTechnique = 'qingmu';
    s.alchemy.inventory = { juqi: 2, naling: 1 };
    s.alchemy.activeBuffs = { stone: { pill: 'naling', expiresAt: now + 300000 } };
    s.expedition.completedCount = 3;
    s.expedition.active = { id: 'lingcaogu', durKey: 'mid', startedAt: now - 100000, endsAt: now + 200000, rewards: { herbs: 5, stone: 20 }, claimed: false };
    s.stats.pillsCrafted = 4; s.stats.pillsUsed = 2; s.stats.expeditionsCompleted = 3;
    G.SaveSystem.save();
    G.GameState.reset();
    ok('往返：重置后为新状态', G.GameState.state.realm.stage === 0 && G.GameState.state.resources.herbs === 0);
    G.SaveSystem.load();
    const s2 = G.GameState.state;
    ok('往返：灵根保留', s2.cultivation && s2.cultivation.rootId === 'wood', s2.cultivation && s2.cultivation.rootId);
    ok('往返：功法等级与装备保留', s2.cultivation && s2.cultivation.techniques && s2.cultivation.techniques.qingmu && s2.cultivation.techniques.qingmu.level === 3 && s2.cultivation.equippedTechnique === 'qingmu');
    ok('往返：新资源保留', s2.resources.herbs === 7 && s2.resources.demonCores === 2 && s2.resources.fragments === 3);
    ok('往返：丹药库存保留', s2.alchemy && s2.alchemy.inventory && s2.alchemy.inventory.juqi === 2 && s2.alchemy.inventory.naling === 1);
    ok('往返：增益保留（未来 expiresAt）', s2.alchemy && s2.alchemy.activeBuffs && s2.alchemy.activeBuffs.stone && s2.alchemy.activeBuffs.stone.pill === 'naling' && s2.alchemy.activeBuffs.stone.expiresAt > now);
    ok('往返：秘境进行中保留（奖励快照 + claimed=false）', s2.expedition && s2.expedition.active && s2.expedition.active.id === 'lingcaogu' && s2.expedition.active.rewards && s2.expedition.active.rewards.herbs === 5 && s2.expedition.active.claimed === false && s2.expedition.completedCount === 3);
    ok('往返：新统计保留', s2.stats.pillsCrafted === 4 && s2.stats.pillsUsed === 2 && s2.stats.expeditionsCompleted === 3);
  }
}

/* ---------- 8. 存档失败反馈 ---------- */
console.log('\n== 8. 存档失败反馈 ==');
{
  const { G, documentStub, localStorageStub } = fresh();
  const origSet = localStorageStub.setItem;
  const toasts = documentStub.getElementById('toasts');
  localStorageStub.setItem = () => { throw new Error('QuotaExceededError'); };
  const r1 = G.SaveSystem.save();
  ok('失败：save() 返回 false', r1 === false, String(r1));
  ok('失败：toast 提示一次', toasts.children.length === 1, toasts.children.length);
  const r2 = G.SaveSystem.save();
  ok('失败：连续失败仍返回 false', r2 === false, String(r2));
  ok('失败：连续失败不重复弹 toast', toasts.children.length === 1, toasts.children.length);
  localStorageStub.setItem = origSet;
  ok('恢复：save() 返回 true', G.SaveSystem.save() === true);
  localStorageStub.setItem = () => { throw new Error('QuotaExceededError'); };
  G.SaveSystem.save();
  ok('恢复后再失败：重新提示一次', toasts.children.length === 2, toasts.children.length);
  localStorageStub.setItem = origSet;
}

/* ---------- 汇总 ---------- */
console.log('\n' + pass + ' passed, ' + fail + ' failed');
process.exit(fail ? 1 : 0);
