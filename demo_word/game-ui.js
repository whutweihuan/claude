/* 地下城跑团 — UI 层（渲染 + 绑定）
 * 职责约定：本文件只做渲染与事件绑定，所有数值规则一律调用 window.GameLogic 的纯函数。
 * 零外链：不加载任何外部字体 / 图片 / 脚本。
 */
(function () {
  'use strict';

  const GL = window.GameLogic;
  const app = document.getElementById('app');

  /** 当前游戏状态（GameLogic.newGame 的产物）。 */
  let state = null;
  /** 每层内容缓存（Ruling C9：按层缓存，重渲染不重掷）。 */
  const floorCache = {};
  /** 日志滚动区元素。 */
  let logEl = null;

  // ------------------------------------------------------------ DOM 小工具

  /** h('div', {class:'x', onclick:fn}, child, 'text') —— 极简元素构造。 */
  function h(tag, props, ...children) {
    const node = document.createElement(tag);
    props = props || {};
    for (const key of Object.keys(props)) {
      const val = props[key];
      if (val === null || val === undefined) continue;
      if (key === 'class') node.className = val;
      else if (key === 'style') node.style.cssText = val;
      else if (key.indexOf('on') === 0 && typeof val === 'function') node.addEventListener(key.slice(2), val);
      else node.setAttribute(key, val);
    }
    for (const child of children) {
      if (child === null || child === undefined) continue;
      node.appendChild(typeof child === 'string' ? document.createTextNode(child) : child);
    }
    return node;
  }

  // ------------------------------------------------------------ 角色元数据

  const CHAR_META = {
    mage: { name: '法师', emoji: '🧙' },
    warrior: { name: '战士', emoji: '🛡️' },
  };

  function charName(type) {
    return CHAR_META[type] ? CHAR_META[type].name : type;
  }

  /** 技能一行文案（名称 + 法力消耗），取自 GL.SKILLS（对象表：id → 定义）。 */
  function skillLine(type) {
    const table = GL.SKILLS[type] || {};
    const skills = Object.keys(table)
      .map(function (id) { return table[id]; })
      .filter(function (s) { return s.name !== '普通攻击'; });
    return '技能：' + skills.map(function (s) {
      return s.name + (s.cost ? '（法力 ' + s.cost + '）' : '（不耗法力）');
    }).join(' · ');
  }

  // ------------------------------------------ 场景表（Ruling C26：文案在 UI 层）

  const SCENES = [
    { name: '地下城入口', emoji: '🕯️ 🐀', bg: 'linear-gradient(180deg,#2a1a10 0%,#120c08 100%)',
      desc: '石门缓缓开启，火把明灭不定，潮湿与铁锈的气味扑面而来。黑暗深处传来窸窣的声响。' },
    { name: '腐臭地窖', emoji: '🦴 🕸️', bg: 'linear-gradient(180deg,#1c2418 0%,#0d110c 100%)',
      desc: '陈年白骨与腐烂织物堆满房间，一层绿色的雾气贴着地面缓缓蠕动。' },
    { name: '蝙蝠洞窟', emoji: '🦇 🌑', bg: 'linear-gradient(180deg,#14142a 0%,#0a0a14 100%)',
      desc: '洞顶垂下密密麻麻的黑色翅膀，火光一暗，便有成千上万双眼睛同时睁开。' },
    { name: '蛛网回廊', emoji: '🕷️ 🕸️', bg: 'linear-gradient(180deg,#22291a 0%,#0e120a 100%)',
      desc: '粗如手指的蛛丝横贯回廊，一缕丝线上还挂着微微的颤动。' },
    { name: '白骨大厅', emoji: '💀 ⚔️', bg: 'linear-gradient(180deg,#26221c 0%,#100e0b 100%)',
      desc: '一具骷髅仍握着锈迹斑斑的长剑，空洞的眼窝正对着你的方向。' },
    { name: '嚎哭幽穴', emoji: '🐺 🌫️', bg: 'linear-gradient(180deg,#1d1a24 0%,#0c0b10 100%)',
      desc: '孤狼的嚎叫在幽穴中回荡，雾气里带着一股淡淡的血腥气。' },
    { name: '地精营地', emoji: '👺 🔥', bg: 'linear-gradient(180deg,#2a1a14 0%,#120c0a 100%)',
      desc: '篝火的余烬还在跳动，地上散落着啃剩的骨头，爪印通向更深处。' },
    { name: '石像长廊', emoji: '🗿 🏛️', bg: 'linear-gradient(180deg,#20242c 0%,#0e1014 100%)',
      desc: '成排的石像沿长廊而立，你不看它们时，它们的石脸似乎在悄悄转向你。' },
    { name: '刺客暗室', emoji: '🌒 🗡️', bg: 'linear-gradient(180deg,#16161e 0%,#09090c 100%)',
      desc: '一枚短刃斜插在地板上，刀柄尚有余温，角落里的影子似乎在呼吸。' },
    { name: '深渊之门', emoji: '⚔️ 🛡️', bg: 'linear-gradient(180deg,#1a1426 0%,#0b0910 100%)',
      desc: '巨大的黑门前，一名重甲骑士背对着你跪伏，听见脚步声也不回头。' },
    { name: '幼龙之巢', emoji: '🐉 🥚', bg: 'linear-gradient(180deg,#2a2010 0%,#120e08 100%)',
      desc: '金币与未孵化的龙蛋堆成小山，看不见的吐息让空气灼热刺鼻。' },
    { name: '鲜血祭坛', emoji: '🩸 🕯️', bg: 'linear-gradient(180deg,#2a0f0f 0%,#120808 100%)',
      desc: '祭坛上浸着新鲜的血，烛火呈暗红色，空气中隐隐传来心跳般的低鸣。' },
    { name: '亡魂战场', emoji: '👻 ⚔️', bg: 'linear-gradient(180deg,#1a2024 0%,#0c0f11 100%)',
      desc: '残破的军旗在无风中猎猎作响，虚空的冲锋余影仍在半空盘旋。' },
    { name: '熔岩河谷', emoji: '🌋 🔥', bg: 'linear-gradient(180deg,#341508 0%,#140a05 100%)',
      desc: '熔岩河在脚下轰鸣，红光映着岩壁，热浪几乎要烧焦你的皮肤。' },
    { name: '虚空裂隙', emoji: '🌀 🌌', bg: 'linear-gradient(180deg,#16102e 0%,#0a0816 100%)',
      desc: '空间裂缝渗出幽蓝的辉光，重力在这里似乎变得若有若无。' },
    { name: '冰川大殿', emoji: '❄️ 🏔️', bg: 'linear-gradient(180deg,#182634 0%,#0c1218 100%)',
      desc: '冰雪凝成的巨像矗立殿中，它的每一次呼吸都让空气结出白霜。' },
    { name: '破碎圣殿', emoji: '⚡ 🕊️', bg: 'linear-gradient(180deg,#241c2e 0%,#100c14 100%)',
      desc: '断裂的彩窗与倾倒的神像散落一地，地上的断翼仍在微微发着光。' },
    { name: '龙裔宝库', emoji: '🐲 👑', bg: 'linear-gradient(180deg,#2e1a1a 0%,#140c0c 100%)',
      desc: '鳞甲王冠反射着火光，龙裔盘踞在骸骨王座上，慵懒地打量着你。' },
    { name: '深渊王座厅', emoji: '👿 🏰', bg: 'linear-gradient(180deg,#240f1c 0%,#100810 100%)',
      desc: '黑雾灌满王座厅，高居其上的王座似乎一直在等待某个人的到来。' },
    { name: '复苏之心殿', emoji: '💖 ✨', bg: 'linear-gradient(180deg,#2e1430 0%,#140a16 100%)',
      desc: '传说中的宝藏「复苏之心」悬浮于殿中央，搏动着柔和的光——而它背后，盘踞着最后的阴影。' },
  ];

  function sceneOf(floor) {
    return SCENES[floor - 1] || SCENES[0];
  }

  // ------------------------------------------------------------ 楼层内容（C9 缓存）

  function floorContent(floor) {
    if (!floorCache[floor]) floorCache[floor] = GL.getFloorContent(floor);
    return floorCache[floor];
  }

  // ------------------------------------------------------------ 日志

  function log(msg) {
    if (!logEl) return;
    logEl.appendChild(h('div', { class: 'log-line' }, msg));
    logEl.scrollTop = logEl.scrollHeight;
  }

  // ------------------------------------------------------------ 角色选择

  function renderCharSelect() {
    state = null;
    logEl = null;
    app.innerHTML = '';
    app.appendChild(h('h1', { class: 'title' }, '地下城跑团'));
    app.appendChild(h('p', { class: 'intro' },
      '深入地下一层层探索，共 20 层。找到最底层房间中的传说宝藏「复苏之心」，拯救世界。'));
    const cards = h('div', { class: 'char-cards' });
    ['mage', 'warrior'].forEach(function (type) {
      const c = GL.CHARS[type];
      cards.appendChild(h('div', { class: 'char-card', onclick: function () { startGame(type); } },
        h('div', { class: 'char-emoji' }, CHAR_META[type].emoji),
        h('div', { class: 'char-name' }, CHAR_META[type].name),
        h('ul', { class: 'char-attrs' },
          h('li', {}, h('span', {}, 'HP'), h('span', {}, String(c.hp))),
          h('li', {}, h('span', {}, '法力值'), h('span', {}, String(c.mana))),
          h('li', {}, h('span', {}, '攻击力'), h('span', {}, String(c.atk))),
          h('li', {}, h('span', {}, '防御'), h('span', {}, String(c.def))),
          h('li', {}, h('span', {}, '智力'), h('span', {}, String(c.intel))),
        ),
        h('div', { class: 'char-skills' }, skillLine(type)),
      ));
    });
    app.appendChild(cards);
  }

  // ------------------------------------------------------------ 开始游戏

  function startGame(charType) {
    state = GL.newGame(charType);
    renderFloorView();
    log('你以「' + charName(charType) + '」的身份踏入地下城。');
    log('目标：抵达第 20 层，击败「复苏之影(最终Boss)」，取得「复苏之心」。');
    log('提示：探索可能带来奖励或惩罚；打倒本层的守护者后才能进入下一层。');
  }

  // ------------------------------------------------------------ 楼层视图

  function renderFloorView() {
    const floor = state.floor;
    app.innerHTML = '';
    app.appendChild(h('h1', { class: 'title' }, '第 ' + floor + ' 层'));

    const grid = h('div', { class: 'floor-grid' });
    const main = h('div', { class: 'floor-main' });
    main.appendChild(renderScene(floor));
    main.appendChild(renderFloor());

    const side = h('div', { class: 'floor-side' });
    side.appendChild(renderPanel());
    logEl = h('div', { class: 'logbox' });
    side.appendChild(logEl);

    grid.appendChild(main);
    grid.appendChild(side);
    app.appendChild(grid);
  }

  /** 场景卡：CSS 渐变 + emoji 氛围（Ruling C26），怪物名来自 getFloorContent。 */
  function renderScene(floor) {
    const s = sceneOf(floor);
    const content = floorContent(floor);
    return h('div', { class: 'scene-card', style: 'background:' + s.bg + ';' },
      h('div', { class: 'scene-emoji' }, s.emoji),
      h('div', { class: 'scene-desc' }, s.desc),
      h('div', { class: 'scene-monster' }, '⚔️ 黑暗中有东西在等待你——' + content.monster.name + '。'),
    );
  }

  /** 房间：描述 + 有序号选项（探索要素 + 遭遇怪 + 自由输入）。
   *  Ruling C25：本任务中选项无点击绑定，仅渲染；接线在任务 6/7。 */
  function renderFloor() {
    const floor = state.floor;
    const s = sceneOf(floor);
    const content = floorContent(floor);
    const m = content.monster;

    const options = h('div', { class: 'options' });
    let n = 1;
    content.interactions.forEach(function (id) {
      if (id === 'box') {
        options.appendChild(h('button', { class: 'opt-btn' }, (n++) + '. 📦 打开神秘的箱子'));
      } else if (id === 'puzzle') {
        options.appendChild(h('button', { class: 'opt-btn' }, (n++) + '. 🧩 破解古老的谜题机关'));
      } else if (id === 'rps') {
        options.appendChild(h('button', { class: 'opt-btn' }, (n++) + '. 🪨 与石像玩一局猜拳'));
      } else if (id === 'altar') {
        options.appendChild(h('button', { class: 'opt-btn' }, (n++) + '. 🕯️ 在祭坛虔诚祈祷'));
        options.appendChild(h('button', { class: 'opt-btn' }, (n++) + '. 🕯️ 在祭坛冒一次险'));
      } else if (id === 'trap') {
        options.appendChild(h('button', { class: 'opt-btn' }, (n++) + '. 🕳️ 先侦察陷阱通道'));
        options.appendChild(h('button', { class: 'opt-btn' }, (n++) + '. 🕳️ 直接穿过陷阱通道'));
      }
    });
    options.appendChild(h('button', { class: 'opt-btn' },
      (n++) + '. ⚔️ 直面守护者 · ' + m.name));

    const room = h('div', { class: 'room' },
      h('h3', { class: 'room-title' }, '第 ' + floor + ' 层 · ' + s.name),
      h('p', { class: 'room-desc' }, '火把的光在墙面上摇曳。你环顾四周，发现了以下可做的事：'),
      h('p', { class: 'room-monster' },
        '⚔️ 本层怪物：' + m.name + '（HP ' + m.hp + ' / 攻 ' + m.atk + ' / 防 ' + m.def +
        '，技能伤害约 ' + m.skillDmg + '，50% 概率发动）'),
      options,
      h('div', { class: 'free-input' },
        h('input', { class: 'free-text', type: 'text', placeholder: '说出你想做什么……' }),
        h('button', { class: 'free-btn' }, '说'),
      ),
    );
    return room;
  }

  // ------------------------------------------------------------ 角色面板

  function bar(label, cur, max, fillClass) {
    const pct = max > 0 ? Math.max(0, Math.min(100, Math.round((cur / max) * 100))) : 0;
    return h('div', {},
      h('div', { class: 'bar-labels' },
        h('span', {}, label + ' ' + cur + '/' + max),
        h('span', {}, pct + '%')),
      h('div', { class: 'bar-track' },
        h('div', { class: 'bar-fill ' + fillClass, style: 'width:' + pct + '%;' })),
    );
  }

  function itemText(it) {
    if (!it) return '—';
    const parts = [];
    if (it.atk) parts.push('攻+' + it.atk);
    if (it.def) parts.push('防+' + it.def);
    if (it.intel) parts.push('智+' + it.intel);
    if (it.manaRegen) parts.push('每层回' + it.manaRegen + '法力');
    return it.name + '（' + (parts.join(' ') || '—') + '）';
  }

  function equipRow(slot, label) {
    return h('div', { class: 'equip-row' },
      h('span', { class: 'equip-slot' }, label),
      h('span', {}, itemText(state.equipment[slot])));
  }

  function renderPanel() {
    return h('div', { class: 'panel' },
      h('h3', { class: 'panel-title' }, charName(state.charType)),
      bar('HP', state.hp, state.maxHp, 'bar-hp'),
      bar('法力', state.mana, state.maxMana, 'bar-mana'),
      h('div', { class: 'stats' },
        h('div', { class: 'stat' }, h('span', { class: 'stat-label' }, '攻'), h('span', { class: 'stat-val' }, String(GL.totalAtk(state)))),
        h('div', { class: 'stat' }, h('span', { class: 'stat-label' }, '防'), h('span', { class: 'stat-val' }, String(GL.totalDef(state)))),
        h('div', { class: 'stat' }, h('span', { class: 'stat-label' }, '智'), h('span', { class: 'stat-val' }, String(GL.totalIntel(state)))),
      ),
      h('div', { class: 'equip' },
        h('h4', { class: 'equip-title' }, '装备'),
        equipRow('weapon', '武器'),
        equipRow('armor', '护甲'),
        equipRow('trinket', '饰品'),
      ),
      h('div', { class: 'floor-num' }, '当前层：' + state.floor + ' / 20'),
    );
  }

  // ------------------------------------------------------------ 初始化

  /** 暴露给任务 6/7 接线与调试。 */
  window.DungeonUI = {
    renderCharSelect: renderCharSelect,
    startGame: startGame,
    renderFloorView: renderFloorView,
    renderScene: renderScene,
    renderFloor: renderFloor,
    renderPanel: renderPanel,
    log: log,
    getState: function () { return state; },
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', renderCharSelect);
  } else {
    renderCharSelect();
  }
})();
