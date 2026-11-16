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

  // ---- 任务 2：战斗纯函数 ----

  // 技能表（确切值，逐字来自规格；C19 用小写键对齐 CHARS/charType）
  // cost=法力消耗；dmg=攻击力（普攻为 null，取 totalAtk）；buff/mana 为特殊效果
  const SKILLS = {
    mage: {
      attack:   { name:'普通攻击', cost:0,  dmg:null, type:'attack' },
      fireball: { name:'火球术',   cost:10, dmg:30,   type:'damage' },
      shield:   { name:'法力护盾', cost:20, buff:'shield', amount:3, type:'buff' },
      arcana:   { name:'奥术智慧', cost:0,  mana:30,  type:'mana' },
      blizzard: { name:'暴风雪',   cost:30, dmg:20,   type:'damage' },
    },
    warrior: {
      attack:    { name:'普通攻击', cost:0,  dmg:null, type:'attack' },
      counter:   { name:'格挡反击', cost:10, buff:'counter', amount:1, type:'buff' },
      roar:      { name:'怒吼',     cost:20, buff:'roar',    amount:1, type:'buff' },
      whirlwind: { name:'旋风斩',   cost:20, dmg:30,   type:'damage' },
      execute:   { name:'裁决',     cost:30, type:'execute' },
    },
  };

  // 扁平动作表：测试玩家对象可能不带 charType，按动作 id 直接查（id 跨类唯一，attack 两角色相同）
  const ACTIONS = {};
  (function () {
    for (const cls of Object.keys(SKILLS)) {
      for (const id of Object.keys(SKILLS[cls])) ACTIONS[id] = SKILLS[cls][id];
    }
  })();

  // 玩家总攻 = 基础攻 + 武器加成
  function totalAtk(p) {
    const eq = (p && p.equipment && p.equipment.weapon) || {};
    return (p ? (p.atk || 0) : 0) + (eq.atk || 0);
  }

  // 玩家总防 = 基础防 + 护甲加成
  function totalDef(p) {
    const eq = (p && p.equipment && p.equipment.armor) || {};
    return (p ? (p.def || 0) : 0) + (eq.def || 0);
  }

  function newBattle(playerState, monster) {
    return {
      player: playerState,
      monster: Object.assign({}, monster),
      buff: { shield: 0, counter: 0, roar: 0 },
      over: false,
      playerWon: false,
    };
  }

  // 回合开始：玩家法力 +5，封顶 maxMana
  function startPlayerTurn(battle) {
    const p = battle.player;
    if (typeof p.mana === 'number' && typeof p.maxMana === 'number') {
      p.mana = Math.min(p.maxMana, p.mana + MANA_PER_TURN);
    }
  }

  // 法力是否足够（缺 mana 字段视为可用，C1 守卫）
  function hasMana(p, cost) {
    if (typeof p.mana !== 'number') return true;
    return p.mana >= cost;
  }

  function spendMana(p, cost) {
    if (typeof p.mana === 'number') p.mana = Math.max(0, p.mana - cost);
  }

  // 玩家行动
  function playerAction(battle, actionId, rng) {
    if (typeof rng !== 'function') rng = Math.random;
    const p = battle.player;
    const m = battle.monster;
    const action = ACTIONS[actionId];
    const result = { ok:false, damage:0, isCrit:false, manaCost:0, usedSkill:false, log:'' };
    if (!action) { result.log = '未知动作。'; return result; }

    const cost = action.cost || 0;
    // 法力不足：拦截，不消耗、不生效（C1 缺字段视为可用）
    if (!hasMana(p, cost)) {
      result.ok = false; result.manaCost = 0;
      result.log = '法力不足，无法施放。';
      return result;
    }
    result.manaCost = cost;
    spendMana(p, cost);

    // 伤害型（普攻/技能）
    if (action.type === 'attack' || action.type === 'damage') {
      const baseAtk = action.dmg != null ? action.dmg : totalAtk(p);
      let dmg = calcDamage(baseAtk, m.def);
      let crit = false;
      // 怒吼待发：×3，用后清
      if (battle.buff.roar > 0) { dmg *= 3; battle.buff.roar = 0; }
      // 暴击：10% ×3（在怒吼之后判定，可叠加）
      if (rng() < CRIT_CHANCE) { dmg = applyCrit(dmg, true); crit = true; }
      m.hp -= dmg;
      result.ok = true; result.damage = dmg; result.isCrit = crit;
      result.log = (crit ? '暴击！' : '') + `造成 ${dmg} 点伤害。`;
    } else if (action.type === 'buff') {
      // shield/counter/roar
      battle.buff[action.buff] = (battle.buff[action.buff] || 0) + action.amount;
      result.ok = true;
      result.log = `发动了「${action.name}」。`;
    } else if (action.type === 'mana') {
      // 奥术智慧：回法力，封顶
      if (typeof p.mana === 'number' && typeof p.maxMana === 'number') {
        p.mana = Math.min(p.maxMana, p.mana + action.mana);
      }
      result.ok = true;
      result.log = `「${action.name}」回复法力。`;
    } else if (action.type === 'execute') {
      // 裁决：HP < 上限 20% 处决，否则不生效（仍已消耗法力，C6）
      if (m.hp < m.maxHp * 0.2) {
        m.hp = 0;
        battle.over = true;
        battle.playerWon = true;
        result.ok = true; result.executed = true;
        result.log = '裁决！直接处决了敌人。';
      } else {
        result.ok = true; result.executed = false;
        result.log = '裁决未生效（敌人血量未低于 20%）。';
      }
    }

    // 战斗结束判定
    if (m.hp <= 0) { battle.over = true; battle.playerWon = true; }
    if (typeof p.hp === 'number' && p.hp <= 0) { battle.over = true; battle.playerWon = false; }
    return result;
  }

  // 怪物回合
  function monsterTurn(battle, rng) {
    if (typeof rng !== 'function') rng = Math.random;
    const p = battle.player;
    const m = battle.monster;
    const usedSkill = rng() < 0.5;
    const rawAtk = usedSkill ? (m.skillDmg || m.atk) : m.atk;
    const rawDmg = calcDamage(rawAtk, totalDef(p));
    let damage = rawDmg;

    if (battle.buff.shield > 0) {
      // 护盾：免疫伤害，回合数 -1
      damage = 0;
      battle.buff.shield -= 1;
    } else if (battle.buff.counter > 0) {
      // 格挡反击：本次伤害 0，反伤怪物等额
      damage = 0;
      battle.buff.counter = 0;
      m.hp -= rawDmg;
    }

    // 扣玩家 HP（缺字段不崩溃）
    if (typeof p.hp === 'number') p.hp = Math.max(0, p.hp - damage);

    // 战斗结束判定
    if (m.hp <= 0) { battle.over = true; battle.playerWon = true; }
    if (typeof p.hp === 'number' && p.hp <= 0) { battle.over = true; battle.playerWon = false; }
    return { damage, usedSkill, log: usedSkill ? '怪物使用技能。' : '怪物普通攻击。' };
  }

  // 战斗结束：回满玩家法力
  function endCombat(battle) {
    const p = battle.player;
    if (typeof p.maxMana === 'number') {
      p.mana = p.maxMana;
    }
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
    SKILLS,
    newBattle,
    totalAtk,
    totalDef,
    startPlayerTurn,
    playerAction,
    monsterTurn,
    endCombat,
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = GameLogic;
  else global.GameLogic = GameLogic;
})(typeof self !== 'undefined' ? self : this);
