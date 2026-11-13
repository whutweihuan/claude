# -*- coding: utf-8 -*-
"""Tkinter 鼠标界面：一次一屏，点按钮完成全部操作。不含任何游戏规则。"""
import textwrap
import time
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

import core
import content
from ui import KIND_ICON, KIND_NAME, item_name

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
        _flow_layout(hf, self.hand_buttons, self.WINDOW_W - 140)
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
        self.log_text = ScrolledText(outer, height=7, width=58,
                                      wrap='word')
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

    # ---------- 火堆屏 ----------

    def show_campfire(self):
        g = self.game
        self._clear()
        self._update_status()
        outer = ttk.Frame(self.container)
        outer.pack(fill='both', expand=True, padx=12, pady=8)
        ttk.Label(outer, text='火堆噼啪作响。你可以做一件事。',
                  wraplength=900).pack(anchor='w')
        opts = g.campfire_options()
        row = ttk.Frame(outer)
        row.pack(pady=8)
        self.sleep_btn = ttk.Button(row, text='睡一觉',
                                    command=self._camp_sleep)
        self.forge_btn = ttk.Button(row, text='锻造一张牌',
                                    command=self._camp_forge)
        self.sharpen_btn = ttk.Button(
            row, text='打磨武器（已用 %d/3）' % g.hero.weapon_sharpen,
            command=self._camp_sharpen)
        self.leave_btn = ttk.Button(row, text='什么也不做',
                                    command=self._camp_leave)
        for btn, o in zip((self.sleep_btn, self.forge_btn,
                           self.sharpen_btn), opts[:3]):
            btn.pack(side='left', padx=4)
            if not o['available']:
                btn.state(['disabled'])
        self.leave_btn.pack(side='left', padx=4)
        self.forge_card_buttons = {}
        if getattr(self, '_camp_forge_mode', False):
            grid = ttk.Frame(outer)
            grid.pack(pady=4)
            widgets = []
            for slot in opts[1]['cards']:
                cid, up = g.hero.deck[slot]
                card = content.CARDS[cid]
                btn = ttk.Button(
                    grid, text='%s\n%s' % (card.name, card.text),
                    command=lambda s=slot: self._camp_forge_pick(s))
                self.forge_card_buttons[slot] = btn
                widgets.append(btn)
            _flow_layout(grid, widgets, self.WINDOW_W - 140)
        msg = getattr(self, '_camp_msg', None)
        if msg:
            ttk.Label(outer, text=msg, wraplength=900).pack(anchor='w',
                                                             pady=4)
            self._camp_msg = None

    def _camp_after(self, lines):
        if self.game.node_done:
            self.show_map()
        else:
            self._camp_msg = ' '.join(lines)
            self.show_campfire()

    def _camp_sleep(self):
        self._camp_after(self.game.campfire('sleep'))

    def _camp_sharpen(self):
        self._camp_after(self.game.campfire('sharpen'))

    def _camp_leave(self):
        self._camp_after(self.game.campfire('leave'))

    def _camp_forge(self):
        self._camp_forge_mode = True
        self.show_campfire()

    def _camp_forge_pick(self, slot):
        self._camp_forge_mode = False
        self._camp_after(self.game.campfire('forge', slot))

    # ---------- 事件屏 ----------

    def show_event(self):
        g = self.game
        ev = g.node_obj
        self._clear()
        self._update_status()
        outer = ttk.Frame(self.container)
        outer.pack(fill='both', expand=True, padx=12, pady=8)
        ttk.Label(outer, text='【%s】' % ev.title,
                  font=('TkDefaultFont', 12)).pack(anchor='w')
        ttk.Label(outer, text=ev.text, wraplength=920,
                  justify='left').pack(anchor='w', pady=6)
        row = ttk.Frame(outer)
        row.pack(anchor='w', pady=4)
        self.event_option_buttons = []
        for i, opt in enumerate(ev.options):
            btn = ttk.Button(row, text=opt.label,
                             command=lambda idx=i: self._event_pick(idx))
            btn.pack(side='left', padx=4, pady=2)
            if not core.event_option_available(g, ev, i):
                btn.state(['disabled'])
            self.event_option_buttons.append(btn)
        msg = getattr(self, '_event_msg', None)
        if msg:
            ttk.Label(outer, text=msg, wraplength=900).pack(anchor='w')
            self._event_msg = None

    def _event_pick(self, idx):
        g = self.game
        lines, follow = core.apply_event(g, g.node_obj, idx)
        if follow is not None:
            g.start_event_combat(follow[1])
            self.show_screen()
        elif g.node_done:
            self.show_map()
        else:
            self._event_msg = ' '.join(lines)
            self.show_event()

    # ---------- 宝箱屏 ----------

    def show_chest(self):
        g = self.game
        loot = g.node_obj
        self._clear()
        self._update_status()
        outer = ttk.Frame(self.container)
        outer.pack(fill='both', expand=True, padx=12, pady=8)
        gear = (content.WEAPONS.get(loot['id'])
                or content.ARMORS.get(loot['id']))
        ttk.Label(outer,
                  text='宝箱里有 %d 金币，还有一件【%s】——\n%s'
                       % (loot['gold'], gear.name, gear.text),
                  wraplength=900).pack(anchor='w', pady=6)
        row = ttk.Frame(outer)
        row.pack(pady=6)
        self.equip_btn = ttk.Button(row, text='装备它',
                                    command=lambda: self._chest_take(True))
        self.gold_only_btn = ttk.Button(
            row, text='只拿金币走人',
            command=lambda: self._chest_take(False))
        self.equip_btn.pack(side='left', padx=4)
        self.gold_only_btn.pack(side='left', padx=4)

    def _chest_take(self, equip):
        self.game.take_chest(equip)
        self.show_map()

    # ---------- 奖励屏 ----------

    def show_rewards(self):
        g = self.game
        p = g.pending
        self._clear()
        self._update_status()
        outer = ttk.Frame(self.container)
        outer.pack(fill='both', expand=True, padx=12, pady=8)
        if p['lines']:
            ttk.Label(outer, text='  '.join(p['lines']),
                      wraplength=900).pack(anchor='w')
        self.relic_choice_buttons = []
        self.card_choice_buttons = []
        row = ttk.Frame(outer)
        row.pack(pady=6)
        if p['relic_choices']:
            ttk.Label(outer, text='战利品·遗物').pack(anchor='w')
            for i, rid in enumerate(p['relic_choices']):
                relic = content.RELICS[rid]
                btn = ttk.Button(row,
                                 text='%s\n%s' % (relic.name, relic.text),
                                 command=lambda idx=i: self._reward_relic(idx))
                btn.pack(side='left', padx=4)
                self.relic_choice_buttons.append(btn)
            self.skip_btn = ttk.Button(outer, text='不拿了',
                                       command=self._reward_skip)
        else:
            ttk.Label(outer,
                      text='战利品·卡牌（%d 选 1）' % len(p['card_choices'])
                      ).pack(anchor='w')
            for i, (cid, up) in enumerate(p['card_choices']):
                card = content.CARDS[cid]
                text = card.upgrade['text'] if up else card.text
                btn = ttk.Button(
                    row, text='%s%s\n%d费 %s' % (card.name,
                                                 '+' if up else '',
                                                 card.cost, text),
                    command=lambda idx=i: self._reward_card(idx))
                btn.pack(side='left', padx=4)
                self.card_choice_buttons.append(btn)
            self.skip_btn = ttk.Button(outer, text='跳过',
                                       command=self._reward_skip)
        self.skip_btn.pack(anchor='w', pady=6)

    def _reward_relic(self, i):
        self.game.choose_relic(i)
        self.show_map()

    def _reward_card(self, i):
        self.game.take_card(i)
        self.show_map()

    def _reward_skip(self):
        g = self.game
        if g.pending['relic_choices']:
            g.skip_relic()
        else:
            g.skip_card()
        self.show_map()

    # ---------- 商店屏 ----------

    def show_shop(self):
        g = self.game
        shop = g.shop
        self._clear()
        self._update_status()
        outer = ttk.Frame(self.container)
        outer.pack(fill='both', expand=True, padx=12, pady=8)
        ttk.Label(outer, text='“随便看，不还价。”',
                  wraplength=900).pack(anchor='w')
        row = ttk.Frame(outer)
        row.pack(pady=6)
        self.shop_slot_buttons = []
        for i, slot in enumerate(shop.slots):
            name = item_name(slot.kind, slot.content_id)
            if slot.sold:
                text = '%s\n已售罄' % name
            elif slot.price != slot.base_price:
                text = '%s\n原价%d → %d金币' % (name, slot.base_price,
                                              slot.price)
            else:
                text = '%s\n%d金币' % (name, slot.price)
            btn = ttk.Button(row, text=text,
                             command=lambda idx=i: self._shop_buy(idx))
            btn.grid(row=i // 4, column=i % 4, padx=3, pady=3,
                     sticky='nsew')
            if slot.sold or g.hero.gold < slot.price:
                btn.state(['disabled'])
            self.shop_slot_buttons.append(btn)
        self.remove_btn = ttk.Button(
            outer, text='删一张牌（%d 金币）' % shop.remove_cost,
            command=self._shop_remove_open)
        self.remove_btn.pack(anchor='w', pady=4)
        if g.hero.gold < shop.remove_cost:
            self.remove_btn.state(['disabled'])
        self.deck_card_buttons = {}
        if getattr(self, '_shop_remove_mode', False):
            grid = ttk.Frame(outer)
            grid.pack(pady=2)
            widgets = []
            for j, (cid, up) in enumerate(g.hero.deck):
                btn = ttk.Button(
                    grid, text='%s%s' % (content.CARDS[cid].name,
                                         '+' if up else ''),
                    command=lambda slot=j: self._shop_remove_pick(slot))
                self.deck_card_buttons[j] = btn
                widgets.append(btn)
            _flow_layout(grid, widgets, self.WINDOW_W - 140)
        msg = getattr(self, '_shop_msg', None)
        if msg:
            ttk.Label(outer, text=msg, wraplength=900).pack(anchor='w')
            self._shop_msg = None
        self.shop_close_btn = ttk.Button(outer, text='离开商店',
                                          command=self._shop_close)
        self.shop_close_btn.pack(anchor='w', pady=6)

    def _shop_buy(self, i):
        lines = core.buy(self.game, i)
        self._shop_msg = ' '.join(lines)
        self.show_shop()

    def _shop_remove_open(self):
        self._shop_remove_mode = True
        self.show_shop()

    def _shop_remove_pick(self, slot):
        lines = core.buy_removal(self.game, slot)
        self._shop_remove_mode = False
        self._shop_msg = ' '.join(lines)
        self.show_shop()

    def _shop_close(self):
        self.game.close_shop()
        self.show_map()

    # ---------- 结算屏 ----------

    def show_end(self):
        g = self.game
        if not self._finished_notified:
            self._finished_notified = True
            result = dict(g.stats)
            result['outcome'] = g.outcome
            self._last_finish_status = None
            if self.on_finish is not None:
                self._last_finish_status = self.on_finish(result)
        self._clear()
        outer = ttk.Frame(self.container)
        outer.pack(fill='both', expand=True, padx=12, pady=8)
        if g.outcome == 'win':
            ttk.Label(outer, text='*** 魔王倒下了。山道尽头透出晨光。***',
                      font=('TkDefaultFont', 14),
                      wraplength=900).pack(pady=8)
        else:
            ttk.Label(outer, text='你倒在了第 %d 层。传说还没有讲完。'
                      % g.depth_reached, wraplength=900).pack(pady=8)
        ttk.Label(outer,
                  text='深度 %d · 击杀 %d · 累计金币 %d · 种子 %s'
                       % (g.stats.get('depth', 0), g.stats.get('kills', 0),
                          g.stats.get('gold_earned', 0),
                          g.stats.get('seed'))).pack(pady=4)
        self.end_msg_var = tk.StringVar()
        if getattr(self, '_last_finish_status', None) == 'io_error':
            self.end_msg_var.set('战绩写入失败（原文件未被破坏）。')
        ttk.Label(outer, textvariable=self.end_msg_var,
                  wraplength=900).pack(pady=2)
        row = ttk.Frame(outer)
        row.pack(pady=10)
        self.replay_btn = ttk.Button(row, text='再来一局（新地图）',
                                     command=self._replay)
        self.leave_app_btn = ttk.Button(row, text='离开山道',
                                        command=self.root.destroy)
        self.replay_btn.pack(side='left', padx=6)
        self.leave_app_btn.pack(side='left', padx=6)

    def _replay(self):
        seed = int(time.time_ns() % 1000000)
        self.start_run(seed)
