# -*- coding: utf-8 -*-
"""cow_core 核心逻辑单元测试：时间以显式参数注入，不真的等待。"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cow_core import (
    Cow, SaveUnreadableError, free_slot_left, load_state, new_game,
    save_state, stage_of, udder_ready,
)

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


class ShopTests(unittest.TestCase):
    def setUp(self):
        self.s = new_game(T0)

    def test_buy_calf(self):
        cow_id = self.s.buy_calf(T0)
        self.assertEqual(self.s.coins, 50)
        calf = self.s.find_cow(cow_id)
        self.assertEqual((calf.born_at, stage_of(calf, T0), calf.pregnant),
                         (T0, "calf", False))
        self.assertEqual(self.s.next_cow_id, 3)
        self.assertEqual(calf.name, "妞妞")  # 名字池第一个未占用

    def test_buy_calf_gate_full(self):
        self.s.capacity = 1
        with self.assertRaisesRegex(ValueError, "牧场满了"):
            self.s.buy_calf(T0)

    def test_buy_calf_reservation_counts_pregnant(self):
        self.s.capacity = 2
        self.s.cows[0].pregnant = True
        with self.assertRaisesRegex(ValueError, "牧场满了"):
            self.s.buy_calf(T0)

    def test_buy_calf_insufficient_coins(self):
        self.s.coins = 10
        with self.assertRaisesRegex(ValueError, "金币不够"):
            self.s.buy_calf(T0)

    def test_sell_price_by_stage(self):
        self.s.cows.append(make_cow(id=2, born_at=T0))            # calf
        self.s.cows.append(make_cow(id=3, born_at=T0 - 50 * 60))  # young
        self.assertEqual(self.s.sell_cow(2, T0), 80)
        self.assertEqual(self.s.sell_cow(3, T0), 160)
        self.assertEqual(self.s.sell_cow(1, T0), 350)
        self.assertEqual(self.s.coins, 790)
        self.assertEqual(self.s.total_income, 590)
        self.assertEqual(len(self.s.cows), 0)

    def test_sell_unknown_cow(self):
        with self.assertRaisesRegex(ValueError, "没有这头牛"):
            self.s.sell_cow(42, T0)

    def test_sell_pregnant_cow_removes_fetus(self):
        self.s.cows[0].pregnant = True
        self.s.cows[0].due_at = T0 + 3600
        self.s.sell_cow(1, T0)
        self.assertEqual(len(self.s.cows), 0)
        self.s.catch_up(T0 + 7200)
        self.assertEqual(len(self.s.cows), 0)  # 不会凭空生产

    def test_sell_pregnant_frees_slot_for_queue(self):
        self.s.capacity = 2
        self.s.cows.append(make_cow(id=2, pregnant=True, due_at=T0 + 3600))
        self.assertFalse(free_slot_left(self.s))  # 1 牛 + 1 孕 = 2 ≥ 容量
        self.s.sell_cow(2, T0)
        # 孕妇被卖 → 预留随她消失；位置被唯一可孕的排队牛（花花）受孕补位
        self.assertTrue(self.s.find_cow(1).pregnant)
        self.assertFalse(free_slot_left(self.s))  # 怀上后重新占住预留

    def test_buy_feed(self):
        self.assertEqual(self.s.buy_feed(), 1)  # 返回背包份数
        self.assertEqual((self.s.coins, self.s.feed_count), (175, 1))
        self.s.coins = 10
        with self.assertRaisesRegex(ValueError, "金币不够"):
            self.s.buy_feed()

    def test_machine_prices_sequence(self):
        self.s.coins = 100000
        self.s.buy_machine()
        self.assertEqual((self.s.coins, self.s.machines), (99700, [None]))
        self.s.buy_machine()
        self.assertEqual(self.s.coins, 99000)
        self.s.buy_machine()
        self.assertEqual(self.s.coins, 97500)
        with self.assertRaisesRegex(ValueError, "加工器已达上限"):
            self.s.buy_machine()

    def test_expand_prices_sequence(self):
        self.s.coins = 100000
        for _ in range(8):
            self.s.expand_capacity()
        self.assertEqual(self.s.capacity, 12)
        self.assertEqual(self.s.coins, 100000 - 13000)  # 200+400+700+1000+1500+2200+3000+4000
        with self.assertRaisesRegex(ValueError, "已扩建到上限"):
            self.s.expand_capacity()

    def test_expand_insufficient_coins(self):
        self.s.coins = 10
        with self.assertRaisesRegex(ValueError, "金币不够"):
            self.s.expand_capacity()


class CheeseTests(unittest.TestCase):
    def setUp(self):
        self.s = new_game(T0)
        self.s.coins = 100000
        self.s.buy_machine()
        self.s.warehouse["milk"] = 5

    def test_process_consumes_and_busy(self):
        self.s.process(0, T0)
        self.assertEqual((self.s.stock("milk"), self.s.machines[0]), (2, T0))
        with self.assertRaisesRegex(ValueError, "加工器正忙"):
            self.s.process(0, T0 + 60)

    def test_cheese_settles_on_catch_up(self):
        self.s.process(0, T0)
        self.s.catch_up(T0 + 1199)
        self.assertEqual(self.s.stock("cheese"), 0)
        self.assertEqual(self.s.machines[0], T0)
        self.s.catch_up(T0 + 1200)
        self.assertEqual(self.s.stock("cheese"), 1)
        self.assertIsNone(self.s.machines[0])

    def test_cheese_sale_value(self):
        self.s.warehouse["cheese"] = 2
        self.assertEqual(self.s.sell_stock("cheese"), 150)
        self.assertEqual(self.s.coins, 100000 - 300 + 150)

    def test_process_all_fills_machines(self):
        self.s.buy_machine()
        self.s.warehouse["milk"] = 7
        self.assertEqual(self.s.process_all(T0), 2)
        self.assertEqual(self.s.stock("milk"), 1)

    def test_process_requires_milk(self):
        self.s.warehouse["milk"] = 2
        with self.assertRaisesRegex(ValueError, "牛奶不够"):
            self.s.process(0, T0)
        self.assertIsNone(self.s.machines[0])

    def test_process_unknown_machine(self):
        with self.assertRaisesRegex(ValueError, "没有这台加工器"):
            self.s.process(5, T0)


def snapshot(s):
    """核心世界状态的完整可比快照（用于一致性/幂等断言）。"""
    return {
        "coins": s.coins,
        "capacity": s.capacity,
        "cows": sorted(
            (c.id, c.name, c.born_at, c.fed_count, c.last_fed_at,
             c.last_milked_at, c.pregnant, c.due_at, c.recovery_until)
            for c in s.cows
        ),
        "machines": list(s.machines),
        "warehouse": dict(s.warehouse),
        "feed_count": s.feed_count,
        "total_income": s.total_income,
        "total_births": s.total_births,
        "next_cow_id": s.next_cow_id,
        "settled_until": s.settled_until,
    }


class BreedingTests(unittest.TestCase):
    def test_initial_cow_pregnant_at_first_settle(self):
        s = new_game(T0)
        s.catch_up(T0)
        self.assertTrue(s.cows[0].pregnant)
        self.assertEqual(s.cows[0].due_at, T0 + 3600)

    def test_first_settle_later_still_anchors_conception_at_start(self):
        s = new_game(T0)
        s.catch_up(T0 + 7200)  # 首次结算迟到 2 小时
        # 初始牛仍在 T0 受孕（事件时间锚定）：T0+3600 已生产，T0+5400 休养结束再孕
        self.assertEqual(s.total_births, 1)
        self.assertEqual(len(s.cows), 2)
        self.assertTrue(s.cows[0].pregnant)
        self.assertEqual(s.cows[0].due_at, T0 + 5400 + 3600)

    def test_offline_jump_equals_online_stepping(self):
        a = new_game(T0)
        b = new_game(T0)
        for k in range(1, 25):  # 在线：每 30 分钟结算一步，共 12 小时
            a.catch_up(T0 + k * 1800.0)
        b.catch_up(T0 + 12 * 3600.0)  # 离线：一跳 12 小时
        self.assertEqual(snapshot(a), snapshot(b))
        # 预期轨迹：T0 受孕 → +1h 生妞妞 → +1.5h 母再孕 → +2.5h 生大壮 →
        #          +3h 母再孕 → +4h 生团团满 4 头 → 全员排队等空位
        self.assertEqual([c.name for c in b.cows], ["花花", "妞妞", "大壮", "团团"])
        self.assertEqual(b.total_births, 3)
        self.assertFalse(any(c.pregnant for c in b.cows))

    def test_thirty_day_offline_matches_hourly_stepping(self):
        a = new_game(T0)
        b = new_game(T0)
        for k in range(1, 721):  # 在线：每小时一步，共 30 天
            a.catch_up(T0 + k * 3600.0)
        b.catch_up(T0 + 30 * 86400.0)  # 离线：一跳 30 天
        self.assertEqual(snapshot(a), snapshot(b))
        self.assertLessEqual(len(b.cows), b.capacity)  # 任何时刻不超容

    def test_idempotent_catch_up(self):
        s = new_game(T0)
        s.catch_up(T0 + 50 * 3600.0)
        snap = snapshot(s)
        s.catch_up(T0 + 50 * 3600.0)
        self.assertEqual(snap, snapshot(s))

    def test_reservation_gate_blocks_births(self):
        s = new_game(T0)
        s.capacity = 1
        s.catch_up(T0 + 10 * 3600.0)
        self.assertEqual(len(s.cows), 1)
        self.assertFalse(s.cows[0].pregnant)

    def test_pending_queue_conceives_in_order(self):
        s = new_game(T0)
        s.catch_up(T0)  # 花花受孕，due T0+3600
        s.cows.append(make_cow(id=2, born_at=T0 - 20000))  # ready_at 更早
        s.cows.append(make_cow(id=3, born_at=T0 - 15000))  # ready_at 更晚
        s.capacity = 4  # 3 牛 + 1 孕 = 4，无空位，两头排队
        self.assertFalse(s.find_cow(2).pregnant)
        s.sell_cow(3, T0)  # 腾位 → 排队更早的 2 号受孕
        self.assertTrue(s.find_cow(2).pregnant)
        self.assertEqual(s.find_cow(2).due_at, T0 + 3600)

    def test_two_pregnant_due_same_moment(self):
        s = new_game(T0)
        s.cows[0].pregnant = True
        s.cows[0].due_at = T0 + 3600
        s.cows.append(make_cow(id=2, born_at=T0 - 20000,
                               pregnant=True, due_at=T0 + 3600))
        s.capacity = 3
        s.catch_up(T0 + 3600)
        self.assertEqual(len(s.cows), 4)  # 两头都产（强制构造可超容，但不崩溃）
        self.assertEqual(s.total_births, 2)
        self.assertFalse(any(c.pregnant for c in s.cows))
        self.assertEqual([c.name for c in s.cows[2:]], ["妞妞", "大壮"])
        s.catch_up(T0 + 4 * 3600)  # 超容 → 不再受孕
        self.assertEqual(len(s.cows), 4)

    def test_time_rollback_no_crash(self):
        s = new_game(T0)
        s.catch_up(T0 + 7200)
        snap = snapshot(s)
        s.catch_up(T0 + 600)  # 时间回拨
        self.assertEqual(snapshot(s), snap)  # 无新事件、不重复生产、不崩溃
        s.catch_up(T0 + 7200)
        self.assertEqual(snapshot(s), snap)


class SaveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "save.json"

    def tearDown(self):
        self.tmp.cleanup()

    def _rich_state(self):
        s = new_game(T0)
        s.coins = 5000
        s.catch_up(T0)                      # 花花受孕 due T0+3600
        s.buy_calf(T0)                      # 妞妞（id2）
        s.buy_feed()
        s.buy_feed()
        s.buy_machine()
        s.buy_machine()
        s.warehouse["milk"] = 10
        s.warehouse["cheese"] = 1
        s.process(0, T0)
        s.process(1, T0)
        s.expand_capacity()
        s.cows[1].fed_count = 1
        s.total_income = 777
        return s

    def _write_raw(self, data):
        self.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_roundtrip_preserves_world(self):
        s = self._rich_state()
        save_state(s, self.path)
        loaded, msg = load_state(self.path)
        self.assertIsNone(msg)
        self.assertEqual(snapshot(loaded), snapshot(s))

    def test_missing_file_starts_new_game(self):
        s, msg = load_state(self.path.parent / "nope.json")
        self.assertIsNone(msg)
        self.assertEqual((s.coins, s.capacity, len(s.cows)), (200, 4, 1))

    def test_corrupt_json_is_backed_up(self):
        self.path.write_text("{ 这不是 JSON", encoding="utf-8")
        s, msg = load_state(self.path)
        self.assertIn("存档损坏", msg)
        self.assertFalse(self.path.exists())
        self.assertEqual(len(list(self.path.parent.glob("save.corrupt-*.json"))), 1)

    def test_bad_field_is_corrupt(self):
        base = self._rich_state().to_dict()
        dup = json.loads(json.dumps(base))
        dup["cows"][1]["id"] = dup["cows"][0]["id"]
        variants = [
            {**base, "coins": "abc"},
            {**base, "capacity": 99},
            {**base, "warehouse": {"milk": -2}},
            {**base, "machines": [None, None, None, None]},
            dup,
            "not-a-dict",
        ]
        for bad in variants:
            with self.subTest(bad=str(bad)[:24]):
                self._write_raw(bad)
                s, msg = load_state(self.path)
                self.assertIn("存档损坏", msg)
                self.assertEqual((s.coins, s.capacity, len(s.cows)), (200, 4, 1))

    def test_unknown_keys_ignored(self):
        data = self._rich_state().to_dict()
        data["future_field"] = {"x": 1}
        data["warehouse"]["yogurt"] = 5
        self._write_raw(data)
        loaded, msg = load_state(self.path)
        self.assertIsNone(msg)
        self.assertEqual(loaded.stock("yogurt"), 0)
        self.assertEqual(snapshot(loaded), snapshot(self._rich_state()))

    def test_permission_error_raises_unreadable(self):
        save_state(self._rich_state(), self.path)
        original = self.path.read_text(encoding="utf-8")
        with mock.patch.object(Path, "open", side_effect=PermissionError("被占用")):
            with self.assertRaises(SaveUnreadableError):
                load_state(self.path)
        self.assertEqual(self.path.read_text(encoding="utf-8"), original)
        self.assertFalse(list(self.path.parent.glob("save.corrupt-*.json")))

    def test_offline_growth_survives_save(self):
        s = self._rich_state()
        save_state(s, self.path)
        loaded, _ = load_state(self.path)
        loaded.catch_up(T0 + 2 * 3600)  # 预产期 T0+3600 → 生小牛
        self.assertEqual(loaded.total_births, s.total_births + 1)
        self.assertEqual(len(loaded.cows), len(s.cows) + 1)


if __name__ == "__main__":
    unittest.main()
