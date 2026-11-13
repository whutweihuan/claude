# -*- coding: utf-8 -*-
"""Tkinter 鼠标界面测试。回调级单测可在有/无显示下运行（无显示则 skip），
子进程 DPI 布局回归见任务 7。"""
import unittest

import tkinter as tk

import core


def _tk_available():
    try:
        r = tk.Tk()
        r.destroy()
        return True
    except Exception:
        return False


TK_OK = _tk_available()


class GuiTestCase(unittest.TestCase):
    def setUp(self):
        if not TK_OK:
            self.skipTest('无可用 Tk 显示环境')
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass


import gui  # noqa: E402


def make_app(root, seed=None, on_finish=None):
    app = gui.WarriorGUI(root, on_finish=on_finish)
    if seed is not None:
        app.start_run(seed)
    return app


class SkeletonTests(GuiTestCase):

    def test_title_then_start_shows_map(self):
        app = make_app(self.root)
        app.show_title()
        app.seed_entry.delete(0, tk.END)
        app.seed_entry.insert(0, '7')
        app.start_btn.invoke()
        self.assertTrue(isinstance(app.game, core.Run))
        self.assertEqual(app.game.seed, 7)
        self.assertEqual(len(app.map_buttons), len(app.game.map.nodes))
        for nid in app.game.map.entry_ids:
            self.assertFalse(app.map_buttons[nid].instate(('disabled',)))

    def test_map_disabled_nodes(self):
        app = make_app(self.root, seed=7)
        choices = set(app.game.choices())
        for nid, btn in app.map_buttons.items():
            if nid in choices:
                self.assertFalse(btn.instate(('disabled',)), nid)
            else:
                self.assertTrue(btn.instate(('disabled',)), nid)

    def test_status_bar_shows_core_state(self):
        app = make_app(self.root, seed=7)
        text = app.status_var.get()
        self.assertIn('生命 80/80', text)
        self.assertIn('金币 0', text)

    def test_run_mode_dispatch(self):
        import main as main_mod
        self.assertEqual(main_mod.run_mode(['--text']), 'text')
        self.assertEqual(main_mod.run_mode([]), 'gui')

    def test_apply_result_to_records_skips_aborted(self):
        import os
        import tempfile
        import main as main_mod
        path = os.path.join(tempfile.mkdtemp(), 'records.json')
        st = main_mod.apply_result_to_records({'outcome': 'aborted'}, path)
        self.assertEqual(st, 'skipped')
        self.assertFalse(os.path.exists(path))


if __name__ == '__main__':
    unittest.main()
