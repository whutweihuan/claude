# -*- coding: utf-8 -*-
"""勇士冒险核心逻辑单元测试。"""
import random
import unittest

import content
import core


def make_hero(deck, weapon='rusty', hp=80):
    return core.Hero(max_hp=80, hp=hp, gold=0, deck=deck, weapon=weapon,
                     armor=None, relics=[], potions=[])


def seed_hand(combat, card_ids):
    """测试内布置确定性手牌（抽牌随机性不是被测行为）。

    优先把牌堆/弃牌堆里的原件拿进手牌，避免制造重复卡牌。
    """
    combat.discard_pile.extend(combat.hand)
    combat.hand = []
    for cid in card_ids:
        card = (cid, False)
        for pile in (combat.draw_pile, combat.discard_pile):
            if card in pile:
                pile.remove(card)
                break
        combat.hand.append(card)


def make_combat(deck, enemies, weapon='rusty', hp=80, seed=42):
    return core.Combat(make_hero(deck, weapon=weapon, hp=hp), enemies,
                       random.Random(seed), tier=1)


class ContentTableTests(unittest.TestCase):

    def test_anchor_card_values(self):
        s, d = content.CARDS['strike'], content.CARDS['defend']
        self.assertEqual((s.cost, s.effects), (1, [('damage', 6)]))
        self.assertEqual((d.cost, d.effects), (1, [('block', 5)]))
        self.assertEqual(s.upgrade['effects'], [('damage', 9)])
        self.assertEqual(content.STARTER_DECK,
                         [('strike', False)] * 6 + [('defend', False)] * 4)

    def test_pool_sizes_and_uniqueness(self):
        self.assertGreaterEqual(len(content.CARDS), 28)
        self.assertGreaterEqual(len(content.WEAPONS), 6)
        self.assertGreaterEqual(len(content.ARMORS), 5)
        self.assertGreaterEqual(len(content.POTIONS), 5)
        all_ids = (list(content.CARDS) + list(content.WEAPONS)
                   + list(content.ARMORS) + list(content.POTIONS))
        self.assertEqual(len(set(all_ids)), len(all_ids))

    def test_all_effects_use_closed_primitives(self):
        content.validate_content()

    def test_enemy_tables(self):
        self.assertGreaterEqual(len(content.ENEMIES), 10)
        for e in content.ENEMIES.values():
            self.assertGreaterEqual(len(e.moves), 2)
            self.assertTrue(all(m.kind in ('attack', 'block', 'buff',
                                           'debuff', 'poison')
                                for m in e.moves))
        boss = content.ENEMIES[content.BOSS_ID]
        self.assertTrue(boss.is_boss and boss.phase2_at_half
                        and boss.hp >= 140)
        self.assertGreaterEqual(len(content.ELITE_IDS), 2)

    def test_events(self):
        self.assertGreaterEqual(len(content.EVENTS), 8)
        for ev in content.EVENTS.values():
            self.assertTrue(2 <= len(ev.options) <= 3)
        content.validate_content()

    def test_encounters_cover_layers(self):
        for layer in range(1, 12):
            self.assertTrue(
                any(a <= layer <= b for a, b, _, _ in content.ENCOUNTERS),
                layer)

    def test_validate_rejects_bad_table(self):
        # 证明 validate_content 不是空壳：篡改一张牌的费用与效果后必须抛 ValueError
        original_card = content.CARDS['strike']
        try:
            content.CARDS['strike'] = content.Card(
                id='strike', name='打击', cost=9, kind='attack', text='x',
                effects=[('nosuch_primitive', 1)], upgrade=None)
            with self.assertRaises(ValueError):
                content.validate_content()
        finally:
            content.CARDS['strike'] = original_card
        content.validate_content()


class CombatPlayerTests(unittest.TestCase):

    def setUp(self):
        self.combat = make_combat(content.STARTER_DECK, ['goblin'])
        self.combat.start()

    def test_opening_hand_and_energy(self):
        self.assertEqual(len(self.combat.hand), 5)
        self.assertEqual(self.combat.energy, 3)

    def test_strike_and_defend_values(self):
        self.combat.play_card(self.combat.hand.index(('strike', False)))
        self.assertEqual(self.combat.enemies[0].hp, 8)
        self.combat.play_card(self.combat.hand.index(('defend', False)))
        self.assertEqual(self.combat.block, 5)
        self.assertEqual(self.combat.energy, 1)

    def test_cannot_play_without_energy(self):
        deck = [('strike', False)] * 5 + [('defend', False)] * 5
        c = make_combat(deck, ['knight'], seed=7)
        c.start()
        seed_hand(c, ['strike', 'strike', 'strike', 'defend'])
        for _ in range(3):
            c.play_card(0)
        self.assertEqual(c.energy, 0)
        lines = c.play_card(0)
        self.assertTrue(any('能量' in l for l in lines))
        self.assertEqual(c.enemies[0].hp, 32 - 18)
        self.assertEqual(len(c.hand), 1)

    def test_hand_discarded_at_end_of_turn(self):
        self.combat.play_card(self.combat.hand.index(('defend', False)))
        self.assertGreater(self.combat.block, 0)
        self.combat.end_turn()
        self.assertEqual(self.combat.block, 0)
        self.assertEqual(len(self.combat.discard_pile), 5)
        self.assertEqual(len(self.combat.hand), 5)

    def test_draw_reshuffles_discard(self):
        deck = [('warcry', False)] * 3 + [('defend', False)] * 7
        c = make_combat(deck, ['knight'], seed=3)
        c.start()
        c.end_turn()
        self.assertEqual(len(c.draw_pile), 0)
        c.end_turn()
        self.assertEqual(len(c.draw_pile), 5)
        self.assertEqual(len(c.discard_pile), 0)
        self.assertEqual(len(c.hand), 5)

    def test_weapon_bonus_applies_per_hit(self):
        c = make_combat(content.STARTER_DECK, ['goblin'], weapon='longsword')
        c.start()
        seed_hand(c, ['twin'])
        c.play_card(0)
        self.assertEqual(c.enemies[0].hp, 14 - (3 + 1) * 2)

    def test_strength_and_vulnerable_math(self):
        c = make_combat(content.STARTER_DECK, ['goblin'], seed=11)
        c.start()
        seed_hand(c, ['trance'])
        c.play_card(0)
        c.end_turn()
        seed_hand(c, ['strike'])
        c.play_card(0)
        self.assertEqual(c.enemies[0].hp, 14 - 8)

        c2 = make_combat(content.STARTER_DECK, ['goblin'], seed=12)
        c2.start()
        seed_hand(c2, ['taunt', 'strike'])
        c2.play_card(0)
        c2.play_card(0)
        self.assertEqual(c2.enemies[0].hp, 14 - 9)
        self.assertEqual(c2.enemies[0].vulnerable, 1)

    def test_power_card_persists(self):
        c = make_combat(content.STARTER_DECK, ['knight'], seed=13)
        c.start()
        seed_hand(c, ['fury'])
        c.play_card(0)
        c.end_turn()
        seed_hand(c, ['strike', 'strike'])
        c.play_card(0)
        c.play_card(0)
        self.assertEqual(c.enemies[0].hp, 32 - 9 - 6)

    def test_war_drum_effective_lines_logged(self):
        deck = [('war_drum', False)] * 2 + [('defend', False)] * 8
        c = make_combat(deck, ['goblin'], seed=16)
        c.start()
        seed_hand(c, ['war_drum'])
        c.play_card(0)
        lines = c.end_turn()
        self.assertTrue(any('持续格挡' in l for l in lines), lines)
        self.assertTrue(any('持续力量' in l for l in lines), lines)
        self.assertEqual(c.strength, 1)

    def test_exhaust_card_leaves_combat(self):
        deck = [('rip', False)] + [('defend', False)] * 9
        c = make_combat(deck, ['knight'], seed=14)
        c.start()
        seed_hand(c, ['rip'])
        c.play_card(0)
        self.assertEqual(c.enemies[0].hp, 32 - 4)
        self.assertEqual(c.exhausted, [('rip', False)])
        self.assertNotIn(('rip', False), c.discard_pile)
        c.end_turn()
        all_after = c.draw_pile + c.hand + c.discard_pile
        self.assertNotIn(('rip', False), all_after)

    def test_pierce_ignores_block(self):
        c = make_combat(content.STARTER_DECK, ['goblin'], seed=15)
        c.start()
        c.enemies[0].block = 10
        seed_hand(c, ['pierce'])
        c.play_card(0)
        self.assertEqual(c.enemies[0].hp, 14 - 8)


class CombatEnemyTests(unittest.TestCase):

    def set_next_move(self, combat, enemy_idx, **kw):
        combat.enemies[enemy_idx].pending_move = content.Move(**kw)

    def test_intent_visible_before_acting(self):
        c1 = make_combat(content.STARTER_DECK, ['goblin', 'wolf'], seed=21)
        c1.start()
        texts = [e.intent for e in c1.enemies]
        for t in texts:
            self.assertIsNotNone(t)
            self.assertTrue(t.startswith('攻击') or t.startswith('格挡')
                            or '强化' in t or '易伤' in t or '毒' in t, t)
        c2 = make_combat(content.STARTER_DECK, ['goblin', 'wolf'], seed=21)
        c2.start()
        self.assertEqual([e.intent for e in c2.enemies], texts)
        c1.end_turn()
        c2.end_turn()
        self.assertEqual([e.intent for e in c1.enemies],
                         [e.intent for e in c2.enemies])

    def test_enemy_attack_hits_block_first(self):
        c = make_combat(content.STARTER_DECK, ['goblin'], seed=22)
        c.start()
        c.block = 3
        self.set_next_move(c, 0, name='砍', kind='attack', weight=1, damage=5)
        hp_before = c.hero.hp
        c.end_turn()
        self.assertEqual(c.hero.hp, hp_before - 2)
        self.assertEqual(c.block, 0)

    def test_multi_hit_attack(self):
        c = make_combat(content.STARTER_DECK, ['goblin'], seed=23)
        c.start()
        self.set_next_move(c, 0, name='咬', kind='attack', weight=1,
                           damage=3, hits=2)
        hp_before = c.hero.hp
        c.end_turn()
        self.assertEqual(c.hero.hp, hp_before - 6)

    def test_dead_enemy_removed_no_index_error(self):
        c = make_combat(content.STARTER_DECK, ['goblin', 'goblin'], seed=24)
        c.start()
        c.enemies[0].hp = 2
        seed_hand(c, ['whirl'])
        c.play_card(0, target=0)  # 4×3：第一段杀死 0 号，后两段转火 1 号
        self.assertEqual(c.enemies[0].hp, 0)
        self.assertEqual(c.enemies[1].hp, 14 - 8)
        seed_hand(c, ['strike'])
        c.energy = 3
        c.play_card(0)  # 补刀 1 号 → 胜利
        self.assertEqual(c.status, 'win')
        lines = c.play_card(0)
        self.assertTrue(any('结束' in l for l in lines))

    def test_win_and_lose_status(self):
        c = make_combat(content.STARTER_DECK, ['goblin'], seed=25)
        c.start()
        seed_hand(c, ['heavy', 'heavy'])
        c.energy = 4
        c.play_card(0)
        c.play_card(0)  # 12×2 >= 14
        self.assertEqual(c.status, 'win')
        c2 = make_combat(content.STARTER_DECK, ['goblin'], seed=26)
        c2.start()
        c2.hero.hp = 3
        self.set_next_move(c2, 0, name='砍', kind='attack', weight=1,
                           damage=5)
        c2.end_turn()
        self.assertEqual(c2.status, 'lose')
        self.assertEqual(c2.hero.hp, 0)

    def test_enemy_block_resets_at_own_turn(self):
        c = make_combat(content.STARTER_DECK, ['slime'], seed=61)
        c.start()
        self.set_next_move(c, 0, name='凝缩', kind='block', weight=1, block=6)
        c.end_turn()
        self.assertEqual(c.enemies[0].block, 6)
        self.set_next_move(c, 0, name='凝缩', kind='block', weight=1, block=6)
        c.end_turn()
        self.assertEqual(c.enemies[0].block, 6)  # 不跨回合累积

    def test_boss_intent_matches_actual_damage(self):
        drawn = False
        for seed in range(60):
            c = make_combat(content.STARTER_DECK, ['demon_lord'], seed=seed)
            c.start()
            c.enemies[0].hp = 60  # 触发二阶段
            c.end_turn()
            e = c.enemies[0]
            if e.pending_move.name != '灭世一击':
                continue
            drawn = True
            d = e.pending_move.damage + e.strength + e.dmg_add
            self.assertEqual(e.intent, '攻击 %d' % d)
            c.block = 0
            c.vulnerable = 0
            hp0 = c.hero.hp
            c.end_turn()
            self.assertEqual(hp0 - c.hero.hp, d)
            break
        self.assertTrue(drawn, '60 个种子没抽到灭世一击')

    def test_elite_cycle_moves_learnable(self):
        c = make_combat(content.STARTER_DECK, ['golem'], seed=27)
        c.start()
        self.assertTrue(c.enemies[0].intent.startswith('格挡 12'),
                        c.enemies[0].intent)
        c.end_turn()
        self.assertEqual(c.enemies[0].block, 12)
        self.assertIn('力量 +2', c.enemies[0].intent)
        c.end_turn()
        self.assertEqual(c.enemies[0].strength, 2)
        self.assertTrue(c.enemies[0].intent.startswith('攻击 11×2'),
                        c.enemies[0].intent)

    def test_boss_phase_switch(self):
        c = make_combat(content.STARTER_DECK, ['demon_lord'], seed=28)
        c.start()
        self.assertTrue(c.enemies[0].intent.startswith('攻击 12'))
        c.enemies[0].hp = 80  # 恰好一半 → 触发阶段 2
        c.end_turn()
        self.assertGreaterEqual(c.enemies[0].strength, 2)
        self.assertTrue(c.enemies[0].intent.startswith('攻击'),
                        c.enemies[0].intent)
        names = [m.name for m in content.ENEMIES['demon_lord'].phase2_moves]
        self.assertIn(c.enemies[0].pending_move.name, names)
        c.end_turn()
        self.assertGreaterEqual(c.enemies[0].strength, 4)

    def test_enemy_debuffs_on_hero(self):
        # 规格 6.2：易伤作用于"受到的攻击伤害 ×1.5"
        c = make_combat(content.STARTER_DECK, ['goblin'], seed=29)
        c.start()
        self.set_next_move(c, 0, name='嘲', kind='debuff', weight=1,
                           vulnerable=2)
        c.end_turn()
        self.assertEqual(c.vulnerable, 2)
        self.set_next_move(c, 0, name='砍', kind='attack', weight=1, damage=5)
        hp_before = c.hero.hp
        c.end_turn()
        self.assertEqual(c.hero.hp, hp_before - 7)  # int(5 × 1.5)
        self.assertEqual(c.vulnerable, 1)


class HookTests(unittest.TestCase):

    NOOP = dict(name='凝视', kind='block', weight=1)  # 敌人不伤害的占位招式

    def combat(self, enemies=('goblin',), weapon='rusty', armor=None,
               relics=(), hp=80, seed=31):
        hero = core.Hero(max_hp=80, hp=hp, gold=0,
                         deck=list(content.STARTER_DECK), weapon=weapon,
                         armor=armor, relics=list(relics), potions=[])
        c = core.Combat(hero, list(enemies), random.Random(seed), tier=1)
        c.start()
        return c

    def set_next_move(self, combat, enemy_idx, **kw):
        combat.enemies[enemy_idx].pending_move = content.Move(**kw)

    def test_rusty_sword_zero(self):
        c = self.combat()
        seed_hand(c, ['strike'])
        c.play_card(0)
        self.assertEqual(c.enemies[0].hp, 8)

    def test_axe_first_card_extra_cost(self):
        c = self.combat(weapon='axe')
        seed_hand(c, ['defend', 'defend'])
        c.play_card(0)
        self.assertEqual(c.energy, 1)
        c.play_card(0)
        self.assertEqual(c.energy, 0)
        seed_hand(c, ['strike'])
        c.energy = 3
        c.play_card(0)
        self.assertEqual(c.enemies[0].hp, 14 - 10)

    def test_flame_turn_start_self_damage(self):
        c = self.combat(weapon='flame')
        self.assertEqual(c.hero.hp, 78)
        self.set_next_move(c, 0, **self.NOOP)
        c.end_turn()
        self.assertEqual(c.hero.hp, 76)

    def test_twinblades_draw_and_penalty(self):
        c = self.combat(weapon='twinblades')
        self.assertEqual(len(c.hand), 6)
        seed_hand(c, ['strike'])
        c.play_card(0)
        self.assertEqual(c.enemies[0].hp, 14 - 5)

    def test_armor_start_block(self):
        c = self.combat(armor='leather')
        self.assertEqual(c.block, 5)
        c2 = self.combat(armor='plate')
        self.assertEqual(c2.block, 9)
        self.assertEqual(c2.energy, 2)

    def test_spiked_thorns(self):
        c = self.combat(armor='spiked')
        self.assertEqual(c.block, 3)
        self.set_next_move(c, 0, name='砍', kind='attack', weight=1,
                           damage=5)
        hp_hero = c.hero.hp
        c.end_turn()
        self.assertEqual(c.hero.hp, hp_hero - 2)
        self.assertEqual(c.enemies[0].hp, 14 - 3)

    def test_guardian_heal_start(self):
        c = self.combat(armor='guardian', hp=70)
        self.assertEqual(c.hero.hp, 72)
        self.assertEqual(c.block, 4)

    def test_relic_coffee_horn(self):
        c = self.combat(relics=['coffee'])
        self.assertEqual(c.energy, 4)
        c2 = self.combat(relics=['horn'])
        self.assertEqual(len(c2.hand), 7)

    def test_relic_tooth(self):
        self.assertEqual(self.combat(relics=['tooth'], hp=20).strength, 2)
        self.assertEqual(self.combat(relics=['tooth']).strength, 0)

    def test_relic_torch_and_whetstone(self):
        c = self.combat(relics=['torch'])
        seed_hand(c, ['strike'])
        c.play_card(0)
        self.assertEqual(c.enemies[0].hp, 14 - 7)
        c2 = self.combat(enemies=('knight',), relics=['whetstone'])
        seed_hand(c2, ['strike', 'strike'])
        c2.play_card(0)
        c2.play_card(0)
        self.assertEqual(c2.enemies[0].hp, 32 - 8 - 6)

    def test_relic_bandage(self):
        c = self.combat(relics=['bandage'])
        self.assertEqual(c.block, 4)

    def test_relic_ember_on_settle(self):
        c = self.combat(relics=['ember'], hp=70)
        seed_hand(c, ['heavy', 'heavy'])
        c.energy = 4
        c.play_card(0)
        c.play_card(0)
        self.assertEqual(c.status, 'win')
        core.settle_combat(c.hero, random.Random(99), layer=3)
        self.assertEqual(c.hero.hp, 74)

    def test_relic_ration_turn_end(self):
        c = self.combat(relics=['ration'], hp=70)
        self.set_next_move(c, 0, **self.NOOP)
        c.end_turn()
        self.assertEqual(c.hero.hp, 72)

    def test_relic_warpaint(self):
        c = self.combat(enemies=('goblin', 'wolf'), relics=['warpaint'])
        self.assertEqual([e.poison for e in c.enemies], [1, 1])
        self.set_next_move(c, 0, **self.NOOP)
        self.set_next_move(c, 1, **self.NOOP)
        c.end_turn()
        self.assertEqual(c.enemies[0].hp, 13)

    def test_relic_iron_heel_block_persist(self):
        c = self.combat(relics=['iron_heel'])
        seed_hand(c, ['defend'])
        c.play_card(0)
        self.set_next_move(c, 0, **self.NOOP)
        c.end_turn()
        self.assertEqual(c.block, 5)

    def test_relic_hourglass_energy(self):
        c = self.combat(relics=['hourglass'])
        self.set_next_move(c, 0, **self.NOOP)
        c.end_turn()
        self.set_next_move(c, 0, **self.NOOP)
        c.end_turn()
        self.assertEqual(c.turn, 3)
        self.assertEqual(c.energy, 4)

    def test_relic_idol_power_cost(self):
        c = self.combat(relics=['idol'])
        seed_hand(c, ['fury'])
        c.energy = 0
        lines = c.play_card(0)
        self.assertFalse(any('能量不足' in l for l in lines))
        self.assertIn('first_attack_bonus', c.powers)

    def test_relic_fang_necklace_thorns(self):
        c = self.combat(relics=['fang_necklace'])
        self.set_next_move(c, 0, name='砍', kind='attack', weight=1, damage=5)
        hp_hero = c.hero.hp
        c.end_turn()
        self.assertEqual(c.hero.hp, hp_hero - 5)
        self.assertEqual(c.enemies[0].hp, 14 - 2)

    def test_relic_vial_death_save_once(self):
        c = self.combat(relics=['vial'], hp=3)
        self.set_next_move(c, 0, name='砍', kind='attack', weight=1,
                           damage=10)
        c.end_turn()
        self.assertEqual(c.hero.hp, 24)
        self.assertNotIn('vial', c.hero.relics)
        self.assertEqual(c.status, 'playing')
        self.set_next_move(c, 0, name='砍', kind='attack', weight=1,
                           damage=30)
        c.end_turn()
        self.assertEqual(c.status, 'lose')

    def test_relic_purse_gold_mult(self):
        h1 = core.Hero(max_hp=80, hp=80, gold=0,
                       deck=list(content.STARTER_DECK), weapon='rusty',
                       relics=[], potions=[])
        h2 = core.Hero(max_hp=80, hp=80, gold=0,
                       deck=list(content.STARTER_DECK), weapon='rusty',
                       relics=['purse'], potions=[])
        r1 = core.settle_combat(h1, random.Random(51), layer=1)
        r2 = core.settle_combat(h2, random.Random(51), layer=1)
        self.assertEqual(r2['gold'], int(r1['gold'] * 1.25))
        self.assertEqual(h2.gold, r2['gold'])

    def test_relic_lucky_dice_four_choices(self):
        hero = core.Hero(max_hp=80, hp=80, gold=0,
                         deck=list(content.STARTER_DECK), weapon='rusty',
                         relics=[], potions=[])
        r = core.settle_combat(hero, random.Random(60), layer=2)
        self.assertEqual(len(r['card_choices']), 3)
        hero2 = core.Hero(max_hp=80, hp=80, gold=0,
                          deck=list(content.STARTER_DECK), weapon='rusty',
                          relics=['lucky_dice'], potions=[])
        r2 = core.settle_combat(hero2, random.Random(60), layer=2)
        self.assertEqual(len(r2['card_choices']), 4)
        self.assertEqual(len(set(r2['card_choices'])), 4)

    def test_settle_elite(self):
        hero = core.Hero(max_hp=80, hp=80, gold=0,
                         deck=list(content.STARTER_DECK), weapon='rusty',
                         relics=[], potions=[])
        r = core.settle_combat(hero, random.Random(70), layer=6,
                               kind='elite')
        self.assertEqual(len(r['relic_choices']), 3)
        for rid in r['relic_choices']:
            self.assertIn(content.RELICS[rid].rarity, ('uncommon', 'rare'))
        self.assertTrue(33 <= r['gold'] <= 50)
        self.assertEqual(r['card_choices'], [])

    def test_settle_normal_gold_range(self):
        hero = core.Hero(max_hp=80, hp=80, gold=0,
                         deck=list(content.STARTER_DECK), weapon='rusty',
                         relics=[], potions=[])
        drops = 0
        for s in range(200):
            r = core.settle_combat(hero, random.Random(s), layer=1)
            self.assertTrue(17 <= r['gold'] <= 24)
            if r['relic_drop']:
                drops += 1
        self.assertTrue(20 <= drops <= 65, drops)

    def test_relic_crown_boss_only(self):
        self.assertEqual(content.RELICS['crown'].rarity, 'boss')
        for pool in core.relic_pool('elite'):
            self.assertNotEqual(pool, 'crown')

    def test_all_relics_table_shape(self):
        self.assertEqual(len(content.RELICS), 19)
        content.validate_content()


class MapGenTests(unittest.TestCase):

    def test_invariants_over_1000_maps(self):
        for s in range(1000):
            m = core.generate_map(random.Random(s))
            nodes = list(m.nodes.values())
            kinds = [n.kind for n in nodes]
            self.assertTrue(15 <= len(kinds) <= 20, s)
            self.assertEqual(kinds.count('elite'), 2, s)
            self.assertEqual(kinds.count('boss'), 1, s)
            self.assertEqual(kinds.count('campfire') >= 3, True, s)
            self.assertGreaterEqual(kinds.count('shop'), 1, s)
            self.assertGreaterEqual(kinds.count('event'), 2, s)
            self.assertEqual(len(m.entry_ids), 2, s)
            for nid in m.entry_ids:
                self.assertEqual(m.nodes[nid].kind, 'combat', s)
                self.assertEqual(m.nodes[nid].layer, 1, s)
            for n in nodes:
                if n.kind == 'elite':
                    self.assertIn(n.layer, (6, 9), s)
                if n.layer in (1, 2):
                    self.assertNotEqual(n.kind, 'elite', s)
            for target_layer in (4, 7, 8, 10):
                self.assertTrue(
                    any(n.layer == target_layer and n.kind == 'campfire'
                        for n in nodes), (s, target_layer))
            self.assertEqual(m.nodes[m.boss_id].layer, 11, s)
            self.assertEqual(m.nodes[m.boss_id].kind, 'boss', s)

    def test_every_node_reachable_and_progresses(self):
        for s in range(200):
            m = core.generate_map(random.Random(s))
            for n in m.nodes.values():
                if n.kind == 'boss':
                    self.assertEqual(n.next, [], s)
                    continue
                self.assertTrue(len(n.next) >= 1, s)
                for nid in n.next:
                    self.assertEqual(m.nodes[nid].layer, n.layer + 1, s)
            # 入口可达所有节点
            seen = set(m.entry_ids)
            frontier = list(m.entry_ids)
            while frontier:
                cur = m.nodes[frontier.pop()]
                for nid in cur.next:
                    if nid not in seen:
                        seen.add(nid)
                        frontier.append(nid)
            self.assertEqual(seen, set(m.nodes), s)
            # 任意节点存在到 boss 的通路
            for n in m.nodes.values():
                stack, visited = [n.id], set()
                found = False
                while stack:
                    cid = stack.pop()
                    if cid == m.boss_id:
                        found = True
                        break
                    if cid in visited:
                        continue
                    visited.add(cid)
                    stack.extend(m.nodes[cid].next)
                self.assertTrue(found, (s, n.id))

    def test_same_seed_same_map(self):
        a = core.generate_map(random.Random(777))
        b = core.generate_map(random.Random(777))
        self.assertEqual(
            [(n.layer, n.kind, tuple(n.next)) for n in a.nodes.values()],
            [(n.layer, n.kind, tuple(n.next)) for n in b.nodes.values()])


if __name__ == '__main__':
    unittest.main()
