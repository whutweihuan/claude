/* 云岫修仙录 冒烟回归测试
 * 用法：node test/smoke.js
 * 方式：vm.runInNewContext 执行 index.html 内嵌 <script>，
 *       以 document/localStorage/window 桩模拟真实启动路径（Game.init 立即执行），
 *       然后直接驱动各系统断言核心循环。
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
if (!m) { console.error('FAIL: 未找到 <script> 块'); process.exit(1); }

/* ---------- DOM 桩 ---------- */
function makeEl(id) {
  const el = {
    id: String(id),
    textContent: '',
    title: '',
    innerHTML: '',
    disabled: false,
    checked: false,
    offsetWidth: 0,
    dataset: {},
    style: { setProperty() {} },
    children: [],
    parentNode: null,
    listeners: {},
  };
  el.classList = {
    _s: new Set(),
    add(c) { this._s.add(c); },
    remove(c) { this._s.delete(c); },
    contains(c) { return this._s.has(c); },
    toggle(c, force) {
      if (force === undefined) { this._s.has(c) ? this._s.delete(c) : this._s.add(c); }
      else if (force) this._s.add(c);
      else this._s.delete(c);
      return this._s.has(c);
    },
  };
  el.addEventListener = (t, f) => { (el.listeners[t] = el.listeners[t] || []).push(f); };
  el.setAttribute = () => {};
  el.getAttribute = () => null;
  el.appendChild = (ch) => { el.children.push(ch); ch.parentNode = el; return ch; };
  el.remove = () => {
    if (el.parentNode && el.parentNode.children) {
      const i = el.parentNode.children.indexOf(el);
      if (i >= 0) el.parentNode.children.splice(i, 1);
    }
  };
  Object.defineProperty(el, 'firstChild', { get() { return el.children[0] || null; } });
  return el;
}

const elements = {};
const tabs = ['cave', 'quest', 'achv', 'log'].map(k => {
  const t = makeEl('tab-' + k);
  t.dataset.tab = k;
  return t;
});

const documentStub = {
  readyState: 'complete',
  getElementById(id) { return elements[id] || (elements[id] = makeEl(id)); },
  createElement(tag) { return makeEl(tag); },
  createDocumentFragment() { return makeEl('fragment'); },
  querySelectorAll(sel) { return sel === '.tab-btn' ? tabs : []; },
  addEventListener() {},
};

const store = {};
const localStorageStub = {
  getItem(k) { return Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null; },
  setItem(k, v) { store[k] = String(v); },
  removeItem(k) { delete store[k]; },
};

const windowStub = { addEventListener() {} };

const sandbox = {
  document: documentStub,
  localStorage: localStorageStub,
  window: windowStub,
  setTimeout, clearTimeout, setInterval, clearInterval,
  Date, Math, Number, JSON, console,
  __exports: null,
};

const bridge = '\n;__exports = { GameConfig, GameState, NumberFormat, Rates, SaveSystem, GameEngine, ' +
  'CultivationSystem, UpgradeSystem, QuestSystem, AchievementSystem, Effects, UI, Game, ' +
  'addCult, addStone, spendStone, addLog };';

vm.createContext(sandbox);
vm.runInContext(m[1] + bridge, sandbox, { filename: 'xian-inline.js' });

const G = sandbox.__exports;
if (!G) { console.error('FAIL: 桥接导出失败'); process.exit(1); }

/* Game.init 已随启动路径执行（readyState=complete 时立即调用）。
 * 立即停掉引擎定时器，保证后续数值断言只由显式 advance 驱动。 */
G.GameEngine.stop();

let pass = 0, fail = 0;
function ok(name, cond, extra) {
  if (cond) { pass++; console.log('  ok  ' + name); }
  else { fail++; console.log('FAIL  ' + name + (extra !== undefined ? '  [' + extra + ']' : '')); }
}
const near = (a, b) => Math.abs(a - b) < 1e-6;

/* ---------- 1. 启动状态 ---------- */
ok('启动：境界为炼气一层', G.GameState.state.realm.stage === 0);
ok('启动：全新存档无离线收益', G.GameState.state.pendingOffline === null);

/* ---------- 2. 自动产出 ---------- */
const s = G.GameState.state;
G.GameEngine.advance(10);
ok('产出：10 秒修为 = 10（基础 1/秒）', near(s.realm.cult, 10), s.realm.cult);
ok('产出：10 秒灵石 = 5（基础 0.5/秒）', near(s.resources.stone, 5), s.resources.stone);
ok('产出：游戏时长累计 10 秒', near(s.stats.playTimeSec, 10), s.stats.playTimeSec);

/* ---------- 3. 吐纳（首吐纳触发成就 a1，奖励从配置读取） ---------- */
const a1 = G.GameConfig.ACHIEVEMENTS.find(a => a.id === 'a1');
const a1Stone = (a1 && a1.reward && a1.reward.stone) || 0;
const bc0 = s.stats.breathCount;
const cultB3 = s.realm.cult, stoneB3 = s.resources.stone;
const r = G.CultivationSystem.breath();
ok('吐纳：返回收益 {cult:20, stone:4}', near(r.cult, 20) && near(r.stone, 4), JSON.stringify(r));
ok('吐纳：计数 +1', s.stats.breathCount === bc0 + 1);
ok('吐纳：修为 +20', near(s.realm.cult, cultB3 + 20), s.realm.cult);
ok('吐纳：灵石 +4（另加首吐纳成就奖励 ' + a1Stone + '）', near(s.resources.stone, stoneB3 + 4 + a1Stone), s.resources.stone);

/* ---------- 4. 升级：余额不足拒绝 / 余额充足成功 ---------- */
s.resources.stone = 5;
ok('升级：灵石不足时拒绝购买', G.UpgradeSystem.buy('array') === null);
ok('升级：拒绝后灵石不变', near(s.resources.stone, 5), s.resources.stone);
s.resources.stone = 100;
const b = G.UpgradeSystem.buy('array');
ok('升级：购买聚灵阵（0→1 级，10 灵石）', b && b.level === 1 && b.cost === 10, JSON.stringify(b));
ok('升级：灵石扣除 10', near(s.resources.stone, 90), s.resources.stone);
ok('升级：速率提升为 3/秒', near(G.Rates.cultPerSec(), 3), G.Rates.cultPerSec());
s.resources.stone = 1000;
const b2 = G.UpgradeSystem.buy('array');
ok('升级：成本按 1.15^lv 增长（1→2 级 = 12）', b2 && b2.level === 2 && b2.cost === 12, JSON.stringify(b2));
ok('升级：灵石扣除 12', near(s.resources.stone, 988), s.resources.stone);
ok('升级：等级累计 = 2', s.buildings.array === 2, s.buildings.array);

/* ---------- 5. 突破（stage 0→1 炼气二层；首突破触发成就 a2） ---------- */
const a2 = G.GameConfig.ACHIEVEMENTS.find(a => a.id === 'a2');
const a2Cult = (a2 && a2.reward && a2.reward.cult) || 0;
s.realm.cult = 0; s.resources.stone = 0;
ok('突破：条件不足时 canBreak=false', G.CultivationSystem.canBreak() === false);
ok('突破：条件不足时 breakthrough 返回 null', G.CultivationSystem.breakthrough() === null);
const need0 = G.GameConfig.REALMS[0];
s.realm.cult = need0.needCult; s.resources.stone = need0.needStone;
ok('突破：条件满足时 canBreak=true', G.CultivationSystem.canBreak() === true);
const br = G.CultivationSystem.breakthrough();
ok('突破：成功进入「炼气二层」', br && br.name === '炼气二层', JSON.stringify(br));
ok('突破：奖励灵石 = 门槛灵石 * 0.5', near(s.resources.stone, Math.floor(need0.needStone * 0.5)), s.resources.stone);
ok('突破：修为 = 恰好满足后为 0 + 首突破成就奖励 ' + a2Cult, near(s.realm.cult, a2Cult), s.realm.cult);
ok('突破：stage = 1', s.realm.stage === 1, s.realm.stage);
ok('突破：计数 = 1', s.stats.breakthroughCount === 1, s.stats.breakthroughCount);
const need1 = G.GameConfig.REALMS[1];
s.realm.cult = need1.needCult + 50; s.resources.stone = need1.needStone;
const br2 = G.CultivationSystem.breakthrough();
ok('突破：超额修为保留 50', br2 && near(s.realm.cult, 50), s.realm.cult);
ok('突破：进入「' + G.GameConfig.REALMS[2].name + '」', br2 && br2.name === G.GameConfig.REALMS[2].name, br2 && br2.name);

/* ---------- 6. 境界倍率（当前 stage=2） ---------- */
ok('倍率：stage2 = 1 + 2*0.25 = 1.5', near(G.Rates.realmMult(), 1.5), G.Rates.realmMult());

/* ---------- 7. 任务 ---------- */
const q1 = G.GameConfig.QUESTS.find(q => q.id === 'g1');
ok('任务：breathCount>=1 时 g1 可领取', G.QuestSystem.stateOf(q1) === 'done');
const st0 = s.resources.stone;
ok('任务：领取成功', G.QuestSystem.claim('g1') === true);
ok('任务：奖励入账 +20 灵石', near(s.resources.stone, st0 + 20), s.resources.stone);
ok('任务：重复领取被拒', G.QuestSystem.claim('g1') === false);
ok('任务：g1 状态变为已领取', G.QuestSystem.stateOf(q1) === 'claimed');
ok('任务：徽章计数 >= 1（升级达成的 d3 仍可领）', G.QuestSystem.badgeCount() >= 1, G.QuestSystem.badgeCount());

/* ---------- 8. 每日刷新 ---------- */
s.quests.daily.breath = 5;
s.quests.dailyDate = '2000-1-1';
G.QuestSystem.refreshDaily();
ok('每日：日期变化后计数清零', s.quests.daily.breath === 0, s.quests.daily.breath);
ok('每日：dailyDate 更新为今天', /^20\d\d-/.test(s.quests.dailyDate), s.quests.dailyDate);

/* ---------- 9. 成就 ---------- */
ok('成就：首吐纳 a1 已解锁', G.AchievementSystem.isUnlocked('a1'));
ok('成就：首次突破 a2 已解锁', G.AchievementSystem.isUnlocked('a2'));
ok('成就：未满足条件的未解锁', G.AchievementSystem.isUnlocked('a8') === false);

/* ---------- 10. 存档往返 ---------- */
s.realm.cult = 1234.5; s.resources.stone = 77;
G.SaveSystem.save();
G.GameState.reset();
ok('存档：重置后归零', G.GameState.state.realm.cult === 0);
G.SaveSystem.load();
ok('存档：读回修为 1234.5', near(G.GameState.state.realm.cult, 1234.5), G.GameState.state.realm.cult);
ok('存档：读回灵石 77', near(G.GameState.state.resources.stone, 77));
/* 缺字段兜底 */
store[G.GameConfig.SAVE_KEY] = JSON.stringify({ realm: { stage: 3, cult: 1 } });
G.SaveSystem.load();
const sl = G.GameState.state;
ok('存档：缺字段以默认值兜底（buildings 存在）', typeof sl.buildings.array === 'number');
ok('存档：缺字段兜底（stats 存在）', typeof sl.stats.totalCult === 'number');

/* ---------- 11. 离线收益 ---------- */
sl.pendingOffline = null;
sl.lastSaved = Date.now() - 3600 * 1000;   // 1 小时前
/* 传入显式 now = lastSaved + 3600s，使缺口恰为 3600，断言确定化 */
const off = G.SaveSystem.computeOffline((sl.lastSaved + 3600 * 1000) / 1000);
ok('离线：1 小时缺口被计算', off && near(off.seconds, 3600), off && off.seconds);
ok('离线：收益 = 速率 * 时长', off && near(off.cult, G.Rates.cultPerSec() * off.seconds));
const pre = sl.realm.cult;
ok('离线：领取成功', G.SaveSystem.claimOffline() === true);
ok('离线：修为入账', sl.realm.cult > pre, sl.realm.cult);
ok('离线：领取后清空', sl.pendingOffline === null);
ok('离线：二次领取被拒（防重复）', G.SaveSystem.claimOffline() === false);
/* 上限 8h */
sl.lastSaved = Date.now() - 10 * 3600 * 1000;
const off2 = G.SaveSystem.computeOffline(Date.now() / 1000);
ok('离线：超过 8 小时按 8h 封顶', off2 && off2.seconds <= 8 * 3600, off2 && off2.seconds);
/* 短缺口忽略 */
sl.pendingOffline = null;
sl.lastSaved = Date.now() - 2000;
ok('离线：<5 秒缺口忽略', G.SaveSystem.computeOffline(Date.now() / 1000) === null);

/* ---------- 12. 重置 ---------- */
G.SaveSystem.resetAll();
ok('重置：境界归零', G.GameState.state.realm.stage === 0);
ok('重置：资源归零', G.GameState.state.resources.stone === 0);
ok('重置：成就清空', G.GameState.state.achievements.unlocked.length === 0);
ok('重置：存档已清除', store[G.GameConfig.SAVE_KEY] === undefined, String(store[G.GameConfig.SAVE_KEY] === undefined));

/* ---------- 汇总 ---------- */
console.log('\n' + pass + ' passed, ' + fail + ' failed');
process.exit(fail ? 1 : 0);
