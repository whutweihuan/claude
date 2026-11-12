# -*- coding: utf-8 -*-
"""cow_core 核心逻辑单元测试：时间以显式参数注入，不真的等待。"""

import unittest

from cow_core import Cow, free_slot_left, new_game, stage_of, udder_ready

T0 = 1_700_000_000.0


def make_cow(**overrides):
    """默认一头刚成年、未孕、奶空的牛；按 overrides 覆盖字段。"""
    fields = dict(
        id=99,
        name="测试牛",
        born_at=T0 - 10800,
        fed_count=0,
        last_fed_at=0.0,
        last_milked_at=T0,
        pregnant=False,
        due_at=0.0,
        recovery_until=0.0,
    )
    fields.update(overrides)
    return Cow(**fields)


class StageTests(unittest.TestCase):
    def test_stage_boundaries(self):
        cow = make_cow(born_at=T0)
        self.assertEqual(stage_of(cow, T0 + 45 * 60 - 1), "calf")
        self.assertEqual(stage_of(cow, T0 + 45 * 60), "young")
        self.assertEqual(stage_of(cow, T0 + 135 * 60 - 1), "young")
        self.assertEqual(stage_of(cow, T0 + 135 * 60), "adult")

    def test_feed_credit_advances_stage(self):
        cow = make_cow(born_at=T0, fed_count=3)  # 省 45 分钟
        self.assertEqual(stage_of(cow, T0 + 90 * 60), "adult")

    def test_initial_game_is_one_adult_with_empty_udder(self):
        s = new_game(T0)
        self.assertEqual((s.coins, s.capacity, len(s.cows)), (200, 4, 1))
        self.assertEqual(stage_of(s.cows[0], T0), "adult")
        self.assertFalse(udder_ready(s.cows[0], T0))
        self.assertTrue(udder_ready(s.cows[0], T0 + 1200))  # 20 分钟满奶
        # 刚出生的牛仔：134 分钟时仍是青年牛，未成年永不满奶
        self.assertFalse(udder_ready(make_cow(born_at=T0), T0 + 134 * 60))

    def test_free_slot_counts_pregnant_cows(self):
        s = new_game(T0)
        s.capacity = 2
        s.cows.append(make_cow(id=2))
        s.cows[1].pregnant = True
        self.assertFalse(free_slot_left(s))  # 牛数 2 + 孕妇 1 = 3 > 容量 2


if __name__ == "__main__":
    unittest.main()
