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


@dataclass
class Relic:
    id: str
    name: str
    rarity: str          # 'common' | 'uncommon' | 'rare' | 'boss'
    text: str
    hooks: Dict


RELIC_HOOK_KEYS = frozenset([
    'first_turn_energy', 'first_turn_draw', 'start_block', 'low_hp_pct',
    'low_hp_strength', 'poison_start', 'combat_end_heal', 'turn_end_heal',
    'attack_damage_base', 'first_attack_bonus', 'thorns', 'block_persist',
    'death_save', 'card_reward_extra', 'gold_mult', 'shop_discount',
    'instant_gold', 'cost_adjust_kind', 'cost_adjust_delta',
    'cost_adjust_min', 'turn_start_energy', 'every_n_turns', 'boss_trophy',
])


def _r(rid, name, rarity, text, hooks):
    RELICS[rid] = Relic(rid, name, rarity, text, hooks)


RELICS = {}

_r('ember', '炭炉石', 'uncommon', '每场战斗结束后回复 4 点生命。',
   {'combat_end_heal': 4})
_r('coffee', '咖啡壶', 'rare', '每场战斗第一回合能量 +1。',
   {'first_turn_energy': 1})
_r('horn', '战吼号角', 'uncommon', '每场战斗第一回合多抽 2 张牌。',
   {'first_turn_draw': 2})
_r('purse', '钱包', 'common', '获得的金币 +25%。', {'gold_mult': 1.25})
_r('tooth', '巨魔之牙', 'rare', '开战时若生命低于 30%，力量 +2。',
   {'low_hp_pct': 0.3, 'low_hp_strength': 2})
_r('torch', '火把', 'uncommon', '攻击伤害 +1。', {'attack_damage_base': 1})
_r('bandage', '旧绷带', 'common', '战斗开始格挡 +4。', {'start_block': 4})
_r('ration', '旅行口粮', 'common', '每回合结束回复 2 点生命。',
   {'turn_end_heal': 2})
_r('whetstone', '磨刀石', 'uncommon', '每回合第一次攻击伤害 +2。',
   {'first_attack_bonus': 2})
_r('hag_hat', '商人之帽', 'uncommon', '商店价格 80%。',
   {'shop_discount': 0.8})
_r('lucky_dice', '幸运骰', 'common', '卡牌奖励多 1 个选项。',
   {'card_reward_extra': 1})
_r('iron_heel', '铁踵', 'rare', '回合结束时格挡不再清零。',
   {'block_persist': 1})
_r('warpaint', '战纹面具', 'uncommon', '开战时所有敌人获得 1 层毒。',
   {'poison_start': 1})
_r('vial', '血之圣瓶', 'rare', '受到致死伤害时以 30% 生命站起（本局限一次）。',
   {'death_save': 0.3})
_r('nugget', '金锭', 'common', '获得时立即 +30 金币。', {'instant_gold': 30})
_r('fang_necklace', '狼牙项链', 'uncommon', '攻击你的敌人受到 2 点伤害。',
   {'thorns': 2})
_r('idol', '战神小像', 'rare', '能力牌费用 -1（最低 0）。',
   {'cost_adjust_kind': 'power', 'cost_adjust_delta': -1,
    'cost_adjust_min': 0})
_r('hourglass', '时之沙漏', 'rare', '每逢第 3 的倍数回合，能量 +1。',
   {'turn_start_energy': 1, 'every_n_turns': 3})
_r('crown', '魔王冠冕', 'boss', '通关纪念。', {'boss_trophy': 1})

RELIC_RARITIES = ('common', 'uncommon', 'rare')


@dataclass
class Move:
    name: str
    kind: str            # 'attack' | 'block' | 'buff' | 'debuff' | 'poison'
    weight: int
    damage: int = 0
    hits: int = 1
    block: int = 0
    strength: int = 0
    vulnerable: int = 0
    poison: int = 0


@dataclass
class Enemy:
    id: str
    name: str
    hp: int
    moves: List[Move]
    is_elite: bool = False
    is_boss: bool = False
    cycle: bool = False
    phase2_at_half: bool = False
    phase2_per_turn_strength: int = 0
    phase2_moves: List[Move] = field(default_factory=list)


@dataclass
class EventOption:
    label: str
    outcome: List[Tuple]


@dataclass
class GameEvent:
    id: str
    title: str
    text: str
    options: List[EventOption]


EVENT_PRIMITIVES = frozenset([
    'hp', 'heal', 'gold', 'gain_potion_random', 'gain_relic_random',
    'gain_gear_random', 'add_card_random', 'upgrade_random_card',
    'remove_random_card', 'start_combat', 'branch', 'nothing',
])

RELIC_RARITIES = ('common', 'uncommon', 'rare')


def _mv(name, kind, weight, damage=0, hits=1, block=0, strength=0,
        vulnerable=0, poison=0):
    return Move(name, kind, weight, damage, hits, block, strength,
                vulnerable, poison)


ENEMIES = {}


def _e(enemy):
    ENEMIES[enemy.id] = enemy


_e(Enemy('goblin', '哥布林', 14,
         [_mv('乱砍', 'attack', 3, damage=5), _mv('竖盾', 'block', 1, block=4)]))
_e(Enemy('wolf', '野狼', 12,
         [_mv('撕咬连击', 'attack', 3, damage=3, hits=2),
          _mv('猛扑', 'attack', 1, damage=6)]))
_e(Enemy('slime', '史莱姆', 20,
         [_mv('酸液拍打', 'attack', 2, damage=4),
          _mv('凝缩', 'block', 2, block=6)]))
_e(Enemy('bandit', '强盗', 24,
         [_mv('弯刀', 'attack', 3, damage=8),
          _mv('磨刀+格挡', 'buff', 1, block=6, strength=1)]))
_e(Enemy('archer', '骷髅弓手', 16,
         [_mv('三连射', 'attack', 3, damage=4, hits=3),
          _mv('蓄力一箭', 'attack', 1, damage=9)]))
_e(Enemy('imp', '小恶魔', 18,
         [_mv('火球', 'attack', 2, damage=7),
          _mv('嘲讽诅咒', 'debuff', 1, vulnerable=2),
          _mv('毒尘', 'poison', 1, poison=3)]))
_e(Enemy('knight', '黑暗骑士', 32,
         [_mv('重剑横扫', 'attack', 3, damage=11),
          _mv('铁壁姿态', 'buff', 1, block=8, strength=2)]))
_e(Enemy('mimic', '宝箱怪', 20,
         [_mv('假箱子咬合', 'attack', 3, damage=9, hits=2),
          _mv('伪装收缩', 'block', 1, block=5)]))
_e(Enemy('golem', '石魔像', 58,
         [_mv('岩甲', 'block', 1, block=12),
          _mv('蓄能', 'buff', 1, strength=2),
          _mv('巨拳', 'attack', 1, damage=9, hits=2)],
         is_elite=True, cycle=True))
_e(Enemy('assassin', '影刺客', 48,
         [_mv('影刃连刺', 'attack', 1, damage=4, hits=3),
          _mv('致命一式', 'attack', 1, damage=10, vulnerable=1),
          _mv('烟雾', 'block', 1, block=6)],
         is_elite=True, cycle=True))
_e(Enemy('demon_lord', '魔王', 160,
         [_mv('魔王斩', 'attack', 1, damage=12),
          _mv('黑暗壁垒', 'block', 1, block=10),
          _mv('炼狱双重', 'attack', 1, damage=6, hits=2, vulnerable=1)],
         is_boss=True, cycle=True, phase2_at_half=True,
         phase2_per_turn_strength=2,
         phase2_moves=[_mv('狂暴连斩', 'attack', 3, damage=8, hits=2),
                       _mv('灭世一击', 'attack', 2, damage=15)]))

ELITE_IDS = ('golem', 'assassin')
BOSS_ID = 'demon_lord'

ENCOUNTERS = [
    (1, 2, [('goblin', 3), ('wolf', 3), ('slime', 2)], 2),
    (3, 5, [('goblin', 2), ('wolf', 2), ('slime', 2), ('bandit', 3),
            ('archer', 3)], 3),
    (6, 8, [('bandit', 2), ('archer', 2), ('imp', 3), ('knight', 2),
            ('slime', 1)], 3),
    (9, 11, [('knight', 3), ('archer', 2), ('imp', 2), ('bandit', 2)], 3),
]


def _ev(eid, title, text, options):
    EVENTS[eid] = GameEvent(eid, title, text,
                            [EventOption(l, o) for l, o in options])


EVENTS = {}

_ev('wounded_traveler', '受伤的旅人',
    '山路边倒着一名旅人，腿被落石砸中。他看见你的剑，眼里闪过一丝希望——'
    '还有你背囊里露出的绷带。',
    [('救助他（耽误行程，损失些体力）',
      [('hp', -3), ('gain_relic_random', 'common')]),
     ('搜走他的财物',
      [('gold', 25), ('branch', [(1, [('start_combat', ['wolf'])]),
                                (1, [('nothing',)])])]),
     ('离开', [('nothing',)])])

_ev('goblin_gambler', '赌博地精',
    '一块歪斜的桌后，地精摇晃着三只贝壳："猜中了，金币翻倍；猜错了，留下买路财。"'
    '桌上是你的钱袋，桌下是它同伙的眼睛。',
    [('押上 30 金币',
      [('gold', -30),
       ('branch', [(1, [('gold', 60)]), (1, [('nothing',)])])]),
     ('掀桌抢钱（可能有埋伏）',
      [('gold', 45),
       ('branch', [(1, [('start_combat', ['bandit', 'imp'])]),
                   (2, [('nothing',)])])]),
     ('不赌', [('nothing',)])])

_ev('dark_altar', '黑暗祭坛',
    '林间空地上立着一座无名祭坛，槽中残留着暗色痕迹。你不确定那是铁锈，'
    '还是别的什么。祭坛上的黑石微微发烫。',
    [('割掌献祭 8 点生命，取走黑石',
      [('hp', -8), ('gain_relic_random', 'uncommon')]),
     ('砸了祭坛，捡走值钱的',
      [('gain_gear_random', 'weapon', 2),
       ('branch', [(1, [('hp', -6)]), (1, [('start_combat', ['slime'])])])]),
     ('离开', [('nothing',)])])

_ev('ruined_forge', '铁匠铺废墟',
    '烧塌的铁匠铺还留着半炉余温。灰烬下或许埋着没被熔掉的家伙，'
    '也可能埋着惊扰死者的代价。',
    [('翻找灰烬',
      [('branch', [(2, [('gain_gear_random', 'weapon', 1)]),
                   (1, [('hp', -6)]),
                   (1, [('gain_potion_random',)])])]),
     ('离开', [('nothing',)])])

_ev('merchant_corpse', '商人的尸体',
    '货车翻了，商人死于劫掠。钱袋还鼓着——劫匪也许还没走远。'
    '他睁着的眼望着你，像在问最后一个愿望。',
    [('搜刮货物',
      [('gold', 40), ('gain_potion_random',),
       ('branch', [(1, [('start_combat', ['bandit'])]),
                   (2, [('nothing',)])])]),
     ('挖个坑安葬他',
      [('branch', [(1, [('gain_relic_random', 'common')]),
                   (2, [('nothing',)])])])])

_ev('hot_spring', '温泉',
    '岩缝间冒着白汽的泉水，暖得很安心。水壶是空的，'
    '而赶路的人总说这种地方浪费时间。',
    [('泡一会儿', [('heal', 12)]),
     ('灌满水壶带走', [('gain_potion_random',)]),
     ('匆匆路过', [('nothing',)])])

_ev('shrine_of_bones', '骨之祠',
    '用巨兽骨骸搭起的小祠，供着无名之人的遗物。祭司说过：跪下的人带走祝福，'
    '伸手的人带走骨头的怒火。',
    [('跪下祈祷', [('upgrade_random_card',)]),
     ('拿走供品',
      [('gold', 55), ('remove_random_card',),
       ('branch', [(1, [('start_combat', ['knight'])]),
                   (2, [('nothing',)])])])])

_ev('mimic_chest', '会咬人的箱子',
    '角落里有一只精致的宝箱，锁扣是牙做的——你见过这种货色。'
    '它也在等你伸手。',
    [('硬开（付点血）',
      [('hp', -10), ('gain_relic_random', 'uncommon')]),
     ('识破它，先拔剑', [('start_combat', ['mimic'])]),
     ('走开', [('nothing',)])])

_ev('wandering_bard', '流浪诗人',
    '诗人拨着断弦的鲁特琴："勇士，为您的传说谱一首？还是先听完这首，'
    '再决定要不要付钱？"',
    [('听完一曲', [('heal', 4)]),
     ('给小费 25 金币，请他教一手',
      [('gold', -25), ('add_card_random', 'uncommon')]),
     ('点一曲《屠魔》',
      [('gold', -10), ('gain_potion_random',)])])


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
    for rid, relic in RELICS.items():
        if relic.rarity not in RELIC_RARITIES + ('boss',):
            raise ValueError('relic %s: 稀有度非法' % rid)
        if not relic.text:
            raise ValueError('relic %s: 缺描述' % rid)
        for key in relic.hooks:
            if key not in RELIC_HOOK_KEYS:
                raise ValueError('relic %s: 未知钩子 %r' % (rid, key))
    if sum(1 for r in RELICS.values() if r.rarity == 'boss') != 1:
        raise ValueError('boss 遗物应恰为 1 件')
    for eid, enemy in ENEMIES.items():
        if len(enemy.moves) < 2:
            raise ValueError('enemy %s: 招式不足' % eid)
        for m in enemy.moves:
            if m.kind not in ('attack', 'block', 'buff', 'debuff', 'poison'):
                raise ValueError('enemy %s: 招式 kind=%r' % (eid, m.kind))
            if m.kind == 'attack' and m.damage <= 0:
                raise ValueError('enemy %s: 攻击招式缺伤害' % eid)
            if m.weight <= 0:
                raise ValueError('enemy %s: 招式 weight=%r' % (eid, m.weight))
        if enemy.phase2_at_half and not enemy.phase2_moves:
            raise ValueError('enemy %s: 缺二阶段招式' % eid)
    if BOSS_ID not in ENEMIES or not ENEMIES[BOSS_ID].is_boss:
        raise ValueError('BOSS_ID 非法')
    for eid in ELITE_IDS:
        if eid not in ENEMIES or not ENEMIES[eid].is_elite:
            raise ValueError('精英 %s 非法' % eid)
    for a, b, pool, max_count in ENCOUNTERS:
        if a > b or not (1 <= max_count <= 3):
            raise ValueError('ENCOUNTERS 区间/数量非法')
        for mid, w in pool:
            if mid not in ENEMIES or w <= 0:
                raise ValueError('ENCOUNTERS 引用敌人非法: %s' % mid)
            if ENEMIES[mid].is_boss or ENEMIES[mid].is_elite:
                raise ValueError('ENCOUNTERS 不应引用精英/boss: %s' % mid)
    _check_event_outcomes(
        [eff for ev in EVENTS.values() for opt in ev.options
         for eff in opt.outcome], 'events')
    for ev in EVENTS.values():
        if not (2 <= len(ev.options) <= 3):
            raise ValueError('event %s: 选项数非法' % ev.id)
    names = [c.name for c in CARDS.values()] \
        + [g.name for g in WEAPONS.values()] \
        + [g.name for g in ARMORS.values()] \
        + [p.name for p in POTIONS.values()] \
        + [e.name for e in ENEMIES.values()] \
        + [r.name for r in RELICS.values()] \
        + [ev.title for ev in EVENTS.values()]
    if len(set(names)) != len(names):
        raise ValueError('存在重名条目')


def _check_event_outcomes(effs, where):
    for eff in effs:
        if not isinstance(eff, tuple) or not eff:
            raise ValueError('%s: 事件原语必须是元组: %r' % (where, eff))
        op = eff[0]
        if op not in EVENT_PRIMITIVES:
            raise ValueError('%s: 未知事件原语 %r' % (where, op))
        if op == 'hp' or op == 'gold':
            if not isinstance(eff[1], int):
                raise ValueError('%s: %s 需要整数' % (where, op))
        elif op in ('gain_relic_random', 'add_card_random'):
            if eff[1] not in RELIC_RARITIES:
                raise ValueError('%s: 稀有度非法 %r' % (where, eff[1]))
        elif op == 'gain_gear_random':
            if eff[1] not in ('weapon', 'armor'):
                raise ValueError('%s: 装备类别非法 %r' % (where, eff[1]))
        elif op == 'start_combat':
            for mid in eff[1]:
                if mid not in ENEMIES:
                    raise ValueError('%s: 引战目标非法 %s' % (where, mid))
        elif op == 'branch':
            for w, outcomes in eff[1]:
                if w <= 0:
                    raise ValueError('%s: 分支权重非法 %r' % (where, w))
                _check_event_outcomes(outcomes, where + '.branch')
