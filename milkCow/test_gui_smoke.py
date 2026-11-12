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


class GuiInteractionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.save_path = Path(self.tmp.name) / "save.json"
        self.app = cow_gui.CowApp(save_path=self.save_path, start_loops=False)
        self.app.update_idletasks()

    def tearDown(self):
        self.app.destroy()
        self.tmp.cleanup()

    def _make_cow_full(self, cow=None):
        import time as _time
        cow = cow or self.app.state.cows[0]
        cow.last_milked_at = _time.time() - MILK_INTERVAL - 1
        return cow

    def test_click_full_cow_milks(self):
        self._make_cow_full()
        coins = self.app.state.coins
        self.app._on_cow_click(1)
        self.assertEqual(self.app.state.stock("milk"), 1)
        self.assertEqual(self.app.state.coins, coins)
        self.assertTrue(any(t.startswith("+1 牛奶") for t in self.app.pasture.texts()))

    def test_click_not_full_cow_selects(self):
        self.app._on_cow_click(1)
        self.assertEqual(self.app.selected_id, 1)
        self.assertEqual(self.app.state.stock("milk"), 0)
        self.assertIn("花花", self.app.action_var.get())

    def test_milk_all_button(self):
        import time as _time
        from cow_core import Cow
        s = self.app.state
        for name in ("妞妞", "大壮"):
            s.cows.append(Cow(id=s.next_cow_id, name=name,
                              born_at=_time.time() - 10800,
                              last_milked_at=_time.time() - MILK_INTERVAL - 1))
            s.next_cow_id += 1
        self._make_cow_full()
        self.app.refresh()
        self.assertEqual(self.app.title(), "奶牛牧场（3 可挤）")
        self.app._on_milk_all_click()
        self.assertEqual(s.stock("milk"), 3)
        self.assertEqual(self.app.title(), "奶牛牧场")

    def test_buy_calf_disabled_when_full(self):
        self.app.state.capacity = 1
        self.app.refresh()
        self.assertEqual(self.app.buy_calf_button.cget("text"), "牧场满了")
        self.assertEqual(str(self.app.buy_calf_button.cget("state")), "disabled")
        self.app._on_buy_calf_click()
        self.assertIn("牧场满了", self.app.status_var.get())

    def test_sell_cow_click_adds_coins(self):
        self.app.selected_id = 1
        coins = self.app.state.coins
        self.app._on_sell_cow_click()
        self.assertEqual(self.app.state.coins, coins + 350)
        self.assertEqual(len(self.app.state.cows), 0)
        self.assertIsNone(self.app.selected_id)

    def test_process_click_starts_machine(self):
        s = self.app.state
        s.coins = 5000
        s.buy_machine()
        s.warehouse["milk"] = 3
        self.app._on_process_click(0)
        self.assertIsNotNone(s.machines[0])
        self.assertEqual(s.stock("milk"), 0)

    def test_sell_all_totals_in_button_text(self):
        self.app.state.warehouse.update({"milk": 2, "cheese": 1})
        self.app.refresh()
        self.assertIn("全部卖出（105）", self.app.sell_all_button.cget("text"))
        coins = self.app.state.coins
        self.app._on_sell_all_click()
        self.assertEqual(self.app.state.coins, coins + 105)
        self.assertEqual(self.app.state.stock("milk"), 0)

    def test_error_goes_to_status_not_dialog(self):
        self.app.state.coins = 0
        self.app.refresh()
        self.app._on_buy_machine_click()
        self.assertIn("金币不够", self.app.status_var.get())
        self.assertEqual(len(self.app.state.machines), 0)

    def test_operations_persist_to_save(self):
        self._make_cow_full()
        self.app._on_cow_click(1)
        self.assertTrue(self.save_path.exists())
        self.assertIn("milk", self.save_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
