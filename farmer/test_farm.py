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
