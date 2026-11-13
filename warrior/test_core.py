# -*- coding: utf-8 -*-
"""勇士冒险核心逻辑单元测试。"""
import unittest

import content


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


if __name__ == '__main__':
    unittest.main()
