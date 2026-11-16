// 地下城跑团游戏 — 核心规则（纯函数，无 DOM）
// UMD：浏览器暴露 window.GameLogic，Node 暴露 module.exports
(function (global) {
  'use strict';

  // ---- 常量 ----
  const MANA_PER_TURN = 5;  // 战斗中玩家每回合开始时法力 +5
  const CRIT_CHANCE = 0.1;  // 玩家所有攻击 10% 暴击
  const CRIT_MULT = 3;      // 暴击 = 3× 伤害

  // ---- 任务 1：基础数值纯函数 ----

  // 伤害 = 攻击力 − 防御力，最低 1（避免 0/负值卡死战斗）
  function calcDamage(atk, def) {
    return Math.max(1, (atk || 0) - (def || 0));
  }

  // 暴击判定在最终伤害值上：基础伤害 ×3
  function applyCrit(baseDamage, isCrit) {
    return isCrit ? baseDamage * CRIT_MULT : baseDamage;
  }

  // 探索点 = 智力 + d6 骰值
  function explorationPoints(intel, roll) {
    return (intel || 0) + roll;
  }

  // 成功需严格大于难度 X（等于为失败）
  function judgeExploration(points, difficulty) {
    return points > difficulty;
  }

  // rollExploration：按序调 rng 两次——先定难度 [9,13]，再掷骰 [1,6]（见决策 C8）
  function rollExploration(intel, rng) {
    if (typeof rng !== 'function') rng = Math.random;
    const difficulty = 9 + Math.floor(rng() * 5); // [9,13]
    const roll = 1 + Math.floor(rng() * 6);       // [1,6]
    const points = explorationPoints(intel, roll);
    return { difficulty, roll, points, success: judgeExploration(points, difficulty) };
  }

  const GameLogic = {
    MANA_PER_TURN,
    CRIT_CHANCE,
    CRIT_MULT,
    calcDamage,
    applyCrit,
    explorationPoints,
    judgeExploration,
    rollExploration,
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = GameLogic;
  else global.GameLogic = GameLogic;
})(typeof self !== 'undefined' ? self : this);
