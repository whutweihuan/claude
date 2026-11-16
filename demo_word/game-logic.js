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

  // ---- 任务 3：奖励 / 装备槽 / HP 经济纯函数 ----

  // 总智力 = 基础智力 + 饰品智力（C22：探索判定与面板一律用总智力）
  function totalIntel(p) {
    const eq = (p && p.equipment && p.equipment.trinket) || {};
    return (p ? (p.intel || 0) : 0) + (eq.intel || 0);
  }

  // 属性成长：atk/def/intel 直接加；hpMax 提升上限并回满 HP
  function applyStatReward(player, reward) {
    if (!reward || typeof reward.amount !== 'number') return;
    if (reward.kind === 'hpMax') {
      player.maxHp = (player.maxHp || 0) + reward.amount;
      if (typeof player.hp === 'number') player.hp = player.maxHp; // 回满
    } else if (reward.kind === 'atk' || reward.kind === 'def' || reward.kind === 'intel') {
      player[reward.kind] = (player[reward.kind] || 0) + reward.amount;
    }
  }

  // 装备槽数值：weapon→atk，armor→def，trinket→intel+回法力（同槽比较用，C23 严格更高才换）
  function equipValue(item) {
    return (item.atk || 0) + (item.def || 0) + (item.intel || 0) + (item.manaRegen || 0);
  }

  // 装备入槽：同槽旧装备数值严格更高则丢弃，否则替换
  function applyEquipment(player, item) {
    if (!item || !item.slot) return;
    if (!player.equipment) player.equipment = {};
    const old = player.equipment[item.slot];
    if (old && equipValue(old) >= equipValue(item)) return; // 同值/更低 → 丢弃
    player.equipment[item.slot] = item;
  }

  // 随机整数 [a,b]（rng ∈ [0,1)）
  function ri(rng, a, b) {
    return a + Math.floor(rng() * (b - a + 1));
  }

  // 掉落：50/50 属性成长或装备（C20 结构，UI 按 type 路由）
  function rollReward(rng) {
    if (typeof rng !== 'function') rng = Math.random;
    if (rng() < 0.5) {
      // 属性成长
      const kinds = ['atk', 'def', 'hpMax', 'intel'];
      const kind = kinds[Math.floor(rng() * kinds.length)];
      let amount;
      if (kind === 'atk') amount = ri(rng, 1, 3);
      else if (kind === 'def') amount = ri(rng, 1, 2);
      else if (kind === 'hpMax') amount = ri(rng, 10, 20);
      else amount = 1; // intel +1
      return { type:'stat', kind, amount };
    }
    // 装备
    const slots = ['weapon', 'armor', 'trinket'];
    const slot = slots[Math.floor(rng() * slots.length)];
    if (slot === 'weapon') {
      const atk = ri(rng, 2, 6);
      const names = ['铁剑', '钢剑', '银剑', '秘银剑', '魔纹剑'];
      return { type:'equipment', slot, name: names[atk - 2], atk };
    }
    if (slot === 'armor') {
      const def = ri(rng, 1, 4);
      const names = ['皮甲', '锁子甲', '板甲', '龙鳞甲'];
      return { type:'equipment', slot, name: names[def - 1], def };
    }
    // trinket：+智力 1~2 或 每层回法（C21 值 5）
    if (rng() < 0.5) {
      const intel = ri(rng, 1, 2);
      const names = ['智慧戒', '贤者符'];
      return { type:'equipment', slot, name: names[intel - 1], intel };
    }
    return { type:'equipment', slot, name:'法力水晶', manaRegen: 5 };
  }

  // 路由：按 reward.type 落到对应 apply（C20）
  function applyReward(player, reward) {
    if (!reward) return;
    if (reward.type === 'stat') applyStatReward(player, reward);
    else if (reward.type === 'equipment') applyEquipment(player, reward);
  }

  // 每层回血 = floor(maxHp × 25%)，封顶（C24 取整）
  function healOnNewFloor(player) {
    if (typeof player.hp !== 'number' || typeof player.maxHp !== 'number') return;
    const heal = Math.floor(player.maxHp * 0.25);
    player.hp = Math.min(player.maxHp, player.hp + heal);
  }

  // 探索成功：+10~15 HP，封顶（rng 可选，默认 Math.random）
  function healExploreSuccess(player, rng) {
    if (typeof rng !== 'function') rng = Math.random;
    if (typeof player.hp !== 'number' || typeof player.maxHp !== 'number') return;
    const heal = ri(rng, 10, 15);
    player.hp = Math.min(player.maxHp, player.hp + heal);
  }

  // 祭坛（C14）：pray = 法力 +30 封顶；risk = 50/50 大奖励或 10~20 伤害
  function healAltar(player, rng, mode) {
    if (typeof rng !== 'function') rng = Math.random;
    if (mode === undefined) mode = 'pray';
    const out = { healed: 0, manaHealed: 0, riskTaken: mode === 'risk', reward: null, log: '' };
    if (mode === 'pray') {
      if (typeof player.mana === 'number' && typeof player.maxMana === 'number') {
        const before = player.mana;
        player.mana = Math.min(player.maxMana, player.mana + 30);
        out.manaHealed = player.mana - before;
      }
      out.log = '你在祭坛祈祷，法力得到恢复。';
    } else {
      if (rng() < 0.5) {
        const reward = rollReward(rng);
        const hpBefore = typeof player.hp === 'number' ? player.hp : 0;
        applyReward(player, reward);
        out.reward = reward;
        if (typeof player.hp === 'number') out.healed = Math.max(0, player.hp - hpBefore);
        out.log = '祭坛回应了你的冒险，赐予你奖励！';
      } else {
        const dmg = ri(rng, 10, 20);
        if (typeof player.hp === 'number') player.hp = Math.max(0, player.hp - dmg);
        out.log = `祭坛的诅咒击中你，受到 ${dmg} 点伤害！`;
      }
    }
    return out;
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
    totalIntel,
    startPlayerTurn,
    playerAction,
    monsterTurn,
    endCombat,
    applyStatReward,
    applyEquipment,
    applyReward,
    rollReward,
    healOnNewFloor,
    healExploreSuccess,
    healAltar,
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = GameLogic;
  else global.GameLogic = GameLogic;
})(typeof self !== 'undefined' ? self : this);
