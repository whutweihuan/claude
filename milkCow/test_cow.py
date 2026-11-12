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


class MilkTests(unittest.TestCase):
    def setUp(self):
        self.s = new_game(T0)

    def test_milk_requires_full_udder(self):
        with self.assertRaisesRegex(ValueError, "这头牛还没蓄满奶"):
            self.s.milk(1, T0 + 1199)
        self.s.milk(1, T0 + 1200)
        self.assertEqual(self.s.warehouse["milk"], 1)

    def test_milk_resets_timer(self):
        self.s.milk(1, T0 + 1200)
        with self.assertRaisesRegex(ValueError, "这头牛还没蓄满奶"):
            self.s.milk(1, T0 + 2399)
        self.s.milk(1, T0 + 2400)
        self.assertEqual(self.s.stock("milk"), 2)

    def test_milk_pregnant_cow_allowed(self):
        self.s.cows[0].pregnant = True
        coins = self.s.coins
        self.s.milk(1, T0 + 1200)
        self.assertEqual(self.s.stock("milk"), 1)
        self.assertEqual(self.s.coins, coins)

    def test_milk_all_counts_only_ready(self):
        self.s.cows.append(make_cow(id=2, born_at=T0 - 10800, last_milked_at=T0))
        self.s.cows.append(make_cow(id=3, born_at=T0 - 10800, last_milked_at=T0 + 600))
        self.assertEqual(self.s.milk_all(T0 + 1200), 2)
        self.assertEqual(self.s.stock("milk"), 2)

    def test_milk_all_zero_is_legal(self):
        self.assertEqual(self.s.milk_all(T0), 0)
        self.assertEqual(self.s.stock("milk"), 0)

    def test_milk_unknown_id_raises(self):
        with self.assertRaisesRegex(ValueError, "没有这头牛"):
            self.s.milk(42, T0 + 99999)

    def test_sell_milk_adds_coins(self):
        self.s.warehouse["milk"] = 3
        got = self.s.sell_stock("milk")
        self.assertEqual((got, self.s.coins, self.s.total_income, self.s.stock("milk")),
                         (45, 245, 45, 0))

    def test_sell_all_stock_totals(self):
        self.s.warehouse.update({"milk": 2, "cheese": 1})
        self.assertEqual(self.s.stock_value(), 105)
        self.assertEqual(self.s.sell_all_stock(), 105)
        self.assertEqual(self.s.coins, 305)
        self.assertEqual(self.s.stock("milk"), 0)
        self.assertEqual(self.s.stock("cheese"), 0)
        self.assertEqual(self.s.sell_all_stock(), 0)  # 空仓返回 0 不报错


class FeedTests(unittest.TestCase):
    def setUp(self):
        self.s = new_game(T0)
        self.s.cows.append(make_cow(id=2, born_at=T0))  # 刚出生的牛仔
        self.s.feed_count = 1

    def test_feed_advances_adulthood(self):
        self.s.feed(2, T0)
        self.assertEqual(self.s.feed_count, 0)
        self.assertEqual(self.s.cows[1].fed_count, 1)
        self.assertEqual(stage_of(self.s.cows[1], T0 + 120 * 60), "adult")  # 135-15=120
        self.assertEqual(stage_of(self.s.cows[1], T0 + 119 * 60), "young")

    def test_feed_three_max_and_cooldown(self):
        self.s.feed_count = 5
        self.s.feed(2, T0)
        with self.assertRaisesRegex(ValueError, "投喂间隔不足 10 分钟"):
            self.s.feed(2, T0 + 599)
        self.s.feed(2, T0 + 600)
        self.s.feed(2, T0 + 1200)
        self.assertEqual(self.s.cows[1].fed_count, 3)
        with self.assertRaisesRegex(ValueError, "最多喂 3 次"):
            self.s.feed(2, T0 + 1800)

    def test_feed_rejects_adult(self):
        with self.assertRaisesRegex(ValueError, "已经成年"):
            self.s.feed(1, T0)  # 花花是成年牛

    def test_feed_rejects_empty_bag(self):
        self.s.feed_count = 0
        with self.assertRaisesRegex(ValueError, "没有高级饲料"):
            self.s.feed(2, T0)

    def test_feed_unknown_cow(self):
        with self.assertRaisesRegex(ValueError, "没有这头牛"):
            self.s.feed(42, T0)

    def test_feed_does_not_touch_coins(self):
        coins = self.s.coins
        self.s.feed(2, T0)
        self.assertEqual(self.s.coins, coins)


if __name__ == "__main__":
    unittest.main()
