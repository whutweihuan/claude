# -*- coding: utf-8 -*-
"""Tkinter 鼠标界面：一次一屏，点按钮完成全部操作。不含任何游戏规则。"""
import textwrap
import time
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

import core
import content
from ui import KIND_ICON, KIND_NAME

WRAP_PX = 170
SINGLE_TARGET_OPS = ('damage', 'pierce', 'execute', 'vulnerable', 'poison',
                     'bonus_if_vulnerable')


def _enable_dpi_awareness():
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except AttributeError:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _flow_layout(container, widgets, max_width):
    """自然宽度流式排布：按行装入 grid，返回行列表。"""
    for w in widgets:
        w.update_idletasks()
    rows = []
    row = []
    used = 0
    for w in widgets:
        need = w.winfo_reqwidth() + 4
        if row and used + need > max_width:
            rows.append(row)
            row = []
            used = 0
        row.append(w)
        used += need
    if row:
        rows.append(row)
    for r, group in enumerate(rows):
        for c, w in enumerate(group):
            w.grid(row=r, column=c, padx=2, pady=2, sticky='nsew')
        container.grid_columnconfigure(c, weight=1)
    return rows


class WarriorGUI(object):
    WINDOW_W = 1000
    WINDOW_H = 660

    def __init__(self, root, on_finish=None):
        self.root = root
        self.on_finish = on_finish
        self.game = None
        self._finished_notified = False
        self._pending_card = None
        self._pending_potion = None
        root.title('勇士冒险')
        root.geometry('%dx%d' % (self.WINDOW_W, self.WINDOW_H))
        root.minsize(900, 620)
        self.top = ttk.Frame(root)
        self.top.pack(side='top', fill='x')
        self.status_var = tk.StringVar(value='勇士冒险 · 纯鼠标 Roguelike')
        ttk.Label(self.top, textvariable=self.status_var).pack(side='left',
                                                                padx=8, pady=4)
        self.container = ttk.Frame(root)
        self.container.pack(fill='both', expand=True)
        root.protocol('WM_DELETE_WINDOW', self._on_close)

    # ---------- 基础 ----------

    def run(self):
        self.show_title()
        self.root.mainloop()

    def _on_close(self):
        self.root.destroy()

    def _clear(self):
        for child in self.container.winfo_children():
            child.destroy()

    def _update_status(self):
        if self.game is None:
            return
        hero = self.game.hero
        armor = (content.ARMORS[hero.armor].name if hero.armor else '无')
        self.status_var.set(
            '生命 %d/%d  金币 %d  武器【%s%s】 防具【%s】 遗物 %d 药水 %d/3'
            % (hero.hp, hero.max_hp, hero.gold,
               content.WEAPONS[hero.weapon].name,
               '+%d' % hero.weapon_sharpen if hero.weapon_sharpen else '',
               armor, len(hero.relics), len(hero.potions)))

    # ---------- 屏幕分发 ----------

    def show_screen(self):
        g = self.game
        if g.finished:
            self.show_end()
            return
        if g.pending is not None:
            self.show_rewards()
            return
        if g.active is not None:
            self.show_combat()
            return
        if g.current is None or g.node_done:
            self.show_map()
            return
        kind = g.map.nodes[g.current].kind
        if kind == 'campfire':
            self.show_campfire()
        elif kind == 'event':
            self.show_event()
        elif kind == 'shop':
            self.show_shop()
        elif kind == 'chest':
            self.show_chest()
        else:
            self.show_map()

    # ---------- 标题屏 ----------

    def show_title(self):
        self._clear()
        frame = ttk.Frame(self.container)
        frame.pack(expand=True)
        ttk.Label(frame, text='勇 士 冒 险',
                  font=('TkDefaultFont', 18)).pack(pady=8)
        ttk.Label(frame, text='打倒顶层的魔王。全程只用鼠标。').pack()
        ttk.Label(frame, text='输入随机种子（留空 = 随机）：').pack(pady=(8, 2))
        self.seed_entry = ttk.Entry(frame, width=16)
        self.seed_entry.pack(pady=2)
        self.start_btn = ttk.Button(frame, text='开始冒险',
                                    command=self._on_start)
        self.start_btn.pack(pady=10)

    def _on_start(self):
        import main as main_mod
        raw = self.seed_entry.get().strip()
        seed = main_mod.parse_seed(raw)
        if seed is None:
            seed = time.time_ns() % 1000000
        self.start_run(seed)

    def start_run(self, seed):
        self.game = core.Run(seed)
        self._finished_notified = False
        self._pending_card = None
        self._pending_potion = None
        self._combat_log = []
        self.show_map()

    # ---------- 地图屏 ----------

    def show_map(self):
        self._clear()
        self._update_status()
        g = self.game
        grid = ttk.Frame(self.container)
        grid.pack(fill='both', expand=True, padx=8, pady=4)
        layers = {}
        for node in g.map.nodes.values():
            layers.setdefault(node.layer, []).append(node)
        self.map_buttons = {}
        choices = set(g.choices())
        for r, layer in enumerate(sorted(layers, reverse=True)):
            rowf = ttk.Frame(grid)
            rowf.grid(row=r, column=0, sticky='w', pady=1)
            ttk.Label(rowf, text='L%-2d' % layer).pack(side='left', padx=4)
            for node in sorted(layers[layer], key=lambda n: n.id):
                if node.id == g.current:
                    prefix = '▶'
                elif node.id in g.visited:
                    prefix = '✓'
                else:
                    prefix = ''
                btn = ttk.Button(
                    rowf, text='%s%s·%s' % (prefix, KIND_ICON[node.kind],
                                            KIND_NAME[node.kind]),
                    command=lambda nid=node.id: self._on_move(nid))
                btn.pack(side='left', padx=2)
                if node.id not in choices:
                    btn.state(['disabled'])
                self.map_buttons[node.id] = btn
        ttk.Label(grid, wraplength=940,
                  text='点击亮色节点前进。图例：战=战斗 精=精英 火=火堆 '
                       '事=事件 店=商店 宝=宝箱 魔=魔王').grid(
            row=len(layers), column=0, sticky='w', pady=6)

    def _on_move(self, nid):
        g = self.game
        if nid not in g.choices():
            return
        g.go(nid)
        g.enter()
        self.show_screen()

    # ---------- 其余屏（逐任务实装） ----------

    def _placeholder(self, text):
        self._clear()
        self._update_status()
        ttk.Label(self.container, text=text, wraplength=900).pack(
            expand=True)

    # ---------- 战斗屏 ----------

    def show_combat(self):
        g = self.game
        combat = g.active
        self._clear()
        self._update_status()
        outer = ttk.Frame(self.container)
        outer.pack(fill='both', expand=True, padx=8, pady=4)
        if getattr(self, '_logged_combat', None) is not combat:
            self._logged_combat = combat
            self._pending_card = None
            self._pending_potion = None
            self._combat_log = []
            self._log(['--- 遭遇 %s！---' % '、'.join(
                e.name for e in combat.enemies)])
        targeting = (self._pending_card is not None
                     or self._pending_potion is not None)
        snap = combat.snapshot()
        ttk.Label(outer, text='生命 %d/%d  格挡 %d  能量 %d  第 %d 回合'
                  % (snap['hp'], snap['max_hp'], snap['block'],
                     snap['energy'], snap['turn'])).pack(anchor='w')
        ef = ttk.Frame(outer)
        ef.pack(fill='x', pady=4)
        self.enemy_buttons = []
        for i, e in enumerate(snap['enemies']):
            if not e['alive']:
                continue
            extras = []
            if e['block']:
                extras.append('格挡%d' % e['block'])
            if e['vulnerable']:
                extras.append('易伤%d' % e['vulnerable'])
            if e['poison']:
                extras.append('毒%d' % e['poison'])
            f = ttk.Frame(ef)
            f.pack(side='left', padx=4)
            prefix = '◉ ' if targeting else ''
            btn = ttk.Button(
                f, text='%s%s\n%d/%d 意图:%s%s'
                       % (prefix, e['name'], e['hp'], e['max_hp'],
                          e['intent'] or '…',
                          (' ' + '/'.join(extras)) if extras else ''),
                command=lambda idx=i: self._on_enemy(idx))
            btn.pack()
            bar = tk.Canvas(f, width=110, height=10, highlightthickness=0)
            bar.pack(pady=(2, 0))
            self._draw_hp_bar(bar, e['hp'], e['max_hp'])
            self.enemy_buttons.append(btn)
        hf = ttk.Frame(outer)
        hf.pack(fill='x', pady=6)
        self.hand_buttons = []
        for card in snap['hand']:
            star = '+' if card['upgraded'] else ''
            body = '\n'.join(textwrap.wrap(card['text'], 12))
            btn = ttk.Button(
                hf,
                text='%s%s（%d费）\n%s' % (card['name'], star, card['cost'],
                                          body),
                command=lambda idx=card['idx']: self._on_card(idx))
            if not card['playable']:
                btn.state(['disabled'])
            self.hand_buttons.append(btn)
        _flow_layout(hf, self.hand_buttons, self.WINDOW_W - 80)
        af = ttk.Frame(outer)
        af.pack(fill='x', pady=2)
        self.end_btn = ttk.Button(af, text='结束回合',
                                  command=self._on_end_turn)
        self.end_btn.pack(side='left', padx=4)
        self.potion_buttons = []
        for slot, pid in enumerate(snap['potions']):
            pb = ttk.Button(af, text='药水·%s' % content.POTIONS[pid].name,
                            command=lambda s=slot: self._on_potion(s))
            pb.pack(side='left', padx=2)
            self.potion_buttons.append(pb)
        ttk.Button(af, text='详情', command=self._show_details).pack(
            side='left', padx=4)
        self.cancel_btn = ttk.Button(af, text='取消',
                                     command=self._cancel_targeting)
        if targeting:
            self.cancel_btn.pack(side='left', padx=4)
        self.log_text = ScrolledText(outer, height=7, wrap='word')
        self.log_text.pack(fill='x', pady=4)
        self._render_log()

    def _draw_hp_bar(self, canvas, hp, max_hp):
        canvas.delete('all')
        canvas.create_rectangle(0, 0, 110, 10, fill='#661a1a',
                                outline='')
        if hp > 0:
            w = int(110 * hp / max(1, max_hp))
            canvas.create_rectangle(0, 0, w, 10, fill='#2e8b57',
                                    outline='')

    # ---------- 战斗日志 ----------

    def _render_log(self):
        self.log_text.configure(state='normal')
        self.log_text.delete('1.0', 'end')
        for line in self._combat_log[-120:]:
            self.log_text.insert('end', line + '\n')
        self.log_text.see('end')
        self.log_text.configure(state='disabled')

    def _log(self, lines):
        if not hasattr(self, '_combat_log'):
            self._combat_log = []
        self._combat_log.extend(lines)
        if hasattr(self, 'log_text'):
            self._render_log()

    # ---------- 战斗动作 ----------

    def _needs_target(self, card_id, upgraded, combat):
        if sum(1 for e in combat.enemies if e.alive) <= 1:
            return False
        effects, _text = combat.effects_for(card_id, upgraded)
        return any(eff[0] in SINGLE_TARGET_OPS for eff in effects)

    def _on_card(self, idx):
        combat = self.game.active
        if combat is None or combat.status != 'playing':
            return
        snap = combat.snapshot()
        if not (0 <= idx < len(snap['hand'])) \
                or not snap['hand'][idx]['playable']:
            return
        if self._pending_card == idx:
            self._pending_card = None
            self.show_combat()
            return
        card_id, upgraded = combat.hand[idx]
        if self._needs_target(card_id, upgraded, combat):
            self._pending_card = idx
            self._pending_potion = None
            self.show_combat()
            return
        self._pending_card = None
        lines = combat.play_card(idx, None)
        self._after_action(lines)

    def _on_enemy(self, idx):
        combat = self.game.active
        if combat is None or combat.status != 'playing':
            return
        if self._pending_card is not None:
            card_idx = self._pending_card
            self._pending_card = None
            lines = combat.play_card(card_idx, idx)
            self._after_action(lines)
        elif self._pending_potion is not None:
            slot = self._pending_potion
            self._pending_potion = None
            lines = combat.use_potion(slot, idx)
            self._after_action(lines)

    def _on_potion(self, slot):
        combat = self.game.active
        if combat is None or combat.status != 'playing':
            return
        if not (0 <= slot < len(combat.hero.potions)):
            return
        pid = combat.hero.potions[slot]
        if content.POTIONS[pid].targeted \
                and sum(1 for e in combat.enemies if e.alive) > 1:
            self._pending_potion = slot
            self._pending_card = None
            self.show_combat()
            return
        self._pending_potion = None
        lines = combat.use_potion(slot, None)
        self._after_action(lines)

    def _on_end_turn(self):
        combat = self.game.active
        if combat is None or combat.status != 'playing':
            return
        lines = combat.end_turn()
        self._after_action(lines)

    def _cancel_targeting(self):
        self._pending_card = None
        self._pending_potion = None
        if self.game.active is not None:
            self.show_combat()

    def _after_action(self, lines):
        self._log(lines)
        combat = self.game.active
        if combat.status != 'playing':
            if combat.status == 'win':
                self._log(['*** 战斗胜利！***'])
            else:
                self._log(['你倒下了……'])
            self.game.combat_finished()
            self.show_screen()
        else:
            self.show_combat()

    def _show_details(self):
        if self.game is None:
            return
        win = tk.Toplevel(self.root)
        win.title('行囊')
        text = ScrolledText(win, width=50, height=14, wrap='word')
        hero = self.game.hero
        text.insert('end', '武器：%s\n' % content.WEAPONS[hero.weapon].name)
        text.insert('end', '防具：%s\n' % (
            content.ARMORS[hero.armor].name if hero.armor else '无'))
        for rid in hero.relics:
            text.insert('end', '遗物：%s —— %s\n'
                        % (content.RELICS[rid].name,
                           content.RELICS[rid].text))
        counts = {}
        for cid, up in hero.deck:
            key = (cid, up)
            counts[key] = counts.get(key, 0) + 1
        text.insert('end', '卡组 %d 张：%s\n' % (
            len(hero.deck), '、'.join(
                '%s%s×%d' % (content.CARDS[cid].name, '+' if up else '', n)
                for (cid, up), n in sorted(counts.items()))))
        text.configure(state='disabled')
        text.pack(fill='both', expand=True)

    def show_rewards(self):
        self._placeholder('奖励屏（待实装）')

    def show_campfire(self):
        self._placeholder('火堆屏（待实装）')

    def show_event(self):
        self._placeholder('事件屏（待实装）')

    def show_shop(self):
        self._placeholder('商店屏（待实装）')

    def show_chest(self):
        self._placeholder('宝箱屏（待实装）')

    def show_end(self):
        self._placeholder('结算屏（待实装）')
