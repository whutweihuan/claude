# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path

import farm_gui
from farm_core import CROPS


class GuiSkeletonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.save_path = Path(self.tmp.name) / "save.json"
        self.now = 1_700_000_000.0
        self.app = farm_gui.FarmApp(
            save_path=self.save_path,
            start_loops=False,
            clock=lambda: self.now,
        )
        self.app.update_idletasks()

    def tearDown(self):
        self.app.destroy()
        self.tmp.cleanup()

    def test_window_builds_eight_plot_cards(self):
        self.assertEqual(len(self.app.plot_cards), 8)
        self.assertEqual(self.app.title(), "小菜园")

    def test_unlocked_empty_plot_shows_empty_text(self):
        self.assertIn("空地", self.app.plot_cards[0].texts())

    def test_locked_plot_shows_locked_text(self):
        self.assertIn("未开垦", self.app.plot_cards[4].texts())

    def test_planted_plot_shows_crop_name_and_countdown(self):
        self.app.state.plant(0, "xiaobaicai", self.now)
        self.app.refresh()
        texts = self.app.plot_cards[0].texts()
        self.assertTrue(any("小白菜" in t for t in texts))
        self.assertTrue(any("还需" in t for t in texts))


class GuiInteractionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.save_path = Path(self.tmp.name) / "save.json"
        self.now = 1_700_000_000.0
        self.app = farm_gui.FarmApp(
            save_path=self.save_path,
            start_loops=False,
            clock=lambda: self.now,
        )
        self.app.update_idletasks()

    def tearDown(self):
        self.app.destroy()
        self.tmp.cleanup()

    def test_select_seed_updates_state_and_highlight(self):
        self.app._on_seed_click("huluobo")
        self.assertEqual(self.app.state.selected_crop, "huluobo")
        self.assertEqual(str(self.app.seed_buttons["huluobo"].cget("relief")), "sunken")

    def test_plot_click_plants_selected_seed(self):
        self.app._on_seed_click("huluobo")
        self.app._on_plot_click(0)
        self.assertEqual(self.app.state.plots[0].crop_id, "huluobo")
        self.assertEqual(self.app.state.coins, 35)
        self.assertIn("种下了胡萝卜", self.app.status_var.get())

    def test_plot_click_on_locked_plot_shows_message(self):
        self.app._on_plot_click(6)
        self.assertIn("还没开垦", self.app.status_var.get())
        self.assertIsNone(self.app.state.plots[6])

    def test_water_click_increases_water_count(self):
        self.app._on_plot_click(0)
        coins_after_plant = self.app.state.coins
        self.app._on_water_click(0)
        self.assertEqual(self.app.state.plots[0].water_count, 1)
        self.assertEqual(self.app.state.coins, coins_after_plant)
        self.assertIn("浇水", self.app.status_var.get())

    def test_water_click_does_not_plant_or_harvest(self):
        self.app._on_plot_click(0)
        plot_before = self.app.state.plots[0]
        coins_before = self.app.state.coins
        self.app._on_water_click(0)
        self.assertIs(self.app.state.plots[0], plot_before)
        self.assertEqual(self.app.state.coins, coins_before)
        self.assertEqual(self.app.state.warehouse, {})


class GuiEconomyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.save_path = Path(self.tmp.name) / "save.json"
        self.now = 1_700_000_000.0
        self.app = farm_gui.FarmApp(
            save_path=self.save_path,
            start_loops=False,
            clock=lambda: self.now,
        )
        self.app.update_idletasks()

    def tearDown(self):
        self.app.destroy()
        self.tmp.cleanup()

    def _plant_ripe(self, index=0, crop_id="xiaobaicai"):
        planted_at = self.now - CROPS[crop_id].grow_seconds - 1
        self.app.state.plant(index, crop_id, planted_at)
        self.app.refresh()

    def test_harvest_click_fills_warehouse(self):
        self._plant_ripe()
        coins_before = self.app.state.coins
        self.app._on_plot_click(0)
        self.assertEqual(self.app.state.warehouse, {"xiaobaicai": 1})
        self.assertEqual(self.app.state.coins, coins_before)
        self.assertIn("×1", self.app.warehouse_vars["xiaobaicai"].get())

    def test_sell_click_adds_coins_and_clears_row(self):
        self._plant_ripe()
        self.app._on_plot_click(0)
        self.app._on_sell_click("xiaobaicai")
        self.assertEqual(self.app.state.coins, 50 + 25)
        self.assertEqual(self.app.state.warehouse, {})
        self.assertIn("卖出小白菜", self.app.status_var.get())
        self.assertTrue(self.app.sell_buttons["xiaobaicai"].cget("state") == "disabled")

    def test_harvest_all_then_sell_all(self):
        self._plant_ripe(0, "xiaobaicai")
        self._plant_ripe(1, "fanqie")
        self.app._on_harvest_all_click()
        self.assertEqual(self.app.state.warehouse, {"xiaobaicai": 1, "fanqie": 1})
        self.assertIn("2", self.app.status_var.get())
        total_text = self.app.sell_all_button.cget("text")
        self.assertIn("160", total_text)
        self.app._on_sell_all_click()
        self.assertEqual(self.app.state.coins, 5 + 25 + 135)
        self.assertEqual(self.app.state.warehouse, {})

    def test_buy_land_click_unlocks_plot(self):
        self.app.state.coins = 300
        self.app.refresh()
        self.app._on_buy_land_click()
        self.assertEqual(self.app.state.unlocked_plots, 5)
        self.assertEqual(self.app.state.coins, 100)
        self.assertIn("第 5 块", self.app.status_var.get())
        self.assertIn("开垦 500", self.app.land_button.cget("text"))

    def test_title_shows_ripe_count(self):
        self._plant_ripe()
        self.app.refresh()
        self.assertEqual(self.app.title(), "小菜园（1 可收）")
        self.app._on_plot_click(0)
        self.app.refresh()
        self.assertEqual(self.app.title(), "小菜园")
