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

  // ---- 任务 4：流程状态机 + 20 层怪物数据 ----

  // 角色初始值（C19 小写键，与 charType/SKILLS 对齐）
  const CHARS = {
    mage:    { hp:100, maxHp:100, mana:100, maxMana:100, atk:5,  def:5,  intel:8 },
    warrior: { hp:200, maxHp:200, mana:50,  maxMana:50,  atk:15, def:10, intel:5 },
  };

  // 20 层怪物曲线（逐字来自计划；maxHp = hp）
  const MONSTERS = [
    { name:'洞穴巨鼠',       hp:50,  maxHp:50,  atk:7,  def:3,  skillDmg:14 },
    { name:'腐尸',           hp:70,  maxHp:70,  atk:9,  def:4,  skillDmg:18 },
    { name:'幽影蝙蝠',       hp:90,  maxHp:90,  atk:11, def:5,  skillDmg:22 },
    { name:'毒液蛛',         hp:110, maxHp:110, atk:13, def:6,  skillDmg:26 },
    { name:'骷髅守卫',       hp:130, maxHp:130, atk:15, def:7,  skillDmg:30 },
    { name:'嗜血狼',         hp:150, maxHp:150, atk:17, def:8,  skillDmg:34 },
    { name:'地精掠夺者',     hp:170, maxHp:170, atk:19, def:9,  skillDmg:38 },
    { name:'石像鬼',         hp:190, maxHp:190, atk:21, def:10, skillDmg:42 },
    { name:'暗影刺客',       hp:210, maxHp:210, atk:23, def:11, skillDmg:46 },
    { name:'深渊骑士',       hp:230, maxHp:230, atk:25, def:12, skillDmg:50 },
    { name:'毒龙幼崽',       hp:250, maxHp:250, atk:27, def:13, skillDmg:54 },
    { name:'血魔',           hp:270, maxHp:270, atk:29, def:14, skillDmg:58 },
    { name:'亡魂骑士',       hp:290, maxHp:290, atk:31, def:15, skillDmg:62 },
    { name:'熔岩兽',         hp:310, maxHp:310, atk:33, def:16, skillDmg:66 },
    { name:'虚空行者',       hp:330, maxHp:330, atk:35, def:17, skillDmg:70 },
    { name:'冰霜巨人',       hp:350, maxHp:350, atk:37, def:18, skillDmg:74 },
    { name:'堕落天使',       hp:370, maxHp:370, atk:39, def:19, skillDmg:78 },
    { name:'龙裔',           hp:390, maxHp:390, atk:41, def:20, skillDmg:82 },
    { name:'深渊领主',       hp:410, maxHp:410, atk:43, def:21, skillDmg:86 },
    { name:'复苏之影(最终Boss)', hp:480, maxHp:480, atk:48, def:24, skillDmg:96 },
  ];

  // 新建游戏状态
  function newGame(charType) {
    const c = CHARS[charType] || CHARS.mage;
    return {
      charType: CHARS[charType] ? charType : 'mage',
      hp: c.hp, maxHp: c.maxHp,
      mana: c.mana, maxMana: c.maxMana,
      atk: c.atk, def: c.def, intel: c.intel,
      floor: 1,
      exploredThisFloor: 0,
      equipment: {},
      over: false,
      won: false,
    };
  }

  // 必遇怪：≥1 次探索后遭遇变为必选（C3）
  function shouldEncounter(state, exploredCount) {
    return exploredCount >= 1;
  }

  // 进入下一层：层数 +1、重置探索计数、回补 25% HP、饰品回法（C21）、超 20 层标记结束
  function advanceFloor(state) {
    state.floor += 1;
    state.exploredThisFloor = 0;
    healOnNewFloor(state);
    const trinket = (state.equipment && state.equipment.trinket) || {};
    if (typeof trinket.manaRegen === 'number' && typeof state.mana === 'number' && typeof state.maxMana === 'number') {
      state.mana = Math.min(state.maxMana, state.mana + trinket.manaRegen);
    }
    if (state.floor > 20) state.over = true;
  }

  // 胜利：第 20 层且击败该层怪物
  function checkVictory(state, monsterDefeated) {
    return state.floor === 20 && monsterDefeated;
  }

  // 失败：玩家 HP ≤ 0
  function checkDefeat(state) {
    return state.hp <= 0;
  }

  // 该层内容：怪物 + 1~3 个互动元素 id（rng 可选，C9）
  function getFloorContent(floor, rng) {
    if (typeof rng !== 'function') rng = Math.random;
    const monster = MONSTERS[floor - 1] || MONSTERS[0];
    const pool = ['box', 'puzzle', 'rps', 'altar', 'trap'];
    const count = 1 + Math.floor(rng() * 3); // 1~3 个
    const picks = [];
    const avail = pool.slice();
    while (picks.length < count && avail.length > 0) {
      const idx = Math.floor(rng() * avail.length);
      picks.push(avail.splice(idx, 1)[0]);
    }
    return { monster, interactions: picks };
  }

  // ---- C4：互动判定纯函数（rng 注入，UI 只调用不内联概率）----

  // 箱子（C10）：20% 概率陷阱（5~10 伤害），否则获得 rollReward 奖励
  function openBox(player, rng) {
    if (typeof rng !== 'function') rng = Math.random;
    const out = { trapped: false, reward: null, log: '' };
    if (rng() < 0.2) {
      const dmg = ri(rng, 5, 10);
      if (typeof player.hp === 'number') player.hp = Math.max(0, player.hp - dmg);
      out.trapped = true;
      out.log = `箱子里藏着陷阱，你受到 ${dmg} 点伤害！`;
    } else {
      out.reward = rollReward(rng);
      applyReward(player, out.reward);
      out.log = '箱子里有一份奖励！';
    }
    return out;
  }

  // 谜题机关（C11）：50/50，成功得奖励，失败 5~10 伤害
  function solvePuzzle(player, rng) {
    if (typeof rng !== 'function') rng = Math.random;
    const out = { solved: false, reward: null, log: '' };
    if (rng() < 0.5) {
      out.solved = true;
      out.reward = rollReward(rng);
      applyReward(player, out.reward);
      out.log = '你破解了谜题机关，获得奖励！';
    } else {
      const dmg = ri(rng, 5, 10);
      if (typeof player.hp === 'number') player.hp = Math.max(0, player.hp - dmg);
      out.log = `谜题机关反噬，你受到 ${dmg} 点伤害！`;
    }
    return out;
  }

  // 猜拳石像（C12）：出招 1=石 2=布 3=剪；怪物出招 1+floor(rng*3)；赢奖励、输 5~10 伤害、平局无事
  function playRps(player, playerMove, rng) {
    if (typeof rng !== 'function') rng = Math.random;
    const monsterMove = 1 + Math.floor(rng() * 3);
    const out = { monsterMove, result: 'tie', reward: null, log: '' };
    const win  = (playerMove === 1 && monsterMove === 3) ||
                 (playerMove === 2 && monsterMove === 1) ||
                 (playerMove === 3 && monsterMove === 2);
    const lose = (playerMove === 3 && monsterMove === 1) ||
                 (playerMove === 1 && monsterMove === 2) ||
                 (playerMove === 2 && monsterMove === 3);
    if (win) {
      out.result = 'win';
      out.reward = rollReward(rng);
      applyReward(player, out.reward);
      out.log = '你赢了石像的猜拳，获得奖励！';
    } else if (lose) {
      out.result = 'lose';
      const dmg = ri(rng, 5, 10);
      if (typeof player.hp === 'number') player.hp = Math.max(0, player.hp - dmg);
      out.log = `石像赢了猜拳，你受到 ${dmg} 点伤害！`;
    } else {
      out.log = '与石像猜拳平局，无事发生。';
    }
    return out;
  }

  // 陷阱通道（C13）：直接通过 30% 概率 5~10 伤害，必通过
  function crossTrap(player, rng) {
    if (typeof rng !== 'function') rng = Math.random;
    const out = { passed: true, triggered: false, log: '' };
    if (rng() < 0.3) {
      const dmg = ri(rng, 5, 10);
      if (typeof player.hp === 'number') player.hp = Math.max(0, player.hp - dmg);
      out.triggered = true;
      out.log = `陷阱通道触发了，你受到 ${dmg} 点伤害，但挣脱了出去！`;
    } else {
      out.log = '你安全通过了陷阱通道。';
    }
    return out;
  }

  // 先探查陷阱通道（C13）：走探索判定，成功安全通过，失败受伤但通过
  function scoutTrap(state, rng) {
    if (typeof rng !== 'function') rng = Math.random;
    const check = rollExploration(totalIntel(state), rng);
    const out = {
      passed: true,
      success: check.success,
      difficulty: check.difficulty,
      roll: check.roll,
      points: check.points,
      log: '',
    };
    if (!check.success) {
      const dmg = ri(rng, 5, 10);
      if (typeof state.hp === 'number') state.hp = Math.max(0, state.hp - dmg);
      out.log = `探查未完全成功：你险险避开，但仍被机关擦伤 ${dmg} 点（依然通过）。`;
    } else {
      out.log = '探查成功：你找到了安全路径，安然通过。';
    }
    return out;
  }

  // 探索失败惩罚（C15）：50/50——5~10 伤害，或立即触发怪物遭遇
  function explorationFailPenalty(player, rng) {
    if (typeof rng !== 'function') rng = Math.random;
    const out = { encounter: false, log: '' };
    if (rng() < 0.5) {
      const dmg = ri(rng, 5, 10);
      if (typeof player.hp === 'number') player.hp = Math.max(0, player.hp - dmg);
      out.log = `探索失败：你触动了诅咒，受到 ${dmg} 点伤害！`;
    } else {
      out.encounter = true;
      out.log = '探索失败：你惊动了黑暗中的某种东西！';
    }
    return out;
  }

  // 探索成功奖励（C16）：必得 +10~15 HP，另 50% 概率追加 rollReward
  function explorationSuccessReward(player, rng) {
    if (typeof rng !== 'function') rng = Math.random;
    const out = { reward: null, log: '探索成功！' };
    healExploreSuccess(player, rng);
    if (rng() < 0.5) {
      out.reward = rollReward(rng);
      applyReward(player, out.reward);
      out.log += ' 还意外获得了一份奖励！';
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
    CHARS,
    MONSTERS,
    newGame,
    shouldEncounter,
    advanceFloor,
    checkVictory,
    checkDefeat,
    getFloorContent,
    openBox,
    solvePuzzle,
    playRps,
    crossTrap,
    scoutTrap,
    explorationFailPenalty,
    explorationSuccessReward,
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = GameLogic;
  else global.GameLogic = GameLogic;
})(typeof self !== 'undefined' ? self : this);
