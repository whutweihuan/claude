import unittest

from farm_core import (
    CROPS, INITIAL_COINS, INITIAL_PLOTS, LAND_PRICES, MAX_PLOTS, FarmState,
)


class InitialStateTests(unittest.TestCase):
    def test_initial_state(self):
        state = FarmState()
        self.assertEqual(state.coins, 60)
        self.assertEqual(state.unlocked_plots, 4)
        self.assertEqual(len(state.plots), 8)
        self.assertTrue(all(p is None for p in state.plots))
        self.assertEqual(state.warehouse, {})
        self.assertEqual(state.total_harvests, 0)
        self.assertEqual(state.total_income, 0)
        self.assertEqual(state.selected_crop, "xiaobaicai")

    def test_crop_table_matches_design(self):
        expected = {
            "xiaobaicai": ("小白菜", 1800, 10, 25),
            "huluobo": ("胡萝卜", 3600, 25, 65),
            "fanqie": ("番茄", 7200, 45, 135),
            "yumi": ("玉米", 14400, 80, 260),
            "nangua": ("南瓜", 28800, 140, 480),
        }
        for crop_id, values in expected.items():
            crop = CROPS[crop_id]
            self.assertEqual(
                (crop.name, crop.grow_seconds, crop.seed_price, crop.sell_price),
                values,
            )
        self.assertEqual(LAND_PRICES, (200, 500, 1000, 1800))
        self.assertEqual((MAX_PLOTS, INITIAL_PLOTS, INITIAL_COINS), (8, 4, 60))


class PlantAndGrowthTests(unittest.TestCase):
    def setUp(self):
        self.state = FarmState()
        self.t0 = 1_700_000_000.0

    def test_plant_deducts_coins_and_records_plot(self):
        self.state.plant(0, "xiaobaicai", self.t0)
        self.assertEqual(self.state.coins, 50)
        self.assertEqual(self.state.plots[0].crop_id, "xiaobaicai")
        self.assertEqual(self.state.plots[0].planted_at, self.t0)

    def test_plant_rejects_occupied_plot(self):
        self.state.plant(0, "xiaobaicai", self.t0)
        with self.assertRaisesRegex(ValueError, "已经有作物"):
            self.state.plant(0, "huluobo", self.t0)

    def test_plant_rejects_locked_plot(self):
        with self.assertRaisesRegex(ValueError, "还没开垦"):
            self.state.plant(4, "xiaobaicai", self.t0)

    def test_plant_rejects_unknown_crop(self):
        with self.assertRaisesRegex(ValueError, "未知作物"):
            self.state.plant(0, "unknown", self.t0)

    def test_plant_rejects_insufficient_coins(self):
        state = FarmState(coins=5)
        with self.assertRaisesRegex(ValueError, "金币不够"):
            state.plant(0, "xiaobaicai", self.t0)

    def test_progress_halfway(self):
        self.state.plant(0, "xiaobaicai", self.t0)
        self.assertAlmostEqual(self.state.progress(0, self.t0 + 900), 0.5)
        self.assertAlmostEqual(self.state.remaining_seconds(0, self.t0 + 900), 900)

    def test_progress_clamps_and_matures(self):
        self.state.plant(0, "xiaobaicai", self.t0)
        self.assertEqual(self.state.progress(0, self.t0 + 99999), 1.0)
        self.assertEqual(self.state.remaining_seconds(0, self.t0 + 99999), 0.0)
        self.assertTrue(self.state.is_mature(0, self.t0 + 1800))
        self.assertFalse(self.state.is_mature(0, self.t0 + 1799))

    def test_clock_rollback_counts_zero_elapsed(self):
        self.state.plant(0, "xiaobaicai", self.t0)
        self.assertEqual(self.state.progress(0, self.t0 - 3600), 0.0)
        self.assertAlmostEqual(self.state.remaining_seconds(0, self.t0 - 3600), 1800)


class WateringTests(unittest.TestCase):
    def setUp(self):
        self.state = FarmState()
        self.state.coins = 1000
        self.t0 = 1_700_000_000.0
        self.state.plant(0, "xiaobaicai", self.t0)   # 1800 秒

    def test_water_reduces_remaining_by_ten_percent_of_total(self):
        self.state.water(0, self.t0 + 60)
        self.assertAlmostEqual(
            self.state.remaining_seconds(0, self.t0 + 60), 1800 - 60 - 180
        )
        self.assertEqual(self.state.plots[0].water_count, 1)

    def test_water_has_ten_minute_cooldown(self):
        self.state.water(0, self.t0 + 60)
        with self.assertRaisesRegex(ValueError, "冷却"):
            self.state.water(0, self.t0 + 659)
        self.state.water(0, self.t0 + 660)  # 冷却刚好结束

    def test_water_limited_to_three_times(self):
        long_state = FarmState(coins=1000)
        long_state.plant(0, "nangua", self.t0)
        for offset in (0, 600, 1200):
            long_state.water(0, self.t0 + offset)
        with self.assertRaisesRegex(ValueError, "3 次"):
            long_state.water(0, self.t0 + 1800)

    def test_water_rejects_empty_plot(self):
        with self.assertRaisesRegex(ValueError, "没有作物"):
            self.state.water(3, self.t0)

    def test_water_rejects_mature_crop(self):
        with self.assertRaisesRegex(ValueError, "已经成熟"):
            self.state.water(0, self.t0 + 1800)

    def test_can_water_reflects_cooldown(self):
        self.assertTrue(self.state.can_water(0, self.t0))
        self.state.water(0, self.t0)
        self.assertFalse(self.state.can_water(0, self.t0 + 599))
        self.assertTrue(self.state.can_water(0, self.t0 + 600))


class HarvestTests(unittest.TestCase):
    def setUp(self):
        self.state = FarmState()
        self.state.coins = 1000
        self.t0 = 1_700_000_000.0

    def test_harvest_rejects_unripe_crop(self):
        self.state.plant(0, "xiaobaicai", self.t0)
        with self.assertRaisesRegex(ValueError, "还没成熟"):
            self.state.harvest(0, self.t0 + 10)

    def test_harvest_puts_crop_in_warehouse_and_clears_plot(self):
        self.state.plant(0, "xiaobaicai", self.t0)
        coins_before = self.state.coins
        crop_id = self.state.harvest(0, self.t0 + 1800)
        self.assertEqual(crop_id, "xiaobaicai")
        self.assertEqual(self.state.warehouse, {"xiaobaicai": 1})
        self.assertIsNone(self.state.plots[0])
        self.assertEqual(self.state.coins, coins_before)
        self.assertEqual(self.state.total_harvests, 1)
        self.assertEqual(self.state.total_income, 0)

    def test_harvest_all_counts_only_ripe_crops(self):
        self.state.plant(0, "xiaobaicai", self.t0)
        self.state.plant(1, "xiaobaicai", self.t0)
        self.state.plant(2, "huluobo", self.t0)
        harvested = self.state.harvest_all(self.t0 + 1800)
        self.assertEqual(harvested, 2)
        self.assertEqual(self.state.warehouse, {"xiaobaicai": 2})
        self.assertIsNotNone(self.state.plots[2])
        self.assertEqual(self.state.harvest_all(self.t0 + 1800), 0)


class SellingTests(unittest.TestCase):
    def setUp(self):
        self.state = FarmState()
        self.state.warehouse = {"xiaobaicai": 3, "fanqie": 1}

    def test_sell_returns_value_and_clears_that_crop(self):
        amount = self.state.sell("xiaobaicai")
        self.assertEqual(amount, 75)
        self.assertEqual(self.state.coins, 60 + 75)
        self.assertEqual(self.state.total_income, 75)
        self.assertEqual(self.state.warehouse, {"fanqie": 1})

    def test_sell_empty_or_unknown_returns_zero(self):
        self.assertEqual(self.state.sell("yumi"), 0)
        self.assertEqual(self.state.sell("unknown"), 0)
        self.assertEqual(self.state.coins, 60)

    def test_sell_all_sums_known_crops_and_clears(self):
        self.assertEqual(self.state.warehouse_value(), 75 + 135)
        amount = self.state.sell_all()
        self.assertEqual(amount, 210)
        self.assertEqual(self.state.coins, 270)
        self.assertEqual(self.state.total_income, 210)
        self.assertEqual(self.state.warehouse, {})
        self.assertEqual(self.state.sell_all(), 0)
