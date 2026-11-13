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
    m['attack_bonus'] = gear.attack_bonus
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
        for e in self.enemies:
            if not e.alive:
                e.intent = None
                continue
            d = e.defn
            if d.phase2_at_half and not e.in_phase2 \
                    and e.hp <= e.max_hp / 2.0:
                e.in_phase2 = True
                e._move_idx = 0
            e.pending_move = self._pick_move(e)
            e.intent = format_intent(e.pending_move, e)

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
            if e.defn.phase2_at_half and not e.in_phase2 \
                    and e.hp <= e.max_hp / 2.0:
                e.in_phase2 = True
                e._move_idx = 0
                lines.append('【%s】发出咆哮，形态崩变！' % e.name)
            if e.in_phase2 and e.defn.phase2_per_turn_strength:
                e.strength += e.defn.phase2_per_turn_strength
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
        gold = rng.randint(30, 45)
    else:
        gold = rng.randint(12, 18) + tier * 4
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
        if rng.random() < 0.15:
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
