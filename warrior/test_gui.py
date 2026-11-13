# -*- coding: utf-8 -*-
"""Tkinter 鼠标界面测试。回调级单测可在有/无显示下运行（无显示则 skip），
子进程 DPI 布局回归见任务 7。"""
import unittest

import tkinter as tk

import content
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


def to_combat(app, enemies=None, hand=None, energy=None):
    g = app.game
    g.go(g.map.entry_ids[0])
    g.enter()
    if enemies is not None:
        g.active.enemies = [core.EnemyInstance(content.ENEMIES[e], 1)
                            for e in enemies]
    if hand is not None:
        g.active.hand = [(c, False) for c in hand]
    if energy is not None:
        g.active.energy = energy
    app.show_screen()
    return g.active


class CombatScreenTests(GuiTestCase):

    def test_combat_widgets_render(self):
        app = make_app(self.root, seed=7)
        combat = to_combat(app, enemies=['goblin'], energy=0)
        self.assertEqual(len(app.hand_buttons), len(combat.hand))
        for btn in app.hand_buttons:
            self.assertTrue(btn.instate(('disabled',)))
        text = ' '.join(b.cget('text') for b in app.enemy_buttons)
        self.assertIn('意图', text)
        log = app.log_text.get('1.0', tk.END)
        self.assertIn('遭遇', log)

    def test_click_card_plays(self):
        app = make_app(self.root, seed=7)
        combat = to_combat(app, enemies=['goblin'],
                           hand=['strike', 'defend', 'defend', 'defend',
                                 'defend'])
        hp0 = combat.enemies[0].hp
        app.hand_buttons[0].invoke()
        self.assertEqual(combat.enemies[0].hp, hp0 - 6)
        self.assertIn('打击', app.log_text.get('1.0', tk.END))

    def test_end_turn_button(self):
        app = make_app(self.root, seed=7)
        combat = to_combat(app, enemies=['goblin'])
        turn0 = combat.turn
        app.end_btn.invoke()
        self.assertEqual(combat.turn, turn0 + 1)

    def test_click_after_combat_over_ignored(self):
        app = make_app(self.root, seed=7)
        combat = to_combat(app, enemies=['goblin'],
                           hand=['strike', 'strike', 'strike'])
        for e in combat.enemies:
            e.hp = 0
        combat.status = 'win'
        app.hand_buttons[0].invoke()  # 不得抛异常
        self.assertEqual(combat.enemies[0].hp, 0)

    def test_win_click_lands_on_rewards(self):
        app = make_app(self.root, seed=7)
        combat = to_combat(app, enemies=['goblin'], hand=['strike'] * 3)
        combat.enemies[0].hp = 3
        app.show_combat()
        app.hand_buttons[0].invoke()
        self.assertEqual(combat.status, 'win')
        self.assertIsNotNone(app.game.pending)


if __name__ == '__main__':
    unittest.main()
