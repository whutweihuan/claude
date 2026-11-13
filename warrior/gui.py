# -*- coding: utf-8 -*-
"""Tkinter 鼠标界面：一次一屏，点按钮完成全部操作。不含任何游戏规则。"""
import time
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

import core
import content
from ui import KIND_ICON, KIND_NAME

WRAP_PX = 170


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

    def show_combat(self):
        self._placeholder('战斗屏（待实装）')

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
