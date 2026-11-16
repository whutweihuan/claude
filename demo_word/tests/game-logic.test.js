const test = require('node:test');
const assert = require('node:assert');
const GL = require('../game-logic.js');

test('calcDamage 下限为 1（攻 ≤ 防不打负）', () => {
  assert.equal(GL.calcDamage(5, 10), 1);
  assert.equal(GL.calcDamage(15, 10), 5);
  assert.equal(GL.calcDamage(30, 3), 27);
});

test('applyCrit 暴击 = 3×，非暴击不变', () => {
  assert.equal(GL.applyCrit(27, true), 81);
  assert.equal(GL.applyCrit(27, false), 27);
});

test('MANA_PER_TURN = 5', () => {
  assert.equal(GL.MANA_PER_TURN, 5);
});

test('explorationPoints = 骰值 + 智力', () => {
  assert.equal(GL.explorationPoints(8, 6), 14);
  assert.equal(GL.explorationPoints(5, 1), 6);
});

test('rollExploration 成功需严格大于难度 X（points === X 为失败）', () => {
  // 用固定 rng 与固定 difficulty 便于断言：直接测判定函数
  assert.equal(GL.judgeExploration(13, 13), false); // 13 > 13 为假
  assert.equal(GL.judgeExploration(14, 13), true);  // 14 > 13 为真
  assert.equal(GL.judgeExploration(9, 13), false);  // 9 > 13 为假
});

test('rollExploration 返回结构且难度在 [9,13]', () => {
  let ok = true;
  for (let i = 0; i < 200; i++) {
    const r = GL.rollExploration(8, Math.random);
    if (!(r.difficulty >= 9 && r.difficulty <= 13)) ok = false;
    if (!(r.roll >= 1 && r.roll <= 6)) ok = false;
    if (typeof r.success !== 'boolean') ok = false;
  }
  assert.ok(ok);
});

// ===== 任务 2：战斗纯函数 =====

const M = () => ({ name:'测试怪', hp:50, maxHp:50, atk:10, def:2, skillDmg:20 });

test('playerAction 普攻 = 总攻 - 怪物防，下限 1', () => {
  const b = GL.newBattle({ atk:15, def:5, intel:5, equipment:{} }, M());
  const r = GL.playerAction(b, 'attack', () => 0.9); // 0.9 → 非暴击
  assert.equal(r.damage, 13); // 15 - 2
  assert.equal(r.isCrit, false);
});

test('playerAction 技能 fireball 伤害 = 30 - 怪物防', () => {
  const b = GL.newBattle({ atk:5, def:5, intel:8, equipment:{} }, M());
  const r = GL.playerAction(b, 'fireball', () => 0.9);
  assert.equal(r.damage, 28); // 30 - 2
  assert.equal(r.manaCost, 10);
});

test('暴击 3×（rng < 0.1 触发）', () => {
  const b = GL.newBattle({ atk:15, def:5, intel:5, equipment:{} }, M());
  const r = GL.playerAction(b, 'attack', () => 0.05); // 0.05 < 0.1 → 暴击
  assert.equal(r.damage, 13 * 3);
  assert.equal(r.isCrit, true);
});

test('法力不足时技能不可用（不消耗、不生效、不造成伤害）', () => {
  const p = { atk:5, def:5, intel:8, mana:5, maxMana:100, equipment:{} };
  const b = GL.newBattle(p, M());
  const r = GL.playerAction(b, 'fireball', () => 0.9); // 需 10 法力，只有 5
  assert.equal(r.ok, false);
  assert.equal(r.manaCost, 0);
  assert.equal(b.player.mana, 5);
  assert.equal(b.monster.hp, 50);
});

test('法力护盾 3 回合免疫：护盾期间受击伤害 = 0', () => {
  const p = { atk:5, def:5, intel:8, mana:100, maxMana:100, equipment:{} };
  const b = GL.newBattle(p, M());
  GL.playerAction(b, 'shield', () => 0.9); // 加护盾
  const hit1 = GL.monsterTurn(b, () => 0.9);
  const hit2 = GL.monsterTurn(b, () => 0.9);
  assert.equal(hit1.damage, 0);
  assert.equal(hit2.damage, 0);
  assert.equal(b.buff.shield, 1); // 3 - 2
});

test('格挡反击：格挡下次伤害 = 0 且等量反伤怪物', () => {
  const p = { atk:15, def:5, intel:5, mana:100, maxMana:50, equipment:{} };
  const b = GL.newBattle(p, M()); // 怪物攻 10，def 2 → 普攻伤害 = max(1,10-5)=5
  GL.playerAction(b, 'counter', () => 0.9);
  const m = b.monster.hp;
  const hit = GL.monsterTurn(b, () => 0.9); // 怪物普攻 5 被格挡
  assert.equal(hit.damage, 0);
  assert.equal(b.monster.hp, m - 5); // 反伤 5
});

test('怒吼：下次攻击 ×3，用后失效', () => {
  const p = { atk:15, def:5, intel:5, mana:100, maxMana:50, equipment:{} };
  const b = GL.newBattle(p, M());
  GL.playerAction(b, 'roar', () => 0.9);
  const r = GL.playerAction(b, 'attack', () => 0.9);
  assert.equal(r.damage, 13 * 3); // 怒吼 ×3
  assert.equal(b.buff.roar, 0);
});

test('怒吼 ×3 与暴击 3× 可叠加（×9）', () => {
  const p = { atk:15, def:5, intel:5, mana:100, maxMana:50, equipment:{} };
  const b = GL.newBattle(p, M());
  GL.playerAction(b, 'roar', () => 0.9);
  const r = GL.playerAction(b, 'attack', () => 0.05); // 暴击
  assert.equal(r.damage, 13 * 3 * 3);
});

test('裁决：处决 HP<20%上限 的敌人；否则不生效', () => {
  const p = { atk:15, def:5, intel:5, mana:100, maxMana:50, equipment:{} };
  const b = GL.newBattle(p, M()); // maxHp 50，20% = 10
  b.monster.hp = 9; // < 10
  const r = GL.playerAction(b, 'execute', () => 0.9);
  assert.equal(b.monster.hp, 0);
  assert.equal(b.over, true);
  assert.equal(b.playerWon, true);
  // 另一局：HP 未低于 20%
  const b2 = GL.newBattle(p, M());
  b2.monster.hp = 30;
  const r2 = GL.playerAction(b2, 'execute', () => 0.9);
  assert.equal(b2.monster.hp, 30);
  assert.equal(r2.executed, false);
});

test('怪物回合：50% 概率用技能(技能伤害值)，否则普攻；均受玩家防御减伤', () => {
  const p = { atk:5, def:5, intel:8, mana:100, maxMana:100, equipment:{} };
  // rng 控制：0.4 → 普攻（<0.5? 定义为 rng<0.5 用技能）；固定验证两种
  const b = GL.newBattle(p, M());
  const normal = GL.monsterTurn(b, () => 0.9); // > 0.5 → 普攻
  assert.equal(normal.usedSkill, false);
  assert.equal(normal.damage, Math.max(1, 10 - 5)); // 5
  const b2 = GL.newBattle(p, M());
  const skill = GL.monsterTurn(b2, () => 0.1); // < 0.5 → 技能
  assert.equal(skill.usedSkill, true);
  assert.equal(skill.damage, Math.max(1, 20 - 5)); // 15
});

test('每回合玩家法力 +5（回合开始），不超过上限', () => {
  const p = { atk:5, def:5, intel:8, mana:98, maxMana:100, equipment:{} };
  const b = GL.newBattle(p, M());
  GL.startPlayerTurn(b); // 应 +5，但封顶 100
  assert.equal(b.player.mana, 100);
});

test('战斗结束回满玩家法力', () => {
  const p = { atk:5, def:5, intel:8, mana:20, maxMana:100, equipment:{} };
  const b = GL.newBattle(p, M());
  b.over = true; b.playerWon = true;
  GL.endCombat(b);
  assert.equal(b.player.mana, 100);
});

// ===== 任务 3：奖励 / 装备 / HP 经济纯函数 =====

test('applyStatReward 属性成长：攻/防/HP上限/智力', () => {
  const p = { atk:5, def:5, intel:8, hp:80, maxHp:100, mana:50, maxMana:100, equipment:{} };
  GL.applyStatReward(p, { kind:'atk', amount:2 });
  assert.equal(p.atk, 7);
  GL.applyStatReward(p, { kind:'hpMax', amount:20 });
  assert.equal(p.maxHp, 120);
  assert.equal(p.hp, 120); // HP 上限奖励回满
});

test('applyEquipment 同槽取更高替换，否则丢弃', () => {
  const p = { atk:5, def:5, intel:8, hp:100, maxHp:100, mana:100, maxMana:100, equipment:{} };
  GL.applyEquipment(p, { slot:'weapon', name:'铁剑', atk:3 });
  assert.equal(p.equipment.weapon.atk, 3);
  GL.applyEquipment(p, { slot:'weapon', name:'木剑', atk:1 }); // 更低 → 丢弃，保留铁剑
  assert.equal(p.equipment.weapon.name, '铁剑');
  assert.equal(p.equipment.weapon.atk, 3);
  GL.applyEquipment(p, { slot:'armor', name:'皮甲', def:2 });
  assert.equal(p.equipment.armor.def, 2);
});

test('totalAtk 计入武器加成', () => {
  const p = { atk:5, equipment:{ weapon:{ name:'铁剑', atk:3 } } };
  assert.equal(GL.totalAtk(p), 8);
});

test('healOnNewFloor 回补上限 25%（不超过上限）', () => {
  const p = { hp:10, maxHp:100, mana:0, maxMana:100 };
  GL.healOnNewFloor(p);
  assert.equal(p.hp, 35); // 10 + 25
  p.hp = 95;
  GL.healOnNewFloor(p);
  assert.equal(p.hp, 100); // 封顶
});

test('healExploreSuccess 探索成功 +10~15，封顶上限', () => {
  const p = { hp:95, maxHp:100 };
  GL.healExploreSuccess(p);
  assert.ok(p.hp >= 100 && p.hp <= 110); // 至少回满
  assert.ok(p.hp <= 100); // 但封顶 100
});

// ===== 任务 4：流程状态机 + 20 层怪物数据 =====

test('newGame 法师初始值正确', () => {
  const s = GL.newGame('mage');
  assert.equal(s.hp, 100); assert.equal(s.maxHp, 100);
  assert.equal(s.mana, 100); assert.equal(s.atk, 5); assert.equal(s.def, 5); assert.equal(s.intel, 8);
  assert.equal(s.floor, 1);
});

test('newGame 战士初始值正确', () => {
  const s = GL.newGame('warrior');
  assert.equal(s.hp, 200); assert.equal(s.mana, 50); assert.equal(s.atk, 15); assert.equal(s.def, 10);
});

test('MONSTERS 有 20 个，第 20 个是最终 Boss', () => {
  assert.equal(GL.MONSTERS.length, 20);
  assert.equal(GL.MONSTERS[19].name, '复苏之影(最终Boss)');
  assert.ok(GL.MONSTERS[19].hp > GL.MONSTERS[0].hp); // 曲线递增
});

test('shouldEncounter：1-2 次探索后必遇怪', () => {
  const s = GL.newGame('mage');
  assert.equal(GL.shouldEncounter(s, 0), false);
  assert.equal(GL.shouldEncounter(s, 1), true);  // ≥1 次探索
  assert.equal(GL.shouldEncounter(s, 2), true);
});

test('advanceFloor 击败怪物后进入下一层，并回补 25% HP', () => {
  const s = GL.newGame('mage');
  s.hp = 10; // 低血
  GL.advanceFloor(s);
  assert.equal(s.floor, 2);
  assert.ok(s.hp >= 35); // 回补 25%
});

test('checkVictory：击败 20 层 Boss → 胜利', () => {
  const s = GL.newGame('mage');
  s.floor = 20;
  assert.equal(GL.checkVictory(s, true), true);  // 20 层且击败
  assert.equal(GL.checkVictory(s, false), false); // 未击败
});

test('checkDefeat：玩家 HP≤0 → 失败', () => {
  const s = GL.newGame('mage');
  s.hp = 0;
  assert.equal(GL.checkDefeat(s), true);
  s.hp = 1;
  assert.equal(GL.checkDefeat(s), false);
});

test('getFloorContent 返回该层怪物与互动元素', () => {
  const c = GL.getFloorContent(1);
  assert.equal(c.monster.name, '洞穴巨鼠');
  assert.ok(Array.isArray(c.interactions));
  assert.ok(c.interactions.length >= 1);
});
