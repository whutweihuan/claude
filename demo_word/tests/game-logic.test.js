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
