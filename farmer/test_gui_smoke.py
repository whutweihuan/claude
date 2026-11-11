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
