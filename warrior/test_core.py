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


if __name__ == '__main__':
    unittest.main()
