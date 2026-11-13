# -*- coding: utf-8 -*-
"""内容数据表：卡牌、武器、防具、遗物、药水（纯数据，无战斗逻辑）。"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

GAME_ID = 'warrior'


@dataclass
class Card:
    id: str
    name: str
    cost: int
    kind: str            # 'attack' | 'skill' | 'power'
    text: str
    effects: List[Tuple]
    upgrade: Optional[Dict] = None


@dataclass
class Gear:
    id: str
    name: str
    kind: str            # 'weapon' | 'armor'
    attack_bonus: int
    text: str
    mods: Dict = field(default_factory=dict)


@dataclass
class Potion:
    id: str
    name: str
    text: str
    effects: List[Tuple]
    targeted: bool = False


# 战斗效果原语封闭集（附录 C）
PRIMITIVES = frozenset([
    'damage', 'damage_all', 'pierce', 'execute', 'bonus_if_vulnerable',
    'self_vulnerable', 'block', 'draw', 'energy', 'hp_cost', 'heal',
    'self_strength', 'vulnerable', 'poison', 'vulnerable_all', 'poison_all',
    'power', 'exhaust',
])

POWER_KEYS = frozenset([
    'first_attack_bonus', 'strength_per_turn', 'block_per_turn',
    'draw_per_turn', 'energy_per_turn',
])

GEAR_MOD_KEYS = frozenset([
    'first_card_extra_cost', 'draw_per_turn', 'turn_start_self_damage',
    'energy_per_turn', 'start_block', 'thorns', 'heal',
])

BASICS = ('strike', 'defend')
STARTER_DECK = [('strike', False)] * 6 + [('defend', False)] * 4

CARDS = {}


def _c(cid, name, cost, kind, text, effects, rarity, upgrade_text=None,
       upgrade_effects=None):
    up = None
    if upgrade_effects is not None:
        up = {'text': upgrade_text, 'effects': upgrade_effects}
    elif cid not in BASICS:
        raise ValueError(cid)  # 建表时即保证非基础牌必有 upgrade
    CARDS[cid] = Card(id=cid, name=name, cost=cost, kind=kind, text=text,
                      effects=effects, upgrade=up)
    CARD_RARITY[cid] = rarity


CARD_RARITY = {}
CARD_RARITY.update({b: 'basic' for b in BASICS})

# —— 基础 ——
_c('strike', '打击', 1, 'attack', '造成 6 点伤害。', [('damage', 6)], 'basic',
   '造成 9 点伤害。', [('damage', 9)])
_c('defend', '防御', 1, 'skill', '获得 5 点格挡。', [('block', 5)], 'basic',
   '获得 8 点格挡。', [('block', 8)])

# —— 攻击 ——
_c('heavy', '重击', 2, 'attack', '造成 12 点伤害。', [('damage', 12)], 'rare',
   '造成 16 点伤害。', [('damage', 16)])
_c('twin', '连刺', 1, 'attack', '造成 3 点伤害两次。',
   [('damage', 3), ('damage', 3)], 'common',
   '造成 4 点伤害三次。', [('damage', 4), ('damage', 4), ('damage', 4)])
_c('cleave', '横扫', 1, 'attack', '对所有敌人造成 7 点伤害。',
   [('damage_all', 7)], 'common',
   '对所有敌人造成 10 点伤害。', [('damage_all', 10)])
_c('quake', '震地', 2, 'attack', '对所有敌人造成 7 点伤害，获得 3 点格挡。',
   [('damage_all', 7), ('block', 3)], 'rare',
   '对所有敌人造成 10 点伤害，获得 5 点格挡。',
   [('damage_all', 10), ('block', 5)])
_c('whirl', '旋风连斩', 2, 'attack', '造成 4 点伤害三次。',
   [('damage', 4), ('damage', 4), ('damage', 4)], 'uncommon',
   '造成 5 点伤害三次。',
   [('damage', 5), ('damage', 5), ('damage', 5)])
_c('execute', '处决', 2, 'attack',
   '若目标血量低于 30%，造成 22 点伤害，否则造成 7 点。',
   [('execute', 0.3, 22, 7)], 'rare',
   '若目标血量低于 30%，造成 26 点伤害，否则造成 9 点。',
   [('execute', 0.3, 26, 9)])
_c('pierce', '破甲刺', 1, 'attack', '造成 8 点伤害，无视格挡。',
   [('pierce', 8)], 'rare', '造成 11 点伤害，无视格挡。', [('pierce', 11)])
_c('brand', '猎印', 1, 'attack',
   '对易伤的敌人额外造成 6 点伤害，然后造成 5 点伤害。',
   [('bonus_if_vulnerable', 6), ('damage', 5)], 'uncommon',
   '对易伤的敌人额外造成 9 点伤害，然后造成 5 点伤害。',
   [('bonus_if_vulnerable', 9), ('damage', 5)])
_c('rip', '撕裂', 0, 'attack', '造成 4 点伤害，本场战斗移出。',
   [('damage', 4), ('exhaust',)], 'common',
   '造成 7 点伤害，本场战斗移出。', [('damage', 7), ('exhaust',)])
_c('poison_stab', '淬毒之刺', 1, 'attack', '造成 4 点伤害，施加 4 层毒。',
   [('damage', 4), ('poison', 4)], 'uncommon',
   '造成 4 点伤害，施加 6 层毒。', [('damage', 4), ('poison', 6)])
_c('fury_edge', '燃血斩', 1, 'attack', '失去 4 点生命，造成 11 点伤害。',
   [('hp_cost', 4), ('damage', 11)], 'uncommon',
   '失去 4 点生命，造成 15 点伤害。', [('hp_cost', 4), ('damage', 15)])
_c('shatter', '碎骨', 2, 'attack', '造成 9 点伤害，自身获得 1 层易伤。',
   [('damage', 9), ('self_vulnerable', 1)], 'rare',
   '造成 13 点伤害，自身获得 1 层易伤。',
   [('damage', 13), ('self_vulnerable', 1)])
_c('annihilate', '湮灭', 3, 'attack', '失去 6 点生命，造成 24 点伤害。',
   [('hp_cost', 6), ('damage', 24)], 'rare',
   '失去 6 点生命，造成 30 点伤害。', [('hp_cost', 6), ('damage', 30)])

# —— 技能 ——
_c('iron_will', '铁志', 1, 'skill', '获得 8 点格挡。', [('block', 8)], 'common',
   '获得 11 点格挡。', [('block', 11)])
_c('taunt', '挑衅', 1, 'skill', '所有敌人获得 2 层易伤。',
   [('vulnerable_all', 2)], 'uncommon', '所有敌人获得 3 层易伤。',
   [('vulnerable_all', 3)])
_c('warcry', '战吼', 0, 'skill', '抽 3 张牌。', [('draw', 3)], 'common',
   '抽 3 张牌，获得 5 点格挡。', [('draw', 3), ('block', 5)])
_c('focus', '蓄能', 0, 'skill', '本回合获得 2 点能量。', [('energy', 2)],
   'common', '本回合获得 3 点能量。', [('energy', 3)])
_c('bulwark', '壁垒', 2, 'skill', '获得 14 点格挡。', [('block', 14)],
   'uncommon', '获得 18 点格挡。', [('block', 18)])
_c('second_wind', '回春', 1, 'skill', '回复 6 点生命。', [('heal', 6)],
   'common', '回复 9 点生命。', [('heal', 9)])
_c('adrenaline', '肾上腺素', 0, 'skill',
   '抽 2 张牌，本回合获得 1 点能量，本战移出。',
   [('draw', 2), ('energy', 1), ('exhaust',)], 'uncommon',
   '抽 2 张牌，本回合获得 1 点能量和 3 点格挡，本战移出。',
   [('draw', 2), ('energy', 1), ('block', 3), ('exhaust',)])
_c('blood_price', '血之代价', 1, 'skill',
   '失去 8 点生命，本回合获得 3 点能量，本战移出。',
   [('hp_cost', 8), ('energy', 3), ('exhaust',)], 'rare',
   '失去 8 点生命，本回合获得 4 点能量，本战移出。',
   [('hp_cost', 8), ('energy', 4), ('exhaust',)])

# —— 能力 ——
_c('fury', '狂怒', 1, 'power', '本战每回合首次攻击伤害 +3。',
   [('power', 'first_attack_bonus', 3)], 'uncommon',
   '本战每回合首次攻击伤害 +5。', [('power', 'first_attack_bonus', 5)])
_c('stone_skin', '石肤', 1, 'power', '每回合结束获得 3 点格挡。',
   [('power', 'block_per_turn', 3)], 'uncommon',
   '每回合结束获得 4 点格挡。', [('power', 'block_per_turn', 4)])
_c('trance', '战意', 2, 'power', '每回合获得 2 点力量。',
   [('power', 'strength_per_turn', 2)], 'rare',
   '每回合获得 3 点力量。', [('power', 'strength_per_turn', 3)])
_c('keen', '嗜刃', 1, 'power', '每回合多抽 1 张牌。',
   [('power', 'draw_per_turn', 1)], 'rare',
   '每回合多抽 1 张牌，每回合能量 +1。',
   [('power', 'draw_per_turn', 1), ('power', 'energy_per_turn', 1)])
_c('war_drum', '战鼓', 2, 'power', '每回合获得 1 点力量和 2 点格挡。',
   [('power', 'strength_per_turn', 1), ('power', 'block_per_turn', 2)],
   'uncommon', '每回合获得 2 点力量和 3 点格挡。',
   [('power', 'strength_per_turn', 2), ('power', 'block_per_turn', 3)])

# —— 武器 ——
WEAPONS = {
    'rusty': Gear('rusty', '锈剑', 'weapon', 0, '攻击伤害 +0。', {}),
    'longsword': Gear('longsword', '旅行者长剑', 'weapon', 1, '攻击伤害 +1。',
                      {}),
    'axe': Gear('axe', '巨斩斧', 'weapon', 4,
                '攻击伤害 +4，每回合第一张牌额外消耗 1 能量。',
                {'first_card_extra_cost': 1}),
    'twinblades': Gear('twinblades', '双刃', 'weapon', -1,
                       '攻击伤害 -1，每回合多抽 1 张牌。',
                       {'draw_per_turn': 1}),
    'flame': Gear('flame', '燃火之刃', 'weapon', 2,
                  '攻击伤害 +2，每回合开始时受到 2 点伤害。',
                  {'turn_start_self_damage': 2}),
    'spear': Gear('spear', '猎魔长矛', 'weapon', 2, '攻击伤害 +2。', {}),
}

# —— 防具 ——
ARMORS = {
    'cloth': Gear('cloth', '布甲', 'armor', 0, '战斗开始获得 2 点格挡。',
                  {'start_block': 2}),
    'leather': Gear('leather', '皮甲', 'armor', 0, '战斗开始获得 5 点格挡。',
                    {'start_block': 5}),
    'plate': Gear('plate', '板甲', 'armor', 0,
                  '战斗开始获得 9 点格挡，每回合能量 -1。',
                  {'start_block': 9, 'energy_per_turn': -1}),
    'spiked': Gear('spiked', '刺甲', 'armor', 0,
                   '战斗开始获得 3 点格挡，敌人攻击你时受到 3 点反弹伤害。',
                   {'start_block': 3, 'thorns': 3}),
    'guardian': Gear('guardian', '守护胸甲', 'armor', 0,
                     '战斗开始获得 4 点格挡并回复 2 点生命。',
                     {'start_block': 4, 'heal': 2}),
}

# —— 药水 ——
POTIONS = {
    'p_blood': Potion('p_blood', '血瓶', '回复 14 点生命。', [('heal', 14)]),
    'p_energy': Potion('p_energy', '灵感', '本回合获得 2 点能量。',
                       [('energy', 2)]),
    'p_fury': Potion('p_fury', '怒火', '本战获得 3 点力量。',
                     [('self_strength', 3)]),
    'p_acid': Potion('p_acid', '酸瓶', '对一个敌人造成 12 点伤害。',
                     [('damage', 12)], True),
    'p_gall': Potion('p_gall', '胆汁膏', '所有敌人获得 6 层毒。',
                     [('poison_all', 6)]),
}


def _check_effects(effects, where):
    if not isinstance(effects, list) or not effects:
        raise ValueError('%s: effects 必须是非空列表' % where)
    for eff in effects:
        if not isinstance(eff, tuple) or not eff:
            raise ValueError('%s: 原语必须是元组: %r' % (where, eff))
        if eff[0] not in PRIMITIVES:
            raise ValueError('%s: 未知原语 %r' % (where, eff[0]))
        if eff[0] == 'power' and eff[1] not in POWER_KEYS:
            raise ValueError('%s: 未知持续词条 %r' % (where, eff[1]))


def validate_content():
    """校验各数据表自洽；违规抛 ValueError。"""
    for cid, card in CARDS.items():
        if card.kind not in ('attack', 'skill', 'power'):
            raise ValueError('card %s: kind=%r' % (cid, card.kind))
        if not (0 <= card.cost <= 3):
            raise ValueError('card %s: cost=%r' % (cid, card.cost))
        _check_effects(card.effects, 'card ' + cid)
        if cid not in BASICS:
            if card.upgrade is None:
                raise ValueError('card %s: 非基础牌缺 upgrade' % cid)
            _check_effects(card.upgrade['effects'], 'card %s+' % cid)
        if cid not in CARD_RARITY:
            raise ValueError('card %s: 缺稀有度' % cid)
        if CARD_RARITY[cid] == 'basic' and cid not in BASICS:
            raise ValueError('card %s: 稀有度与基础牌不符' % cid)
    for table, kind in ((WEAPONS, 'weapon'), (ARMORS, 'armor')):
        for gid, gear in table.items():
            if gear.kind != kind:
                raise ValueError('gear %s: kind 不符' % gid)
            for key in gear.mods:
                if key not in GEAR_MOD_KEYS:
                    raise ValueError('gear %s: 未知词条 %r' % (gid, key))
    for pid, pot in POTIONS.items():
        _check_effects(pot.effects, 'potion ' + pid)
    names = [c.name for c in CARDS.values()] \
        + [g.name for g in WEAPONS.values()] \
        + [g.name for g in ARMORS.values()] \
        + [p.name for p in POTIONS.values()]
    if len(set(names)) != len(names):
        raise ValueError('存在重名条目')
