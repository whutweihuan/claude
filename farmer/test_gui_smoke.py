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
