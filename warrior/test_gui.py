# -*- coding: utf-8 -*-
"""Tkinter 鼠标界面测试。回调级单测可在有/无显示下运行（无显示则 skip），
子进程 DPI 布局回归见任务 7。"""
import os
import sys
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
    app._action_debounce = 0.0  # 测试默认关防抖；防抖行为单独测
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


class ShopScreenTests(GuiTestCase):

    def app_at_shop(self, seed=80, relics=()):
        app = make_app(self.root, seed)
        app.game.hero.relics = list(relics)
        node = find_node(app.game, 'shop')
        force_node(app.game, node)
        app.show_screen()
        return app

    def test_shop_slots_and_buy(self):
        app = self.app_at_shop()
        shop = app.game.shop
        self.assertEqual(len(app.shop_slot_buttons), 7)
        wi = [i for i, s in enumerate(shop.slots) if s.kind == 'weapon'][0]
        wid = shop.slots[wi].content_id
        app.game.hero.gold = 999
        app.show_shop()
        price = shop.slots[wi].price
        app.shop_slot_buttons[wi].invoke()
        self.assertEqual(app.game.hero.weapon, wid)
        self.assertEqual(app.game.hero.gold, 999 - price)
        self.assertTrue(shop.slots[wi].sold)
        app.show_shop()
        self.assertTrue(app.shop_slot_buttons[wi].instate(('disabled',)))

    def test_shop_unaffordable_disabled(self):
        app = self.app_at_shop(seed=81)
        app.game.hero.gold = 0
        app.show_shop()
        for btn in app.shop_slot_buttons:
            self.assertTrue(btn.instate(('disabled',)))
        self.assertTrue(app.remove_btn.instate(('disabled',)))

    def test_discount_shows_base_price(self):
        app = self.app_at_shop(seed=82, relics=['hag_hat'])
        texts = [b.cget('text') for b in app.shop_slot_buttons]
        with_disc = [t for t in texts if '原' in t]
        self.assertTrue(with_disc)
        for t in with_disc:
            self.assertIn('金币', t)

    def test_remove_card_service(self):
        app = self.app_at_shop(seed=83)
        app.game.hero.gold = 999
        app.show_shop()
        cost = app.game.shop.remove_cost
        n0 = len(app.game.hero.deck)
        app.remove_btn.invoke()
        slot0_btn = app.deck_card_buttons[0]
        slot0_btn.invoke()
        self.assertEqual(len(app.game.hero.deck), n0 - 1)
        self.assertEqual(app.game.hero.gold, 999 - cost)

    def test_close_shop(self):
        app = self.app_at_shop(seed=84)
        app.shop_close_btn.invoke()
        self.assertTrue(app.game.node_done)


class EndScreenTests(GuiTestCase):

    def win_boss(self, app):
        g = app.game
        force_node(g, find_node(g, 'boss'))
        for e in g.active.enemies:
            e.hp = 0
        g.active.status = 'win'
        g.combat_finished()
        app.show_screen()

    def test_on_finish_called_once_per_run(self):
        calls = []

        def on_finish(result):
            calls.append(result)
            return 'ok'

        app = make_app(self.root, seed=7, on_finish=on_finish)
        self.win_boss(app)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['outcome'], 'win')
        self.assertEqual(calls[0]['depth'], 11)
        app.show_end()
        self.assertEqual(len(calls), 1)

    def test_replay_uses_new_seed(self):
        app = make_app(self.root, seed=7, on_finish=lambda r: 'ok')
        self.win_boss(app)
        old = app.game.seed
        app.replay_btn.invoke()
        self.assertNotEqual(app.game.seed, old)
        self.assertFalse(app.game.finished)

    def test_leave_button_destroys_root(self):
        app = make_app(self.root, seed=7, on_finish=lambda r: 'ok')
        self.win_boss(app)
        app.leave_app_btn.invoke()
        self.assertRaises(tk.TclError, app.root.winfo_exists)

    def test_on_finish_io_error_hint(self):
        app = make_app(self.root, seed=7, on_finish=lambda r: 'io_error')
        self.win_boss(app)
        self.assertIn('写入失败', app.end_msg_var.get())

    def test_close_midrun_no_record(self):
        calls = []
        app = make_app(self.root, seed=7, on_finish=calls.append)
        app._on_close()
        self.assertEqual(calls, [])


LAYOUT_SCRIPT = r'''
import sys
sys.stdout.reconfigure(encoding='utf-8')
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

import core
import content
import gui
import test_run

gui._enable_dpi_awareness()
root = tk.Tk()
app = gui.WarriorGUI(root, on_finish=lambda r: 'ok')
app.start_run(4242)
game = app.game
problems = []


def walk(w):
    yield w
    for c in w.winfo_children():
        for g in walk(c):
            yield g


_STYLE = ttk.Style()


def _wfont(w):
    try:
        f = w.cget('font')
        if f:
            return tkfont.Font(font=f)
    except (tk.TclError, KeyError, ValueError):
        pass
    cls = w.winfo_class()
    if cls == 'TButton':
        name = _STYLE.lookup('TButton', 'font')
        if name:
            try:
                return tkfont.Font(font=name)
            except (tk.TclError, ValueError):
                pass
    if cls == 'TLabel':
        name = _STYLE.lookup('TLabel', 'font')
        if name:
            try:
                return tkfont.Font(font=name)
            except (tk.TclError, ValueError):
                pass
    return tkfont.nametofont('TkDefaultFont')


def check(tag):
    root.update_idletasks()
    root.update()
    for w in walk(root):
        if not w.winfo_ismapped():
            continue
        cls = w.winfo_class()
        if cls in ('Label', 'Button', 'TLabel', 'TButton'):
            text = str(w.cget('text'))
            if not text:
                continue
            wl = 0
            try:
                wl = int(w.cget('wraplength'))
            except (ValueError, tk.TclError):
                wl = 0
            if wl == 0:
                for line in text.split('\n'):
                    need = _wfont(w).measure(line)
                    if need > w.winfo_width() + 2:
                        problems.append('%s: %r needs %d > %d'
                                        % (tag, line[:16], need,
                                           w.winfo_width()))
            if cls in ('Button', 'TButton'):
                if (w.winfo_x() + w.winfo_width()
                        > w.master.winfo_width() + 2):
                    problems.append('%s: %r overflows row'
                                    % (tag, text[:12]))
                if w.winfo_height() < 8:
                    problems.append('%s: %r collapsed to h=%d'
                                    % (tag, text[:12], w.winfo_height()))
        if isinstance(w, tk.Canvas):
            cw = w.winfo_width()
            chh = w.winfo_height()
            for item in w.find_all():
                bbox = w.bbox(item)
                if not bbox:
                    continue
                if (bbox[0] < -1 or bbox[1] < -1
                        or bbox[2] > cw + 1 or bbox[3] > chh + 1):
                    problems.append('%s: canvas bbox out' % tag)
    if root.winfo_reqwidth() > 1120:
        problems.append('%s: window reqwidth %d > 1120'
                        % (tag, root.winfo_reqwidth()))
    if root.winfo_reqheight() > 1080:
        problems.append('%s: window reqheight %d > 1080'
                        % (tag, root.winfo_reqheight()))
    log = getattr(app, 'log_text', None)
    try:
        if log is not None and log.winfo_exists() \
                and log.winfo_ismapped() and log.winfo_height() < 8:
            problems.append('%s: log collapsed' % tag)
    except tk.TclError:
        pass


# 1) 战斗屏：12 张手牌 + 3 带状态敌人 + 长日志
test_run.force_node(game, test_run.find_node(game, 'combat'))
game.active.enemies = [
    core.EnemyInstance(content.ENEMIES[e], 1)
    for e in ('goblin', 'wolf', 'slime')]
for e in game.active.enemies:
    e.intent = '攻击 5×2'
    e.block = 5
    e.vulnerable = 1
    e.poison = 2
game.active.hand = ([('strike', False)] * 4 + [('defend', True)] * 4
                    + [('heavy', False)] * 2 + [('cleave', True)] * 2)
app._combat_log = ['这是一条足够长的战斗日志用来验证换行与宽度限制是否有效。'] * 3
app.show_combat()
check('combat')

# 2) 火堆屏 + 锻造展开
game.node_done = True
game.pending = None
game.active = None
test_run.force_node(game, test_run.find_node(game, 'campfire'))
app._camp_forge_mode = True
app.show_campfire()
check('campfire')
app._camp_forge_mode = False

# 3) 商店屏 + 删牌展开
game.node_done = True
test_run.force_node(game, test_run.find_node(game, 'shop'))
game.hero.gold = 999
app._shop_remove_mode = True
app.show_shop()
check('shop')
app._shop_remove_mode = False

# 4) 奖励屏：卡牌三选一（最长文本）与遗物三选一
game.node_done = True
game.pending = {
    'gold': 40,
    'relic_choices': [],
    'relic_drop': None,
    'card_choices': [('annihilate', False), ('execute', False),
                     ('blood_price', False)],
    'lines': ['获得 40 金币。']}
app.show_rewards()
check('rewards')
game.pending = {
    'gold': 0,
    'relic_choices': ['idol', 'hourglass', 'warpaint'],
    'relic_drop': None,
    'card_choices': [],
    'lines': []}
app.show_rewards()
check('rewards-relic')
game.pending = None

# 5) 事件屏（渲染测试：直接把 current 指向事件节点，不走真实移动）
evnode = test_run.find_node(game, 'event')
game.current = evnode.id
game.node_done = False
game.active = None
game.pending = None
game.node_obj = content.EVENTS['goblin_gambler']
app.show_event()
check('event')

# 6) 地图屏
game.node_done = True
app.show_map()
check('map')

root.destroy()
if problems:
    print('\n'.join(problems))
    sys.exit(1)
'''


class LayoutRegressionTests(unittest.TestCase):

    def test_layout_fits_with_real_dpi_awareness(self):
        if not TK_OK:
            self.skipTest('无可用 Tk 显示环境')
        import subprocess
        result = subprocess.run(
            [sys.executable, '-c', LAYOUT_SCRIPT],
            capture_output=True, text=True, encoding='utf-8',
            errors='replace', timeout=60, cwd=os.path.dirname(
                os.path.abspath(__file__)))
        self.assertEqual(result.returncode, 0,
                         result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()


class FinalFixTests(GuiTestCase):
    """终审修复轮回归（Critical 1 / Important 2/7 / Minor 升级项 8/9）。"""

    def make(self, seed=7, debounce=None):
        app = make_app(self.root, seed)
        if debounce is not None:
            app._action_debounce = debounce
        return app

    def finish_combat(self, app):
        g = app.game
        for e in g.active.enemies:
            e.hp = 0
        g.active.status = 'win'
        g.combat_finished()
        while g.pending is not None:
            if g.pending['relic_choices']:
                g.skip_relic()
            else:
                g.skip_card()
        app.show_screen()

    def test_second_combat_renders(self):
        # Critical 1：同一 app 连续两场战斗，第二场必须可玩
        app = self.make()
        to_combat(app, enemies=['goblin'])
        self.finish_combat(app)
        nxt = app.game.choices()[0]
        app.game.go(nxt)
        while app.game.map.nodes[nxt].kind not in ('combat', 'elite', 'boss'):
            app.game.enter()
            app.game.node_done = True
            app.game.go(app.game.choices()[0])
            nxt = app.game.current
        app.game.enter()
        app.show_screen()
        self.assertTrue(app.game.active is not None)
        self.assertGreater(len(app.hand_buttons), 0)

    def test_replay_first_combat_renders(self):
        # Critical 1 变体：start_run 重置后新局首场战斗（模拟重开路径）
        app = self.make()
        to_combat(app, enemies=['goblin'])
        self.finish_combat(app)
        app.start_run(99)
        to_combat(app, enemies=['wolf'])
        self.assertGreater(len(app.hand_buttons), 0)

    def test_end_turn_clears_targeting(self):
        app = self.make()
        combat = to_combat(app, enemies=['goblin', 'wolf'],
                           hand=['strike', 'defend', 'defend'])
        app.hand_buttons[0].invoke()
        self.assertEqual(app._pending_card, 0)
        app.end_btn.invoke()
        self.assertIsNone(app._pending_card)
        hp0 = combat.enemies[0].hp
        app._on_enemy(0)  # 不应误打新回合的牌
        self.assertEqual(combat.enemies[0].hp, hp0)

    def test_card_play_clears_potion_pending(self):
        app = self.make()
        combat = to_combat(app, enemies=['goblin', 'wolf'],
                           hand=['defend', 'defend'])
        app.game.hero.potions = ['p_acid']
        app.show_combat()
        app.potion_buttons[0].invoke()
        self.assertEqual(app._pending_potion, 0)
        app.hand_buttons[0].invoke()  # defend 直接打出
        self.assertIsNone(app._pending_potion)

    def test_double_click_debounced(self):
        app = self.make(debounce=0.2)
        combat = to_combat(app, enemies=['goblin'])
        turn0 = combat.turn
        app.end_btn.invoke()
        app.end_btn.invoke()
        self.assertEqual(combat.turn, turn0 + 1)

    def test_start_run_resets_screen_modes(self):
        app = self.make()
        app._camp_forge_mode = True
        app._shop_remove_mode = True
        app.start_run(121)
        self.assertFalse(app._camp_forge_mode)
        self.assertFalse(app._shop_remove_mode)
