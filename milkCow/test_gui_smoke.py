# -*- coding: utf-8 -*-
"""cow_gui 冒烟与布局测试。构建窗口用 start_loops=False，不进 mainloop。"""

import tempfile
import time
import unittest
from pathlib import Path

import cow_gui
from cow_core import MILK_INTERVAL


class GuiSkeletonTests(unittest.TestCase):
    """GUI 测试用真实时钟：新开档的时间基准是 time.time()（规格 §10.1），
    固定 T0 会让存档锚点晚于测试时钟，满奶/怀孕判定失真。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.save_path = Path(self.tmp.name) / "save.json"
        self.app = cow_gui.CowApp(
            save_path=self.save_path,
            start_loops=False,
        )
        self.app.update_idletasks()

    def tearDown(self):
        self.app.destroy()
        self.tmp.cleanup()

    def test_window_builds_with_title_and_pasture(self):
        self.assertEqual(self.app.title(), "奶牛牧场")
        self.assertEqual((self.app.pasture.WIDTH, self.app.pasture.HEIGHT),
                         (760, 460))

    def test_initial_cow_drawn_with_name(self):
        self.assertTrue(any("花花" in t for t in self.app.pasture.texts()))

    def test_startup_conceives_initial_cow(self):
        self.assertTrue(self.app.state.cows[0].pregnant)
        self.app.refresh()
        self.assertIn("孕", self.app.cows_var.get())

    def test_title_shows_milking_count(self):
        self.app.state.cows[0].last_milked_at = time.time() - MILK_INTERVAL - 1
        self.app.refresh()
        self.assertEqual(self.app.title(), "奶牛牧场（1 可挤）")


if __name__ == "__main__":
    unittest.main()
