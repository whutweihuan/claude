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
    weapon_sharpen: int = 0


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
        self.pending_move = None
        self.in_phase2 = False
        self._move_idx = 0

    @property
    def alive(self):
        return self.hp > 0


def merged_mods(hero):
    """聚合武器词条、防具词条与遗物钩子为扁平 dict。"""
    m = {}

    def add(src):
        for k, v in src.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                m[k] = v
            else:
                m[k] = m.get(k, 0) + v

    gear = content.WEAPONS[hero.weapon]
    m['attack_bonus'] = gear.attack_bonus + getattr(hero, 'weapon_sharpen', 0)
    add(gear.mods)
    if hero.armor:
        add(content.ARMORS[hero.armor].mods)
    for rid in hero.relics:
        add(content.RELICS[rid].hooks)
    return m


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
        self.mods = merged_mods(hero)
        self.death_saved = False
        self._cards_played_this_turn = 0

    # ---------- 回合流程 ----------

    def start(self):
        return self._begin_player_turn()

    def _begin_player_turn(self):
        lines = []
        m = self.mods
        self.turn += 1
        if not m.get('block_persist'):
            self.block = 0
        if self.poison > 0:
            self.hero.hp -= self.poison
            lines.append('毒素发作，你受到 %d 点伤害。' % self.poison)
            self._check_end()
            if self.status != 'playing':
                return lines
        if m.get('turn_start_self_damage'):
            self.hero.hp -= m['turn_start_self_damage']
            lines.append('燃火之刃灼伤你 %d 点。'
                         % m['turn_start_self_damage'])
            self._check_end()
            if self.status != 'playing':
                return lines
        if self.turn == 1:
            if m.get('start_block'):
                self.block += m['start_block']
                lines.append('装备提供 %d 点格挡。' % m['start_block'])
            if m.get('heal'):
                before = self.hero.hp
                self.hero.hp = min(self.hero.max_hp,
                                   self.hero.hp + m['heal'])
                if self.hero.hp > before:
                    lines.append('防具让你回复 %d 点生命。'
                                 % (self.hero.hp - before))
            if m.get('poison_start'):
                for e in self.enemies:
                    if e.alive:
                        e.poison += m['poison_start']
                lines.append('战纹面具让所有敌人中毒。')
            if m.get('low_hp_strength') and self.hero.hp \
                    < m.get('low_hp_pct', 0) * self.hero.max_hp:
                self.strength += m['low_hp_strength']
                lines.append('巨魔之牙生效：力量 +%d。'
                             % m['low_hp_strength'])
        energy = self.BASE_ENERGY + m.get('energy_per_turn', 0) \
            + self.powers.get('energy_per_turn', 0)
        if self.turn == 1:
            energy += m.get('first_turn_energy', 0)
        if m.get('every_n_turns') and self.turn % m['every_n_turns'] == 0:
            energy += m.get('turn_start_energy', 0)
        self.energy = max(0, energy)
        self.attacked_this_turn = False
        self._cards_played_this_turn = 0
        if self.powers.get('strength_per_turn'):
            self.strength += self.powers['strength_per_turn']
        n = self.BASE_DRAW + m.get('draw_per_turn', 0) \
            + self.powers.get('draw_per_turn', 0)
        if self.turn == 1:
            n += m.get('first_turn_draw', 0)
        lines.extend(self._draw(n))
        if self.status == 'playing':
            lines.extend(self._gen_intents())
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
        lines = []
        for e in self.enemies:
            if not e.alive:
                e.intent = None
                continue
            d = e.defn
            if d.phase2_at_half and not e.in_phase2 \
                    and e.hp <= e.max_hp / 2.0:
                e.in_phase2 = True
                e._move_idx = 0
                lines.append('【%s】发出咆哮，形态崩变！' % e.name)
            if e.in_phase2 and d.phase2_per_turn_strength:
                e.strength += d.phase2_per_turn_strength
            e.pending_move = self._pick_move(e)
            e.intent = format_intent(e.pending_move, e)
        return lines

    def _pick_move(self, enemy):
        pool = enemy.defn.phase2_moves if enemy.in_phase2 else enemy.defn.moves
        if enemy.defn.cycle and not enemy.in_phase2:
            mv = pool[enemy._move_idx % len(pool)]
            enemy._move_idx += 1
            return mv
        total = sum(m.weight for m in pool)
        r = self.rng.randrange(total)
        for m in pool:
            if r < m.weight:
                return m
            r -= m.weight
        return pool[-1]

    def use_potion(self, slot, target=None):
        if self.status != 'playing':
            return ['现在不在战斗中。']
        if not (0 <= slot < len(self.hero.potions)):
            return ['没有这瓶药水。']
        pid = self.hero.potions[slot]
        pot = content.POTIONS[pid]
        self.hero.potions.pop(slot)
        lines = ['你喝下【%s】。' % pot.name]
        for eff in pot.effects:
            lines.extend(apply_effect(self.hero, self, eff, target))
        self._check_end()
        return lines

    def end_turn(self):
        lines = []
        if self.powers.get('block_per_turn'):
            self.block += self.powers['block_per_turn']
        if self.mods.get('turn_end_heal'):
            before = self.hero.hp
            self.hero.hp = min(self.hero.max_hp,
                               self.hero.hp + self.mods['turn_end_heal'])
            if self.hero.hp > before:
                lines.append('旅行口粮回复 %d 点生命。'
                             % (self.hero.hp - before))
        self.discard_pile.extend(self.hand)
        self.hand = []
        lines.extend(self._enemy_turn())
        if self.status == 'playing':
            lines.extend(self._begin_player_turn())
        return lines

    def _enemy_turn(self):
        lines = []
        for e in self.enemies:
            if not e.alive or self.status != 'playing':
                continue
            if e.poison > 0:
                e.hp -= e.poison
                lines.append('【%s】毒发，受到 %d 点伤害。'
                             % (e.name, e.poison))
                if e.hp <= 0:
                    e.hp = 0
                    lines.append('【%s】被击败！' % e.name)
                    continue
            e.block = 0  # 敌人格挡在其行动开始时清零（规格 6.2）
            mv = e.pending_move or self._pick_move(e)
            e.pending_move = None
            lines.extend(self._exec_move(e, mv))
        return lines

    def _exec_move(self, enemy, mv):
        lines = []
        if mv.kind == 'attack':
            for _ in range(mv.hits):
                dmg = mv.damage + enemy.strength + enemy.dmg_add
                if self.vulnerable > 0:
                    dmg = int(dmg * 1.5)
                    self.vulnerable -= 1
                absorbed, real = self.damage_hero(dmg)
                text = '【%s】使用【%s】：' % (enemy.name, mv.name)
                if absorbed and real:
                    text += '格挡 %d，受到 %d 点伤害。' % (absorbed, real)
                elif absorbed:
                    text += '全部被格挡（%d）。' % absorbed
                else:
                    text += '你受到 %d 点伤害。' % real
                lines.append(text)
                if self.status != 'playing':
                    break
            thorns = self.mods.get('thorns', 0)
            if thorns and enemy.alive:
                enemy.hp -= thorns
                lines.append('尖刺/狼牙反伤：【%s】受到 %d 点伤害。'
                             % (enemy.name, thorns))
                if enemy.hp <= 0:
                    enemy.hp = 0
                    lines.append('【%s】被击败！' % enemy.name)
                self._check_end()
        else:
            if mv.block:
                enemy.block += mv.block
                lines.append('【%s】获得 %d 点格挡。' % (enemy.name, mv.block))
            if mv.strength:
                enemy.strength += mv.strength
                lines.append('【%s】力量 +%d。' % (enemy.name, mv.strength))
            if mv.kind == 'debuff' and mv.vulnerable:
                self.vulnerable += mv.vulnerable
                lines.append('你对【%s】的诅咒屈服：易伤 %d 层。'
                             % (enemy.name, mv.vulnerable))
            if mv.kind == 'poison' and mv.poison:
                self.poison += mv.poison
                lines.append('你中毒（%d）。' % self.poison)
        return lines

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
        self._cards_played_this_turn += 1
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
        cost = card.cost
        if self._cards_played_this_turn == 0:
            cost += self.mods.get('first_card_extra_cost', 0)
        if self.mods.get('cost_adjust_kind') == card.kind:
            cost = max(cost + self.mods.get('cost_adjust_delta', 0),
                       self.mods.get('cost_adjust_min', 0))
        return max(0, cost)

    def snapshot(self):
        return {
            'hp': self.hero.hp, 'max_hp': self.hero.max_hp,
            'block': self.block, 'energy': self.energy,
            'gold': self.hero.gold, 'turn': self.turn,
            'status': self.status,
            'hand': [{'idx': idx, 'name': content.CARDS[cid].name,
                      'cost': self._card_cost(content.CARDS[cid]),
                      'text': self.effects_for(cid, up)[1],
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
        dmg = n + self.mods.get('attack_bonus', 0) \
            + self.mods.get('attack_damage_base', 0) + self.strength
        if self._pending_bonus:
            dmg += self._pending_bonus
            self._pending_bonus = 0
        fab = self.powers.get('first_attack_bonus', 0) \
            + self.mods.get('first_attack_bonus', 0)
        if fab and not self.attacked_this_turn:
            dmg += fab
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
            ds = self._find_death_save()
            if ds is not None:
                rid, pct = ds
                self.hero.relics.remove(rid)
                self.hero.hp = int(-(-self.hero.max_hp * pct // 1))
                self.death_saved = True
                self.mods = merged_mods(self.hero)
                return
            self.hero.hp = 0
            self.status = 'lose'
        elif all(not e.alive for e in self.enemies):
            self.status = 'win'

    def _find_death_save(self):
        for rid in self.hero.relics:
            pct = content.RELICS[rid].hooks.get('death_save')
            if pct:
                return rid, pct
        return None


def format_intent(mv, enemy):
    parts = []
    if mv.kind == 'attack':
        d = mv.damage + enemy.strength + enemy.dmg_add
        parts.append('攻击 %d×%d' % (d, mv.hits) if mv.hits > 1
                     else '攻击 %d' % d)
    if mv.block:
        parts.append('格挡 %d' % mv.block)
    if mv.strength:
        parts.append('力量 +%d' % mv.strength)
    if mv.vulnerable:
        parts.append('施加易伤 %d' % mv.vulnerable)
    if mv.poison:
        parts.append('毒 %d' % mv.poison)
    return ' / '.join(parts) or '蓄势'


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


# ---------- 地图层级与奖励结算 ----------

def layer_tier(layer):
    return 1 if layer <= 4 else (2 if layer <= 8 else 3)


RARITY_WEIGHTS_EARLY = [('common', 8), ('uncommon', 3), ('rare', 1)]
RARITY_WEIGHTS_LATE = [('common', 5), ('uncommon', 4), ('rare', 2)]


def relic_pool(source):
    """source: 'common' 普通掉落 / 'elite' 精英三选一 / 'shop' 商店 / 'all'。"""
    rarities = {'common': ('common',), 'elite': ('uncommon', 'rare'),
                'shop': ('common', 'uncommon', 'rare'),
                'all': ('common', 'uncommon', 'rare')}[source]
    return [rid for rid, r in content.RELICS.items()
            if r.rarity in rarities]


def card_reward_choice(rng, layer, n=3):
    pools = {rar: [cid for cid, c in content.CARDS.items()
                   if content.CARD_RARITY[cid] == rar]
             for rar, _w in RARITY_WEIGHTS_EARLY}
    weights = RARITY_WEIGHTS_EARLY if layer < 7 else RARITY_WEIGHTS_LATE
    total = sum(w for _r, w in weights)
    picks = []
    guard = 0
    while len(picks) < n and guard < 200:
        guard += 1
        r = rng.randrange(total)
        chosen_rar = weights[-1][0]
        for rar, w in weights:
            if r < w:
                chosen_rar = rar
                break
            r -= w
        cid = rng.choice(pools[chosen_rar])
        card = (cid, False)
        if card not in picks:
            picks.append(card)
    return picks


def settle_combat(hero, rng, layer, kind='normal'):
    """战斗胜利后的奖励结算。返回 {gold, relic_choices, relic_drop,
    card_choices, lines}。金币直接入账。"""
    mods = merged_mods(hero)
    tier = layer_tier(layer)
    lines = []
    if kind == 'elite':
        gold = rng.randint(33, 50)
    else:
        gold = rng.randint(13, 20) + tier * 4
    if mods.get('gold_mult'):
        gold = int(gold * mods['gold_mult'])
    hero.gold += gold
    lines.append('获得 %d 金币。' % gold)
    result = {'gold': gold, 'relic_choices': [], 'relic_drop': None,
              'card_choices': [], 'lines': lines}
    if kind == 'elite':
        pool = relic_pool('elite')
        choices = []
        while len(choices) < 3:
            pick = rng.choice(pool)
            if pick not in choices:
                choices.append(pick)
        result['relic_choices'] = choices
    else:
        if rng.random() < 0.2:
            result['relic_drop'] = rng.choice(relic_pool('common'))
        n = 3 + int(mods.get('card_reward_extra', 0))
        result['card_choices'] = card_reward_choice(rng, layer, n)
    if mods.get('combat_end_heal'):
        before = hero.hp
        hero.hp = min(hero.max_hp, hero.hp + mods['combat_end_heal'])
        if hero.hp > before:
            lines.append('炭炉石温暖着你：回复 %d 点生命。'
                         % (hero.hp - before))
    return result


# ---------- 地图生成 ----------

NORMAL_LAYERS = 10
BOSS_LAYER = 11
ELITE_LAYERS = (6, 9)
CAMPFIRE_LAYERS = (4, 7, 8, 10)


@dataclass
class MapNode:
    id: int
    layer: int
    kind: str
    next: list = field(default_factory=list)


class GameMap(object):
    def __init__(self, nodes, entry_ids, boss_id):
        self.nodes = {n.id: n for n in nodes}
        self.entry_ids = entry_ids
        self.boss_id = boss_id

    def layer_nodes(self, layer):
        return [n for n in self.nodes.values() if n.layer == layer]


def generate_map(rng):
    counts = [2] + [1] * (NORMAL_LAYERS - 1)
    remaining = rng.randint(14, 19) - sum(counts)
    while remaining > 0:
        i = rng.randrange(1, NORMAL_LAYERS)
        if counts[i] < 3:
            counts[i] += 1
            remaining -= 1
    nodes = []
    by_layer = {}
    nid = 0
    for layer in range(1, NORMAL_LAYERS + 1):
        lst = []
        for _ in range(counts[layer - 1]):
            nid += 1
            node = MapNode(nid, layer, 'combat')
            nodes.append(node)
            lst.append(node)
        by_layer[layer] = lst

    def free_node(layer):
        cands = [n for n in by_layer[layer] if n.kind == 'combat']
        node = rng.choice(cands)
        return node

    for layer in ELITE_LAYERS:
        free_node(layer).kind = 'elite'
    for layer in CAMPFIRE_LAYERS:
        free_node(layer).kind = 'campfire'
    shop_cands = [n for l in range(2, 9) for n in by_layer[l]
                  if n.kind == 'combat']
    rng.choice(shop_cands).kind = 'shop'
    event_cands = [n for n in nodes if n.kind == 'combat'
                   and n.layer > 1]
    for node in rng.sample(event_cands, 2):
        node.kind = 'event'
    rest = [n for n in nodes if n.kind == 'combat' and n.layer > 1]
    for node in rest:
        node.kind = rng.choices(['combat', 'event', 'chest'],
                                weights=[5, 2, 2])[0]

    boss_id = nid + 1
    boss = MapNode(boss_id, BOSS_LAYER, 'boss')
    nodes.append(boss)

    for layer in range(1, NORMAL_LAYERS):
        cur = by_layer[layer]
        nxt = by_layer[layer + 1]
        have_parent = set()
        for node in cur:
            k = 1 if len(nxt) == 1 else rng.choice([1, 2])
            for child in rng.sample(nxt, k):
                if child.id not in node.next:
                    node.next.append(child.id)
                have_parent.add(child.id)
        for child in nxt:
            if child.id not in have_parent:
                parent = rng.choice(cur)
                parent.next.append(child.id)
                have_parent.add(child.id)
    for node in by_layer[NORMAL_LAYERS]:
        node.next.append(boss_id)

    return GameMap(nodes, [n.id for n in by_layer[1]], boss_id)


# ---------- 一局编排 ----------

def make_encounter(rng, layer):
    for a, b, pool, max_count in content.ENCOUNTERS:
        if a <= layer <= b:
            ids = [p[0] for p in pool]
            weights = [p[1] for p in pool]
            count = rng.randint(1, max_count)
            return [rng.choices(ids, weights=weights)[0]
                    for _ in range(count)]
    return ['goblin']


class Run(object):
    SHARPEN_MAX = 3
    CHEST_WEAPONS_EARLY = ('longsword', 'spear')
    CHEST_WEAPONS_LATE = ('flame', 'twinblades', 'axe')
    CHEST_ARMORS_EARLY = ('cloth', 'leather')
    CHEST_ARMORS_LATE = ('spiked', 'guardian', 'plate')

    def __init__(self, seed):
        self.seed = seed
        self.rng = random.Random(seed)
        self.hero = Hero(max_hp=80, hp=80, gold=0,
                         deck=list(content.STARTER_DECK),
                         weapon='rusty', armor=None, relics=[], potions=[])
        self.map = generate_map(self.rng)
        self.current = None
        self.visited = set()
        self.node_done = False
        self.pending = None
        self.active = None
        self.shop = None
        self._loot = None
        self.node_obj = None
        self.seen_events = set()
        self.finished = False
        self.outcome = None
        self.kills = 0
        self.gold_earned = 0
        self.depth_reached = 0
        self.stats = {}

    # ---- 移动与节点 ----

    def choices(self):
        if self.finished or self.pending is not None:
            return []
        if self.current is None:
            return list(self.map.entry_ids)
        if not self.node_done:
            return []
        return [nid for nid in self.map.nodes[self.current].next
                if nid not in self.visited]

    def go(self, node_id):
        if node_id not in self.choices():
            raise ValueError('现在不能移动到该节点。')
        self.current = node_id
        self.visited.add(node_id)
        node = self.map.nodes[node_id]
        self.depth_reached = max(self.depth_reached, node.layer)
        self.node_done = False
        self.active = None
        self.shop = None
        self._loot = None
        self.node_obj = None

    def enter(self):
        node = self.map.nodes[self.current]
        kind = node.kind
        self.node_obj = None
        tier = layer_tier(node.layer)
        if kind == 'combat':
            ids = make_encounter(self.rng, node.layer)
            self.active = Combat(self.hero, ids, self.rng, tier)
            self.active.start()
            return ('combat', self.active)
        if kind == 'elite':
            self.active = Combat(
                self.hero, [self.rng.choice(content.ELITE_IDS)],
                self.rng, tier)
            self.active.start()
            return ('elite', self.active)
        if kind == 'boss':
            # 规格 6.10 的 boss 血量 160 是字面终值，不随 tier 放大
            self.active = Combat(self.hero, [content.BOSS_ID], self.rng, 1)
            self.active.start()
            return ('boss', self.active)
        if kind == 'campfire':
            return ('campfire', None)
        if kind == 'event':
            self.node_obj = self._pick_event()
            return ('event', self.node_obj)
        if kind == 'chest':
            self._loot = self._make_loot(node.layer)
            self.node_obj = self._loot
            return ('chest', self._loot)
        if kind == 'shop':
            self.shop = make_shop(self.rng, self.hero, node.layer)
            self.node_obj = self.shop
            return ('shop', self.shop)
        raise ValueError('未知节点类型 %r' % kind)

    def _pick_event(self):
        unseen = [e for e in content.EVENTS.values()
                  if e.id not in self.seen_events]
        if not unseen:
            unseen = list(content.EVENTS.values())
        ev = self.rng.choice(unseen)
        self.seen_events.add(ev.id)
        return ev

    def _make_loot(self, layer):
        gold = self.rng.randint(20, 40)
        gear_kind = self.rng.choice(['weapon', 'armor'])
        if gear_kind == 'weapon':
            pool = (self.CHEST_WEAPONS_LATE if layer >= 6
                    else self.CHEST_WEAPONS_EARLY)
        else:
            pool = (self.CHEST_ARMORS_LATE if layer >= 6
                    else self.CHEST_ARMORS_EARLY)
        return {'gold': gold, 'kind': gear_kind,
                'id': self.rng.choice(pool)}

    # ---- 战斗结算 ----

    def combat_finished(self):
        combat = self.active
        if combat is None:
            return
        self.kills += sum(1 for e in combat.enemies if not e.alive)
        node = self.map.nodes[self.current]
        if combat.status == 'win':
            if node.kind == 'boss':
                self.add_relic('crown')
                self._finish('win')
            else:
                sk = 'elite' if node.kind == 'elite' else 'normal'
                pending = settle_combat(self.hero, self.rng, node.layer,
                                        kind=sk)
                self.gold_earned += pending['gold']
                if pending['relic_drop']:
                    self.add_relic(pending['relic_drop'])
                self.pending = pending
        elif combat.status == 'lose':
            self._finish('dead')
        self.active = None

    def take_card(self, i):
        if not (self.pending and self.pending['card_choices']):
            return ['没有可选的卡牌。']
        if not (0 <= i < len(self.pending['card_choices'])):
            return ['没有这张牌，请重新选择。']
        cid, up = self.pending['card_choices'][i]
        self.hero.deck.append((cid, up))
        return self._after_pending_step('你将【%s】加入了卡组。'
                                        % content.CARDS[cid].name)

    def skip_card(self):
        return self._after_pending_step('你放弃了卡牌奖励。')

    def choose_relic(self, i):
        if not (self.pending and self.pending['relic_choices']):
            return ['没有可选的遗物。']
        if not (0 <= i < len(self.pending['relic_choices'])):
            return ['没有这件遗物，请重新选择。']
        rid = self.pending['relic_choices'][i]
        self.add_relic(rid)
        return self._after_pending_step('你取走了【%s】！'
                                        % content.RELICS[rid].name)

    def skip_relic(self):
        return self._after_pending_step('你留下了遗物。')

    def _after_pending_step(self, line):
        p = self.pending
        if p is None:
            self.node_done = True
            return [line]
        if p['relic_choices']:
            p['relic_choices'] = []
        elif p['card_choices']:
            p['card_choices'] = []
        if not (p['relic_choices'] or p['card_choices']):
            self.pending = None
            self.node_done = True
        return [line]

    # ---- 火堆 ----

    def campfire_options(self):
        node = self.map.nodes[self.current]
        if node.kind != 'campfire' or self.node_done:
            return []
        forge_slots = [idx for idx, (cid, up) in enumerate(self.hero.deck)
                       if not up and content.CARDS[cid].upgrade]
        return [
            {'kind': 'sleep', 'available': self.hero.hp < self.hero.max_hp,
             'text': '睡觉：回复 %d 点生命'
                     % int(self.hero.max_hp * 0.3)},
            {'kind': 'forge', 'available': bool(forge_slots),
             'cards': forge_slots, 'text': '锻造：强化一张牌'},
            {'kind': 'sharpen',
             'available': self.hero.weapon_sharpen < self.SHARPEN_MAX,
             'count': self.hero.weapon_sharpen,
             'text': '打磨武器：攻击伤害 +1（本局限 %d 次）'
                     % self.SHARPEN_MAX},
        ]

    def campfire(self, kind, card_slot=None):
        if self.map.nodes[self.current].kind != 'campfire':
            return ['这里没有火堆。']
        if self.node_done:
            return ['火堆已经用过了。']
        if kind == 'sleep':
            if self.hero.hp >= self.hero.max_hp:
                return ['你生命已满，不必睡觉。火堆还在。']
            before = self.hero.hp
            self.hero.hp = min(self.hero.max_hp,
                               int(self.hero.hp + self.hero.max_hp * 0.3))
            self.node_done = True
            return ['你在火堆旁睡了一觉，回复 %d 点生命。'
                    % (self.hero.hp - before)]
        if kind == 'forge':
            forge_list = [o for o in self.campfire_options()
                          if o['kind'] == 'forge']
            valid = forge_list[0]['cards'] if forge_list else []
            if card_slot is None or card_slot not in valid:
                return ['这张牌无法锻造，请重新选择。']
            cid, _up = self.hero.deck[card_slot]
            self.hero.deck[card_slot] = (cid, True)
            self.node_done = True
            return ['火光照亮铁砧：【%s+】焕然一新。'
                    % content.CARDS[cid].name]
        if kind == 'sharpen':
            if self.hero.weapon_sharpen >= self.SHARPEN_MAX:
                return ['武器打磨已达上限（+%d）。' % self.SHARPEN_MAX]
            self.hero.weapon_sharpen += 1
            self.node_done = True
            return ['你把武器磨得雪亮（攻击伤害 +%d）。'
                    % self.hero.weapon_sharpen]
        if kind == 'leave':
            self.node_done = True
            return ['你只烤了烤手，继续赶路。']
        return ['火堆没有这个选项。']

    # ---- 宝箱 / 事件 / 商店 ----

    def take_chest(self, equip):
        if self._loot is None:
            return ['这里没有宝箱。']
        loot = self._loot
        self._loot = None
        self.hero.gold += loot['gold']
        self.gold_earned += loot['gold']
        gear = (content.WEAPONS.get(loot['id'])
                or content.ARMORS.get(loot['id']))
        lines = ['宝箱里有 %d 金币。' % loot['gold']]
        if equip:
            if loot['kind'] == 'weapon':
                old = content.WEAPONS[self.hero.weapon].name
                self.hero.weapon = loot['id']
                lines.append('你装备了【%s】，丢下【%s】。'
                             % (gear.name, old))
            else:
                self.hero.armor = loot['id']
                lines.append('你装备了【%s】。' % gear.name)
        else:
            lines.append('你看了一眼【%s】，走开了。' % gear.name)
        self.node_done = True
        return lines

    def finish_event(self):
        self.node_done = True
        return []

    def start_event_combat(self, enemy_ids):
        node = self.map.nodes[self.current]
        self.active = Combat(self.hero, list(enemy_ids), self.rng,
                             layer_tier(node.layer))
        self.active.start()
        return self.active

    def close_shop(self):
        self.node_done = True
        return []

    # ---- 局外药水 ----

    def use_potion_outside(self, slot):
        if not (0 <= slot < len(self.hero.potions)):
            return ['没有这瓶药水。']
        pid = self.hero.potions[slot]
        if not potion_outside_usable(pid):
            return ['【%s】必须在战斗中使用。' % content.POTIONS[pid].name]
        self.hero.potions.pop(slot)
        n = content.POTIONS[pid].effects[0][1]
        before = self.hero.hp
        self.hero.hp = min(self.hero.max_hp, self.hero.hp + n)
        return ['你喝下【%s】，回复 %d 点生命。'
                % (content.POTIONS[pid].name, self.hero.hp - before)]

    def gain_potion(self, pid=None):
        """事件/商店入包：满 3 瓶时返回提示且物品不损失。"""
        pool = list(content.POTIONS) if pid is None else [pid]
        if pid is None:
            pid = self.rng.choice(pool)
        if len(self.hero.potions) >= 3:
            return ['药水背包已满（3/3），【%s】被你留在了原地。'
                    % content.POTIONS[pid].name], False
        self.hero.potions.append(pid)
        return ['你获得了药水【%s】。' % content.POTIONS[pid].name], True

    # ---- 遗物 ----

    def add_relic(self, rid):
        if rid in self.hero.relics:
            return
        self.hero.relics.append(rid)
        instant = content.RELICS[rid].hooks.get('instant_gold')
        if instant:
            self.hero.gold += instant
            self.gold_earned += instant

    def _finish(self, outcome):
        self.outcome = outcome
        self.finished = True
        self.pending = None
        self.stats = {'depth': self.depth_reached, 'kills': self.kills,
                      'gold_earned': self.gold_earned, 'seed': self.seed}


# ---------- 商店与药水 ----------

CARD_PRICE = {'common': 45, 'uncommon': 65, 'rare': 90}
WEAPON_PRICE = {'longsword': 100, 'spear': 100, 'flame': 100,
                'twinblades': 120, 'axe': 150}
ARMOR_PRICE = {'cloth': 60, 'leather': 80, 'spiked': 100, 'guardian': 110,
               'plate': 130}
RELIC_PRICE = {'common': 110, 'uncommon': 140, 'rare': 175}
POTION_PRICE = 45
REMOVE_COST = 65


@dataclass
class Slot:
    kind: str
    content_id: str
    base_price: int
    price: int
    sold: bool = False


class Shop(object):
    def __init__(self, slots, remove_cost):
        self.slots = slots
        self.remove_cost = remove_cost


def make_shop(rng, hero, layer):
    disc = merged_mods(hero).get('shop_discount', 1.0)
    slots = []

    def add(kind, cid, base):
        slots.append(Slot(kind, cid, base, int(base * disc)))

    for cid, _up in card_reward_choice(rng, layer, 2):
        add('card', cid, CARD_PRICE[content.CARD_RARITY[cid]])
    wid = rng.choice(list(WEAPON_PRICE))
    add('weapon', wid, WEAPON_PRICE[wid])
    aid = rng.choice(list(ARMOR_PRICE))
    add('armor', aid, ARMOR_PRICE[aid])
    rid = rng.choice(relic_pool('shop'))
    add('relic', rid, RELIC_PRICE[content.RELICS[rid].rarity])
    for pid in rng.sample(list(content.POTIONS), 2):
        add('potion', pid, POTION_PRICE)
    return Shop(slots, int(REMOVE_COST * disc))


POTION_OUTSIDE_OPS = frozenset(['heal'])


def potion_outside_usable(pid):
    return all(eff[0] in POTION_OUTSIDE_OPS
               for eff in content.POTIONS[pid].effects)


def _give_potion(hero):
    """入包药水（商店/事件共用）；满 3 瓶返回 False，物品不损失。"""
    if len(hero.potions) >= 3:
        return False
    return True


def buy(run, slot_idx):
    shop = run.shop
    if shop is None:
        return ['这里没有商店。']
    if not (0 <= slot_idx < len(shop.slots)):
        return ['没有这件商品，请重新选择。']
    slot = shop.slots[slot_idx]
    if slot.sold:
        return ['这件已经售罄了。']
    if run.hero.gold < slot.price:
        return ['金币不足，还差 %d。' % (slot.price - run.hero.gold)]
    if slot.kind == 'potion' and len(run.hero.potions) >= 3:
        return ['药水背包已满（3/3），先用手里的。']
    hero = run.hero
    hero.gold -= slot.price
    slot.sold = True
    if slot.kind == 'card':
        hero.deck.append((slot.content_id, False))
        return ['你买下了【%s】。' % content.CARDS[slot.content_id].name]
    if slot.kind == 'weapon':
        hero.weapon = slot.content_id
        return ['你换上了【%s】。' % content.WEAPONS[slot.content_id].name]
    if slot.kind == 'armor':
        hero.armor = slot.content_id
        return ['你穿上了【%s】。' % content.ARMORS[slot.content_id].name]
    if slot.kind == 'relic':
        run.add_relic(slot.content_id)
        return ['你请下了【%s】。' % content.RELICS[slot.content_id].name]
    hero.potions.append(slot.content_id)
    return ['你买下了【%s】。' % content.POTIONS[slot.content_id].name]


def buy_removal(run, deck_idx):
    shop = run.shop
    if shop is None:
        return ['这里没有商店。']
    if run.hero.gold < shop.remove_cost:
        return ['金币不足，删牌服务要 %d 金币。' % shop.remove_cost]
    if not (0 <= deck_idx < len(run.hero.deck)):
        return ['卡组里没有这张牌。']
    cid, up = run.hero.deck.pop(deck_idx)
    run.hero.gold -= shop.remove_cost
    name = content.CARDS[cid].name + ('+' if up else '')
    return ['你与商人耳语几句，【%s】消失在火焰里。' % name]


# ---------- 事件结算 ----------

def _outcome_block_reason(run, outcomes):
    for eff in outcomes:
        op = eff[0]
        if op == 'hp' and eff[1] < 0 and run.hero.hp + eff[1] <= 0:
            return '你撑不住这股代价，放弃了尝试。'
        if op == 'gold' and eff[1] < 0 and run.hero.gold + eff[1] < 0:
            return '金币不足。'
        if op == 'branch':
            for _w, sub in eff[1]:
                reason = _outcome_block_reason(run, sub)
                if reason:
                    return reason
    return None


def event_option_available(run, event, idx):
    if not (0 <= idx < len(event.options)):
        return False
    return _outcome_block_reason(run, event.options[idx].outcome) is None


def apply_event(run, event, idx):
    """返回 (日志行, follow)。follow 为 None 或 ('combat', enemy_ids)。"""
    if not (0 <= idx < len(event.options)):
        return ['没有这个选项，请重新选择。'], None
    opt = event.options[idx]
    reason = _outcome_block_reason(run, opt.outcome)
    if reason:
        return [reason], None
    lines = ['你选择：%s。' % opt.label]
    follow = _exec_outcomes(run, opt.outcome, lines)
    if follow is None:
        run.finish_event()
    return lines, follow


def _exec_outcomes(run, outcomes, lines):
    rng = run.rng
    hero = run.hero
    follow = None
    for eff in outcomes:
        op = eff[0]
        if op == 'hp':
            hero.hp += eff[1]
            if hero.hp > hero.max_hp:
                hero.hp = hero.max_hp
            if eff[1] < 0:
                lines.append('你失去 %d 点生命。' % -eff[1])
            else:
                lines.append('回复 %d 点生命。' % eff[1])
        elif op == 'heal':
            before = hero.hp
            hero.hp = min(hero.max_hp, hero.hp + eff[1])
            lines.append('回复 %d 点生命。' % (hero.hp - before))
        elif op == 'gold':
            hero.gold += eff[1]
            if eff[1] > 0:
                run.gold_earned += eff[1]
                lines.append('获得 %d 金币。' % eff[1])
            else:
                lines.append('花费 %d 金币。' % -eff[1])
        elif op == 'gain_potion_random':
            msg, _ok = run.gain_potion()
            lines.append(msg)
        elif op == 'gain_relic_random':
            pool = [rid for rid, r in content.RELICS.items()
                    if r.rarity == eff[1]]
            rid = rng.choice(pool)
            run.add_relic(rid)
            lines.append('你获得了遗物【%s】。' % content.RELICS[rid].name)
        elif op == 'gain_gear_random':
            kind, tier = eff[1], eff[2]
            late = tier >= 2
            if kind == 'weapon':
                pool = (Run.CHEST_WEAPONS_LATE if late
                        else Run.CHEST_WEAPONS_EARLY)
                gid = rng.choice(pool)
                hero.weapon = gid
                lines.append('你换上了【%s】。'
                             % content.WEAPONS[gid].name)
            else:
                pool = (Run.CHEST_ARMORS_LATE if late
                        else Run.CHEST_ARMORS_EARLY)
                gid = rng.choice(pool)
                hero.armor = gid
                lines.append('你穿上了【%s】。'
                             % content.ARMORS[gid].name)
        elif op == 'add_card_random':
            pool = [cid for cid, c in content.CARDS.items()
                    if content.CARD_RARITY[cid] == eff[1]]
            cid = rng.choice(pool)
            hero.deck.append((cid, False))
            lines.append('你学会了【%s】。' % content.CARDS[cid].name)
        elif op == 'upgrade_random_card':
            slots = [i for i, (cid, up) in enumerate(hero.deck)
                     if not up and content.CARDS[cid].upgrade]
            if slots:
                i = rng.choice(slots)
                cid, _up = hero.deck[i]
                hero.deck[i] = (cid, True)
                lines.append('【%s+】被无名之神祝福了。'
                             % content.CARDS[cid].name)
            else:
                lines.append('诸神对你的卡组无动于衷。')
        elif op == 'remove_random_card':
            if len(hero.deck) > 1:
                i = rng.randrange(len(hero.deck))
                cid, up = hero.deck.pop(i)
                name = content.CARDS[cid].name + ('+' if up else '')
                lines.append('【%s】莫名其妙地消失了。' % name)
        elif op == 'start_combat':
            follow = ('combat', list(eff[1]))
        elif op == 'branch':
            total = sum(w for w, _o in eff[1])
            r = rng.randrange(total)
            for w, sub in eff[1]:
                if r < w:
                    sub_follow = _exec_outcomes(run, sub, lines)
                    if sub_follow is not None:
                        follow = sub_follow
                    break
                r -= w
        elif op == 'nothing':
            pass
        else:
            raise ValueError('未知事件原语 %r' % (eff,))
    return follow
