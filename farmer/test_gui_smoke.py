# -*- coding: utf-8 -*-
import subprocess
import sys
import tempfile
import tkinter as tk
import tkinter.font as tkfont
import unittest
from pathlib import Path
from unittest import mock

import farm_gui
from farm_core import CROPS, FarmState, save_state


def _label_widgets(widget):
    result = []
    for child in widget.winfo_children():
        if child.winfo_class() == "Label":
            result.append(child)
        result.extend(_label_widgets(child))
    return result


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

    def test_harvest_shows_floating_text(self):
        self._plant_ripe()
        self.app._on_plot_click(0)
        texts = self.app.plot_cards[0].texts()
        self.assertTrue(any(t.startswith("+1 小白菜") for t in texts))

    def test_harvest_all_shows_floating_text_for_each_ripe_plot(self):
        self._plant_ripe(0, "xiaobaicai")
        self._plant_ripe(1, "fanqie")
        self.app._on_harvest_all_click()
        self.assertTrue(
            any(t.startswith("+1 小白菜") for t in self.app.plot_cards[0].texts())
        )
        self.assertTrue(
            any(t.startswith("+1 番茄") for t in self.app.plot_cards[1].texts())
        )

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


class GuiPersistenceTests(unittest.TestCase):
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
        try:
            self.app.destroy()
        except tk.TclError:
            pass
        self.tmp.cleanup()

    def test_close_saves_state(self):
        self.app._on_plot_click(0)
        self.app._on_close()
        self.assertTrue(self.save_path.exists())
        data = self.save_path.read_text(encoding="utf-8")
        self.assertIn("xiaobaicai", data)

    def test_save_failure_does_not_crash(self):
        with mock.patch.object(farm_gui, "save_state", side_effect=OSError("磁盘忙")):
            self.app._save()
        self.assertIn("保存失败", self.app.status_var.get())

    def test_app_starts_from_existing_save(self):
        self.app.state.coins = 777
        self.app._save()
        app2 = farm_gui.FarmApp(
            save_path=self.save_path,
            start_loops=False,
            clock=lambda: self.now,
        )
        try:
            self.assertEqual(app2.state.coins, 777)
        finally:
            app2.destroy()

    def test_unreadable_save_is_not_overwritten(self):
        save_state(FarmState(coins=999), self.save_path)
        original = self.save_path.read_text(encoding="utf-8")
        with mock.patch.object(Path, "open", side_effect=PermissionError("被占用")):
            app = farm_gui.FarmApp(
                save_path=self.save_path,
                start_loops=False,
                clock=lambda: self.now,
            )
        try:
            self.assertIn("读取存档失败", app.status_var.get())
            app._on_plot_click(0)
            app._on_close()
        finally:
            try:
                app.destroy()
            except tk.TclError:
                pass
        self.assertEqual(self.save_path.read_text(encoding="utf-8"), original)
        self.assertFalse(list(self.save_path.parent.glob("save.corrupt-*.json")))


class GuiLayoutTests(unittest.TestCase):
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
        self.app.update()

    def tearDown(self):
        self.app.destroy()
        self.tmp.cleanup()

    def test_plot_grid_fits_in_farm_area(self):
        card = self.app.plot_cards[3]
        self.assertLessEqual(
            card.winfo_x() + card.winfo_width(),
            self.app.farm_frame.winfo_width(),
        )
        self.assertLessEqual(self.app.winfo_reqwidth(), self.app.winfo_width())

    def test_seed_buttons_fit_their_text(self):
        for crop_id, button in self.app.seed_buttons.items():
            font = tkfont.Font(font=button.cget("font"))
            self.assertLessEqual(
                font.measure(button.cget("text")),
                button.winfo_width(),
                "{} 的种子按钮文字被裁切".format(crop_id),
            )

    def test_warehouse_labels_fit_their_text(self):
        for label in _label_widgets(self.app.warehouse_frame):
            text = label.cget("text")
            if not text:
                continue
            font = tkfont.Font(font=label.cget("font"))
            self.assertLessEqual(
                font.measure(text),
                label.winfo_width(),
                "仓库文字 {!r} 需要 {}px，但标签只有 {}px".format(
                    text, font.measure(text), label.winfo_width()
                ),
            )
        font = tkfont.Font(font=self.app.sell_all_button.cget("font"))
        self.assertLessEqual(
            font.measure(self.app.sell_all_button.cget("text")),
            self.app.sell_all_button.winfo_width(),
        )

    @unittest.skipUnless(sys.platform == "win32", "系统 DPI 布局测试仅限 Windows")
    def test_layout_fits_with_real_dpi_awareness(self):
        script = r'''
import sys, tempfile
from pathlib import Path
import tkinter.font as tkfont
import farm_gui

sys.stdout.reconfigure(encoding="utf-8")
farm_gui._enable_dpi_awareness()
app = farm_gui.FarmApp(
    save_path=Path(tempfile.mkdtemp()) / "save.json",
    start_loops=False,
)
app.state.coins = 1000
app.state.plant(0, "nangua", app.clock())
app.state.plant(1, "xiaobaicai", app.clock() - 1800)
app.refresh()
app.update_idletasks()
app.update()
problems = []

if app.winfo_reqwidth() > app.winfo_width():
    problems.append("window req %d > width %d" % (app.winfo_reqwidth(), app.winfo_width()))

card = app.plot_cards[3]
if card.winfo_x() + card.winfo_width() > app.farm_frame.winfo_width():
    problems.append("card 4 clipped")

def labels(widget):
    for child in widget.winfo_children():
        if child.winfo_class() == "Label":
            yield child
        for sub in labels(child):
            yield sub

for label in labels(app.warehouse_frame):
    text = label.cget("text")
    if not text:
        continue
    need = tkfont.Font(font=label.cget("font")).measure(text)
    if need > label.winfo_width():
        problems.append("label %r needs %d > %d" % (text, need, label.winfo_width()))

for crop_id, button in app.sell_buttons.items():
    if button.winfo_x() + button.winfo_width() > button.master.winfo_width():
        problems.append("sell button %s overflows row" % crop_id)

for crop_id, button in app.seed_buttons.items():
    need = tkfont.Font(font=button.cget("font")).measure(button.cget("text"))
    if need > button.winfo_width():
        problems.append("seed button %s needs %d > %d" % (crop_id, need, button.winfo_width()))

for card in app.plot_cards:
    width = card.canvas.winfo_width()
    height = card.canvas.winfo_height()
    for item in card.canvas.find_all():
        if card.canvas.type(item) != "text":
            continue
        bbox = card.canvas.bbox(item)
        if bbox[0] < 0 or bbox[1] < 0 or bbox[2] > width or bbox[3] > height:
            problems.append(
                "canvas text %r bbox %r outside %dx%d"
                % (card.canvas.itemcget(item, "text"), bbox, width, height)
            )

app.destroy()
if problems:
    print("\n".join(problems))
    sys.exit(1)
'''
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            cwd=str(Path(__file__).resolve().parent),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
