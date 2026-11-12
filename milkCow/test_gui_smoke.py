# -*- coding: utf-8 -*-
"""cow_gui 冒烟与布局测试。构建窗口用 start_loops=False，不进 mainloop。"""

import json
import subprocess
import sys
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

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

    def test_shop_buttons_show_not_enough_coins(self):
        self.app.state.coins = 0
        self.app.refresh()
        self.assertEqual(self.app.buy_calf_button.cget("text"), "金币不够")
        self.assertEqual(self.app.buy_feed_button.cget("text"), "金币不够")
        self.assertEqual(self.app.buy_machine_button.cget("text"), "金币不够")
        self.assertEqual(self.app.expand_button.cget("text"), "金币不够")

    def test_feed_buys_and_feeds_success(self):
        from cow_core import Cow
        s = self.app.state
        s.coins = 1000
        s.cows.append(Cow(id=s.next_cow_id, name="大壮",
                          born_at=time.time() - 600, last_milked_at=time.time()))
        calf_id = s.next_cow_id
        s.next_cow_id += 1
        self.app._on_buy_feed_click()
        self.assertEqual(s.feed_count, 1)
        self.assertIn("背包 1 份", self.app.status_var.get())
        self.app.selected_id = calf_id
        self.app._on_feed_click()
        self.assertEqual(s.find_cow(calf_id).fed_count, 1)
        self.assertIn("喂了 大壮", self.app.status_var.get())

    def test_expand_success_then_full_label(self):
        s = self.app.state
        s.coins = 10000
        self.app._on_expand_click()
        self.assertEqual(s.capacity, 5)
        self.assertIn("扩建到 5", self.app.status_var.get())
        s.capacity = 12
        self.app.refresh()
        self.assertEqual(self.app.expand_button.winfo_manager(), "")
        self.assertEqual(self.app.expand_label.cget("text"), "已全部扩建")
        self.assertEqual(self.app.expand_label.winfo_manager(), "pack")

    def test_ready_segment_in_action_bar(self):
        # 设计机制：有空位时可孕牛会在结算瞬间补孕，"可孕"只在等位时可见
        s = self.app.state
        s.capacity = 1
        cow = s.cows[0]
        cow.pregnant = False
        cow.due_at = 0.0
        cow.recovery_until = 0.0
        self.app.selected_id = 1
        self.app.refresh()
        self.assertIn("可孕（等空位）", self.app.action_var.get())

    def test_sell_pregnant_cow_mentions_fetus(self):
        self.app.selected_id = 1  # 花花开局已怀
        self.assertTrue(self.app.state.cows[0].pregnant)
        self.app._on_sell_cow_click()
        self.assertIn("腹中", self.app.status_var.get())

    def test_machine_progress_blocks(self):
        s = self.app.state
        s.coins = 5000
        s.buy_machine()
        s.warehouse["milk"] = 3
        self.app._on_process_click(0)
        text = self.app.machine_rows[0][0].get()
        self.assertRegex(text, r"^#1 [░▓]{6} \d+(:\d+)+$")

    def test_operations_persist_to_save(self):
        self._make_cow_full()
        self.app._on_cow_click(1)
        self.assertTrue(self.save_path.exists())
        self.assertIn("milk", self.save_path.read_text(encoding="utf-8"))

    def test_feed_button_shows_disable_reason(self):
        self.app.selected_id = 1  # 花花是成年牛
        self.app.refresh()
        self.assertIn("已成年", self.app.feed_button.cget("text"))
        self.assertEqual(str(self.app.feed_button.cget("state")), "disabled")

    def test_feed_button_ready_for_fed_calf(self):
        from cow_core import Cow
        s = self.app.state
        s.cows.append(Cow(id=s.next_cow_id, name="团团",
                          born_at=time.time(), last_milked_at=time.time()))
        s.next_cow_id += 1
        s.feed_count = 1
        self.app.selected_id = s.next_cow_id - 1
        self.app.refresh()
        self.assertIn("背包 1 份", self.app.feed_button.cget("text"))
        self.assertEqual(str(self.app.feed_button.cget("state")), "normal")


def snapshot_core(s):
    return (
        s.coins, s.capacity,
        sorted((c.id, c.born_at, c.fed_count, c.pregnant, c.due_at,
                c.recovery_until, c.last_milked_at, c.name) for c in s.cows),
        list(s.machines), dict(s.warehouse), s.feed_count,
        s.total_births, s.total_income, s.next_cow_id,
    )


class GuiAnimationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.save_path = Path(self.tmp.name) / "save.json"
        self.app = cow_gui.CowApp(save_path=self.save_path, start_loops=False,
                                  anim_seed=7)
        self.app.update_idletasks()

    def tearDown(self):
        try:
            self.app.destroy()
        except tk.TclError:
            pass
        self.tmp.cleanup()

    def test_positions_advance_with_seed(self):
        track_a = []
        for _ in range(30):
            self.app._animate_step(0.3)
        track_a = dict(self.app.positions)
        self.app.destroy()
        app_b = cow_gui.CowApp(save_path=self.save_path, start_loops=False,
                               anim_seed=7)
        for _ in range(30):
            app_b._animate_step(0.3)
        self.assertEqual(track_a, dict(app_b.positions))
        app_b.destroy()
        for (x, y) in track_a.values():
            self.assertTrue(60 <= x <= 705, "x 越界: {}".format(x))
            self.assertTrue(80 <= y <= 395, "y 越界: {}".format(y))

    def test_animation_moves_at_least_one_cow(self):
        before = dict(self.app.positions)
        for _ in range(30):
            self.app._animate_step(0.3)
        self.assertNotEqual(before, dict(self.app.positions))

    def test_animation_does_not_mutate_state(self):
        snap = snapshot_core(self.app.state)
        for _ in range(20):
            self.app._animate_step(0.3)
        self.assertEqual(snap, snapshot_core(self.app.state))

    def test_closed_animation_leaves_cow_still(self):
        before = dict(self.app.positions)
        self.app.update()
        self.assertEqual(before, dict(self.app.positions))

    def test_sold_cow_position_removed(self):
        import time as _time
        from cow_core import Cow
        s = self.app.state
        s.cows.append(Cow(id=s.next_cow_id, name="大壮",
                          born_at=_time.time() - 10800,
                          last_milked_at=_time.time()))
        new_id = s.next_cow_id
        s.next_cow_id += 1
        self.app.refresh()
        self.assertIn(new_id, self.app.positions)
        s.sell_cow(new_id, _time.time())
        self.app.refresh()
        self.assertNotIn(new_id, self.app.positions)
        self.assertNotIn(new_id, self.app._targets)


class GuiPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.save_path = Path(self.tmp.name) / "save.json"

    def tearDown(self):
        self.tmp.cleanup()

    def _build(self):
        app = cow_gui.CowApp(save_path=self.save_path, start_loops=False)
        app.update_idletasks()
        return app

    def test_startup_settles_and_persists(self):
        app = self._build()
        app.destroy()
        self.assertTrue(self.save_path.exists())
        data = json.loads(self.save_path.read_text(encoding="utf-8"))
        self.assertTrue(data["cows"][0]["pregnant"])  # 开局结算已落盘

    def test_close_saves_changes(self):
        app = self._build()
        app.state.coins = 555
        app._on_close()
        data = json.loads(self.save_path.read_text(encoding="utf-8"))
        self.assertEqual(data["coins"], 555)

    def test_corrupt_save_shows_warning(self):
        app = self._build()
        app.destroy()
        self.save_path.write_text("{ 坏档", encoding="utf-8")
        app2 = self._build()
        try:
            self.assertIn("存档损坏", app2.status_var.get())
            self.assertEqual(app2.state.coins, 200)
            self.assertTrue(list(self.save_path.parent.glob("save.corrupt-*.json")))
        finally:
            app2.destroy()

    def test_readonly_mode_does_not_overwrite(self):
        app = self._build()
        app.state.coins = 999
        app._save()
        app.destroy()
        original = self.save_path.read_text(encoding="utf-8")
        with mock.patch.object(Path, "open", side_effect=PermissionError("被占用")):
            app2 = cow_gui.CowApp(save_path=self.save_path, start_loops=False)
        try:
            self.assertIn("读取存档失败", app2.status_var.get())
            self.assertTrue(app2._readonly)
            app2._on_close()
        finally:
            try:
                app2.destroy()
            except tk.TclError:
                pass
        self.assertEqual(self.save_path.read_text(encoding="utf-8"), original)
        self.assertFalse(list(self.save_path.parent.glob("save.corrupt-*.json")))


_LAYOUT_PROBE = r'''
import sys, tempfile, time
from pathlib import Path
import tkinter.font as tkfont
import cow_gui
from cow_core import Cow, MILK_INTERVAL

sys.stdout.reconfigure(encoding="utf-8")
cow_gui._enable_dpi_awareness()
app = cow_gui.CowApp(save_path=Path(tempfile.mkdtemp()) / "save.json",
                     start_loops=False)
now = time.time()
s = app.state
s.coins = 123456
s.capacity = 6
s.cows.append(Cow(id=s.next_cow_id, name="妞妞", born_at=now - 10800,
                  last_milked_at=now - MILK_INTERVAL - 1)); s.next_cow_id += 1
s.cows.append(Cow(id=s.next_cow_id, name="大壮", born_at=now - 10800,
                  pregnant=True, due_at=now + 3600)); s.next_cow_id += 1
s.cows.append(Cow(id=s.next_cow_id, name="团团", born_at=now - 10800,
                  recovery_until=now + 900,
                  last_milked_at=now - MILK_INTERVAL - 1)); s.next_cow_id += 1
s.cows.append(Cow(id=s.next_cow_id, name="默默", born_at=now,
                  last_milked_at=now)); s.next_cow_id += 1
s.buy_machine(); s.buy_machine(); s.buy_machine()
s.warehouse.update({"milk": 1234, "cheese": 56})
s.process(0, now)
s.feed_count = 7
s.expand_capacity()
app.selected_id = 1
app.refresh()
app.update_idletasks()
app.update()
problems = []

if app.winfo_reqwidth() > app.winfo_width():
    problems.append("window req %d > width %d"
                    % (app.winfo_reqwidth(), app.winfo_width()))
if app.winfo_reqheight() > app.winfo_height():
    problems.append("window reqh %d > height %d"
                    % (app.winfo_reqheight(), app.winfo_height()))
if app.minsize()[0] < 1260 or app.minsize()[1] < 640:
    problems.append("minsize %r" % (app.minsize(),))

def widget_text(w):
    keys = w.keys()
    if "textvariable" in keys:
        tv = str(w.cget("textvariable") or "")
        if tv:
            try:
                return str(w.tk.globalgetvar(tv))
            except Exception:
                return ""
    return str(w.cget("text") or "")

def walk(w):
    for child in w.winfo_children():
        yield child
        for got in walk(child):
            yield got

for widget in walk(app):
    if widget.winfo_class() not in ("Label", "Button"):
        continue
    if not widget.winfo_ismapped():
        continue  # 隐藏的替换控件不参与测量
    text = widget_text(widget)
    if not text:
        continue
    need = tkfont.Font(font=widget.cget("font")).measure(text)
    if need > widget.winfo_width():
        problems.append("%s %r needs %d > %d"
                        % (widget.winfo_class(), text, need, widget.winfo_width()))

canvas = app.pasture
cw, ch = canvas.winfo_width(), canvas.winfo_height()
if ch < canvas.HEIGHT - 2:
    problems.append("pasture squeezed to %d < %d" % (ch, canvas.HEIGHT))
for item in canvas.find_all():
    if canvas.type(item) != "text":
        continue
    bbox = canvas.bbox(item)
    if bbox[0] < 0 or bbox[1] < 0 or bbox[2] > cw or bbox[3] > ch:
        problems.append("canvas text %r bbox %r outside %dx%d"
                        % (canvas.itemcget(item, "text"), bbox, cw, ch))
    if bbox[1] < 2:
        problems.append("canvas text %r too close to top: %r"
                        % (canvas.itemcget(item, "text"), bbox))

app.destroy()
if problems:
    print("\n".join(problems))
    sys.exit(1)
'''


class GuiLayoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.save_path = Path(self.tmp.name) / "save.json"
        self.app = cow_gui.CowApp(save_path=self.save_path, start_loops=False)
        self.app.update_idletasks()
        self.app.update()

    def tearDown(self):
        self.app.destroy()
        self.tmp.cleanup()

    def _texts(self, widget):
        found = []
        for child in widget.winfo_children():
            if child.winfo_class() in ("Label", "Button") \
                    and child.winfo_ismapped():
                tv = str(child.cget("textvariable") or "")
                text = str(child.tk.globalgetvar(tv)) if tv else str(child.cget("text"))
                if text:
                    found.append((child, text))
            found.extend(self._texts(child))
        return found

    def test_warehouse_labels_fit(self):
        import tkinter.font as tkfont
        for label, text in self._texts(self.app.warehouse_frame) + \
                self._texts(self.app):
            font = tkfont.Font(font=label.cget("font"))
            self.assertLessEqual(
                font.measure(text), label.winfo_width(),
                "仓库文字 {!r} 需要 {}px，标签只有 {}px".format(
                    text, font.measure(text), label.winfo_width()))

    def test_window_and_minsize(self):
        self.assertLessEqual(self.app.winfo_reqwidth(), self.app.winfo_width())
        self.assertGreaterEqual(self.app.minsize()[0], 1260)

    @unittest.skipUnless(sys.platform == "win32", "真实 DPI 布局测试仅限 Windows")
    def test_layout_fits_with_real_dpi_awareness(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, "-c", _LAYOUT_PROBE],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, cwd=str(Path(__file__).resolve().parent),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
