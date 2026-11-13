# -*- coding: utf-8 -*-
"""纯逻辑核心：战斗状态机、效果解释器、地图、一局编排。无 print/input。"""
import random
from dataclasses import dataclass, field

import content

TIER_HP_MULT = {1: 1.0, 2: 1.3, 3: 1.6}
TIER_DMG_ADD = {1: 0, 2: 1, 3: 2}


@dataclass
class Hero:
    max_hp: int = 80
    hp: int = 80
    gold: int = 0
    deck: list = field(default_factory=list)
    weapon: str = 'rusty'
    armor: object = None
    relics: list = field(default_factory=list)
    potions: list = field(default_factory=list)


class EnemyInstance(object):
    def __init__(self, defn, tier):
        self.defn = defn
        self.id = defn.id
        self.name = defn.name
        self.max_hp = int(round(defn.hp * TIER_HP_MULT.get(tier, 1.0)))
        self.hp = self.max_hp
        self.block = 0
        self.strength = 0
        self.vulnerable = 0
        self.poison = 0
        self.dmg_add = TIER_DMG_ADD.get(tier, 0)
        self.intent = None
        self._move_idx = 0

    @property
    def alive(self):
        return self.hp > 0


class Combat(object):
    BASE_ENERGY = 3
    BASE_DRAW = 5

    def __init__(self, hero, enemy_ids, rng, tier=1):
        self.hero = hero
        self.rng = rng
        self.enemies = [EnemyInstance(content.ENEMIES[eid], tier)
                        for eid in enemy_ids]
        self.draw_pile = list(hero.deck)
        rng.shuffle(self.draw_pile)
        self.hand = []
        self.discard_pile = []
        self.exhausted = []
        self.energy = 0
        self.block = 0
        self.strength = 0
        self.vulnerable = 0     # 英雄侧易伤
        self.poison = 0         # 英雄侧毒
        self.powers = {}        # 本战持续词条 key -> n
        self.turn = 0
        self.status = 'playing'
        self.attacked_this_turn = False
        self._pending_bonus = 0
        self._card_exhausts = False

    # ---------- 回合流程 ----------

    def start(self):
        return self._begin_player_turn()

    def _begin_player_turn(self):
        lines = []
        self.turn += 1
        self.block = 0
        if self.poison > 0:
            lines.extend(self._tick_poison(hero_side=True))
        self.energy = self.BASE_ENERGY + self.powers.get('energy_per_turn', 0)
        self.attacked_this_turn = False
        if self.powers.get('strength_per_turn'):
            self.strength += self.powers['strength_per_turn']
        n = self.BASE_DRAW + self.powers.get('draw_per_turn', 0)
        lines.extend(self._draw(n))
        if self.status == 'playing':
            self._gen_intents()
        return lines

    def _draw(self, n):
        lines = []
        for _ in range(n):
            if not self.draw_pile:
                if not self.discard_pile:
                    break
                self.draw_pile = list(self.discard_pile)
                self.discard_pile = []
                self.rng.shuffle(self.draw_pile)
                lines.append('（弃牌堆洗回抽牌堆）')
            if self.draw_pile:
                self.hand.append(self.draw_pile.pop())
        return lines

    def _gen_intents(self):
        """任务 4 实装敌人意图；此处占位。"""

    def end_turn(self):
        lines = []
        if self.powers.get('block_per_turn'):
            self.block += self.powers['block_per_turn']
        self.discard_pile.extend(self.hand)
        self.hand = []
        lines.extend(self._enemy_turn())
        if self.status == 'playing':
            lines.extend(self._begin_player_turn())
        return lines

    def _enemy_turn(self):
        """任务 4 实装敌人行动；此处占位。"""
        return []

    # ---------- 出牌 ----------

    def effects_for(self, card_id, upgraded):
        card = content.CARDS[card_id]
        if upgraded and card.upgrade:
            return card.upgrade['effects'], card.upgrade['text']
        return card.effects, card.text

    def play_card(self, i, target=None):
        if self.status != 'playing':
            return ['战斗已结束。']
        if not (0 <= i < len(self.hand)):
            return ['没有这张牌，请重新选择。']
        card_id, upgraded = self.hand[i]
        card = content.CARDS[card_id]
        cost = self._card_cost(card)
        if cost > self.energy:
            return ['能量不足：【%s】需要 %d 点能量。' % (card.name, cost)]
        effects, _text = self.effects_for(card_id, upgraded)
        self.energy -= cost
        self.hand.pop(i)
        self._pending_bonus = 0
        self._card_exhausts = any(eff[0] == 'exhaust' for eff in effects)
        lines = ['你打出【%s】。' % card.name]
        for eff in effects:
            if self.status != 'playing':
                break
            lines.extend(apply_effect(self.hero, self, eff, target))
            if self._target_none():
                break
        if self._card_exhausts:
            self.exhausted.append((card_id, upgraded))
        else:
            self.discard_pile.append((card_id, upgraded))
        self._check_end()
        return lines

    def _card_cost(self, card):
        return card.cost

    def snapshot(self):
        return {
            'hp': self.hero.hp, 'max_hp': self.hero.max_hp,
            'block': self.block, 'energy': self.energy,
            'gold': self.hero.gold, 'turn': self.turn,
            'status': self.status,
            'hand': [{'idx': idx, 'name': content.CARDS[cid].name,
                      'cost': self._card_cost(content.CARDS[cid]),
                      'effects': self.effects_for(cid, up)[0],
                      'playable': self._card_cost(content.CARDS[cid])
                      <= self.energy,
                      'upgraded': up}
                     for idx, (cid, up) in enumerate(self.hand)],
            'enemies': [{'name': e.name, 'hp': e.hp, 'max_hp': e.max_hp,
                         'block': e.block, 'intent': e.intent,
                         'vulnerable': e.vulnerable, 'poison': e.poison,
                         'alive': e.alive}
                        for e in self.enemies],
            'draw_count': len(self.draw_pile),
            'discard_count': len(self.discard_pile),
            'weapon': self.hero.weapon, 'armor': self.hero.armor,
            'relics': list(self.hero.relics),
            'potions': list(self.hero.potions),
        }

    # ---------- 结算工具 ----------

    def _target_none(self):
        return not any(e.alive for e in self.enemies)

    def pick_target(self, target):
        if target is not None and 0 <= target < len(self.enemies) \
                and self.enemies[target].alive:
            return self.enemies[target]
        for e in self.enemies:
            if e.alive:
                return e
        return None

    def hit_enemy(self, enemy, n, ignore_block=False):
        """返回日志行。n 为基准值，武器加成/力量/首次攻击加成/易伤在此结算。"""
        lines = []
        if enemy is None or not enemy.alive:
            return lines
        dmg = n + content.WEAPONS[self.hero.weapon].attack_bonus \
            + self.strength
        if self._pending_bonus:
            dmg += self._pending_bonus
            self._pending_bonus = 0
        if self.powers.get('first_attack_bonus') \
                and not self.attacked_this_turn:
            dmg += self.powers['first_attack_bonus']
        self.attacked_this_turn = True
        if enemy.vulnerable > 0:
            dmg = int(dmg * 1.5)
            enemy.vulnerable -= 1
        absorbed = 0
        if not ignore_block and enemy.block > 0:
            absorbed = min(enemy.block, dmg)
            enemy.block -= absorbed
            dmg -= absorbed
        enemy.hp -= dmg
        lines.append('【%s】受到 %d 点伤害（剩余 %d）。'
                     % (enemy.name, dmg, max(0, enemy.hp)))
        if enemy.hp <= 0:
            enemy.hp = 0
            enemy.block = 0
            lines.append('【%s】被击败！' % enemy.name)
        return lines

    def damage_hero(self, n):
        absorbed = min(self.block, n)
        self.block -= absorbed
        real = n - absorbed
        self.hero.hp -= real
        if real > 0:
            self._check_end()
        return absorbed, real

    def _check_end(self):
        if self.hero.hp <= 0:
            self.hero.hp = 0
            self.status = 'lose'
        elif all(not e.alive for e in self.enemies):
            self.status = 'win'

    def _tick_poison(self, hero_side):
        if hero_side:
            n = self.poison  # 毒不衰减（规格）
            self.hero.hp -= n
            self._check_end()
            return ['毒素发作，你受到 %d 点伤害。' % n]
        return []


def apply_effect(hero, combat, eff, target):
    """战斗效果原语解释器（content.PRIMITIVES 封闭集）。"""
    op = eff[0]
    lines = []
    if op == 'damage':
        lines.extend(combat.hit_enemy(combat.pick_target(target), eff[1]))
    elif op == 'pierce':
        lines.extend(combat.hit_enemy(combat.pick_target(target), eff[1],
                                      ignore_block=True))
    elif op == 'execute':
        frac, hi, lo = eff[1], eff[2], eff[3]
        t = combat.pick_target(target)
        n = hi if (t is not None and t.hp < t.max_hp * frac) else lo
        lines.extend(combat.hit_enemy(t, n))
    elif op == 'bonus_if_vulnerable':
        t = combat.pick_target(target)
        if t is not None and t.vulnerable > 0:
            combat._pending_bonus += eff[1]
            lines.append('猎印生效：本次攻击额外 +%d。' % eff[1])
    elif op == 'damage_all':
        for e in combat.enemies:
            lines.extend(combat.hit_enemy(e, eff[1]))
    elif op == 'block':
        combat.block += eff[1]
        lines.append('获得 %d 点格挡。' % eff[1])
    elif op == 'draw':
        lines.extend(combat._draw(eff[1]))
    elif op == 'energy':
        combat.energy += eff[1]
        lines.append('本回合能量 +%d。' % eff[1])
    elif op == 'hp_cost':
        hero.hp -= eff[1]
        lines.append('你失去 %d 点生命。' % eff[1])
        combat._check_end()
    elif op == 'heal':
        before = hero.hp
        hero.hp = min(hero.max_hp, hero.hp + eff[1])
        lines.append('回复 %d 点生命。' % (hero.hp - before))
    elif op == 'self_strength':
        combat.strength += eff[1]
        lines.append('力量 +%d。' % eff[1])
    elif op == 'self_vulnerable':
        combat.vulnerable += eff[1]
        lines.append('你获得 %d 层易伤。' % eff[1])
    elif op == 'vulnerable':
        t = combat.pick_target(target)
        if t is not None:
            t.vulnerable += eff[1]
            lines.append('【%s】获得 %d 层易伤。' % (t.name, eff[1]))
    elif op == 'poison':
        t = combat.pick_target(target)
        if t is not None:
            t.poison += eff[1]
            lines.append('【%s】中毒（%d）。' % (t.name, t.poison))
    elif op == 'vulnerable_all':
        for e in combat.enemies:
            if e.alive:
                e.vulnerable += eff[1]
        lines.append('所有敌人获得 %d 层易伤。' % eff[1])
    elif op == 'poison_all':
        for e in combat.enemies:
            if e.alive:
                e.poison += eff[1]
        lines.append('所有敌人中毒（%d 层）。' % eff[1])
    elif op == 'power':
        key, n = eff[1], eff[2]
        combat.powers[key] = combat.powers.get(key, 0) + n
        lines.append('持续效果生效：%s +%d。' % (key, n))
    elif op == 'exhaust':
        pass  # play_card 统一处理本战移出
    else:
        raise ValueError('未知战斗原语: %r' % (eff,))
    return lines
