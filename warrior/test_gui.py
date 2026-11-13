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


class TargetingTests(GuiTestCase):

    def two_enemy_combat(self, potions=None):
        app = make_app(self.root, seed=7)
        combat = to_combat(app, enemies=['goblin', 'wolf'],
                           hand=['strike', 'cleave', 'defend', 'defend',
                                 'defend'])
        if potions:
            app.game.hero.potions = list(potions)
            app.show_combat()
        return app, combat

    def test_single_target_card_enters_targeting(self):
        app, combat = self.two_enemy_combat()
        app.hand_buttons[0].invoke()  # strike 单体、双敌 → 选目标
        self.assertEqual(app._pending_card, 0)
        self.assertTrue(app.cancel_btn.winfo_manager() != '')

    def test_target_click_hits_only_chosen(self):
        app, combat = self.two_enemy_combat()
        app.hand_buttons[0].invoke()
        hp0, hp1 = combat.enemies[0].hp, combat.enemies[1].hp
        app.enemy_buttons[1].invoke()  # 打 1 号 wolf
        self.assertEqual(combat.enemies[0].hp, hp0)
        self.assertEqual(combat.enemies[1].hp, hp1 - 6)
        self.assertIsNone(app._pending_card)

    def test_cancel_returns_to_plain(self):
        app, combat = self.two_enemy_combat()
        app.hand_buttons[0].invoke()
        hp0, hp1 = combat.enemies[0].hp, combat.enemies[1].hp
        app._cancel_targeting()
        self.assertEqual(combat.enemies[0].hp, hp0)
        self.assertEqual(combat.enemies[1].hp, hp1)
        self.assertIsNone(app._pending_card)

    def test_reclick_same_card_cancels(self):
        app, combat = self.two_enemy_combat()
        app.hand_buttons[0].invoke()
        app.hand_buttons[0].invoke()
        self.assertIsNone(app._pending_card)
        self.assertEqual(combat.enemies[0].hp, 14)

    def test_aoe_no_target_needed(self):
        app, combat = self.two_enemy_combat()
        app.hand_buttons[1].invoke()  # cleave 群伤直接结算
        self.assertEqual(combat.enemies[0].hp, 14 - 7)
        self.assertEqual(combat.enemies[1].hp, 12 - 7)
        self.assertIsNone(app._pending_card)

    def test_potion_targeted_uses_targeting(self):
        app, combat = self.two_enemy_combat(potions=['p_acid'])
        app.potion_buttons[0].invoke()
        self.assertEqual(app._pending_potion, 0)
        app.enemy_buttons[0].invoke()
        self.assertEqual(combat.enemies[0].hp, 14 - 12)
        self.assertEqual(app.game.hero.potions, [])


from test_run import find_node, force_node  # noqa: E402


class NodeScreensTests(GuiTestCase):

    def app_at(self, kind, seed=7):
        app = make_app(self.root, seed)
        node = find_node(app.game, kind)
        force_node(app.game, node)
        app.show_screen()
        return app

    def test_campfire_buttons_state(self):
        app = self.app_at('campfire')
        self.assertTrue(app.sleep_btn.instate(('disabled',)))  # 满血
        app.sharpen_btn.invoke()
        self.assertEqual(app.game.hero.weapon_sharpen, 1)
        self.assertTrue(app.game.node_done)

    def test_campfire_forge_grid(self):
        app = self.app_at('campfire', seed=8)
        app.forge_btn.invoke()
        slot = next(i for i, (c, u) in enumerate(app.game.hero.deck)
                    if c == 'strike')
        app.forge_card_buttons[slot].invoke()
        self.assertEqual(app.game.hero.deck[slot], ('strike', True))
        self.assertTrue(app.game.node_done)

    def test_event_option_disabled_and_apply(self):
        app = self.app_at('event')
        app.game.node_obj = content.EVENTS['goblin_gambler']
        app.show_screen()
        app.game.hero.gold = 0
        app.show_screen()
        self.assertTrue(app.event_option_buttons[0].instate(('disabled',)))
        app.event_option_buttons[2].invoke()  # 不赌
        self.assertTrue(app.game.node_done)

    def test_event_followup_opens_combat(self):
        app = self.app_at('event')
        app.game.node_obj = content.EVENTS['mimic_chest']
        app.show_screen()
        app.event_option_buttons[1].invoke()  # 识破先手
        self.assertIsNotNone(app.game.active)
        texts = ' '.join(b.cget('text') for b in app.enemy_buttons)
        self.assertIn('宝箱怪', texts)

    def test_chest_take_or_leave(self):
        app = self.app_at('chest')
        loot = dict(app.game.node_obj)
        app.equip_btn.invoke()
        self.assertEqual(app.game.hero.gold, loot['gold'])
        if loot['kind'] == 'weapon':
            self.assertEqual(app.game.hero.weapon, loot['id'])
        else:
            self.assertEqual(app.game.hero.armor, loot['id'])
        app2 = self.app_at('chest', seed=9)
        loot2 = dict(app2.game.node_obj)
        weapon2 = app2.game.hero.weapon
        app2.gold_only_btn.invoke()
        self.assertEqual(app2.game.hero.gold, loot2['gold'])
        self.assertEqual(app2.game.hero.weapon, weapon2)

    def _pending_combat_win(self, app):
        g = app.game
        g.go(g.map.entry_ids[0])
        g.enter()
        for e in g.active.enemies:
            e.hp = 0
        g.active.status = 'win'
        g.combat_finished()
        app.show_screen()
        return g

    def test_rewards_take_card(self):
        app = make_app(self.root, seed=7)
        g = self._pending_combat_win(app)
        n0 = len(g.hero.deck)
        self.assertEqual(len(app.card_choice_buttons), len(g.pending['card_choices']))
        app.card_choice_buttons[0].invoke()
        self.assertEqual(len(g.hero.deck), n0 + 1)
        self.assertIsNone(g.pending)

    def test_rewards_skip(self):
        app = make_app(self.root, seed=7)
        g = self._pending_combat_win(app)
        n0 = len(g.hero.deck)
        app.skip_btn.invoke()
        self.assertEqual(len(g.hero.deck), n0)
        self.assertTrue(g.node_done)

    def test_rewards_relic_choice(self):
        app = make_app(self.root, seed=7)
        g = app.game
        g.pending = {'gold': 0, 'relic_choices': ['ember', 'purse', 'torch'],
                     'relic_drop': None, 'card_choices': [], 'lines': []}
        app.show_screen()
        app.relic_choice_buttons[0].invoke()
        self.assertIn('ember', g.hero.relics)
        self.assertTrue(g.node_done)


if __name__ == '__main__':
    unittest.main()
