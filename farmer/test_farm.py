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
