# -*- coding: utf-8 -*-
"""奶牛牧场桌面版（tkinter）。运行: python cow_gui.py"""

import math
import random
import time
import tkinter as tk
from pathlib import Path
from typing import Dict, List, Tuple

from cow_core import (
    CALF_PRICE, CAPACITY_PRICES, CHEESE_MILK_COST, CHEESE_PRICE, CHEESE_TIME,
    COW_SELL_PRICES, FEED_COOLDOWN, FEED_CREDIT, FEED_MAX, FEED_PRICE,
    GROWTH_YOUNG, INITIAL_CAPACITY, MAX_CAPACITY, MAX_MACHINES, MACHINE_PRICES,
    MILK_INTERVAL, MILK_PRICE, SaveUnreadableError, adult_at, free_slot_left,
    load_state, new_game, ready_at, save_state, stage_of, udder_ready,
)

BG = "#F6F1E7"
HEADER_BG = "#E9DFC9"
CARD_BG = "#EFE6D6"
WAREHOUSE_BG = "#F3ECDD"
GRASS = "#7FB069"
GRASS_TOP = "#93C07A"
GRASS_BOTTOM = "#6A9A54"
GRASS_DARK = "#6E9E58"
FENCE = "#F4F1EA"
TEXT = "#3F3327"
MUTED = "#8A7A66"
GREEN = "#4F8F3F"
HIGHLIGHT = "#E2A33B"
COW_WHITE = "#F4F1EA"
COW_BLACK = "#3A3A3A"
COW_NOSE = "#E3AEB4"
COW_UDDE = "#F4C6CC"
HEART_PINK = "#E87FA0"
MILK_WHITE = "#FFFFFF"

FONT = ("Microsoft YaHei UI", 10)
FONT_SMALL = ("Microsoft YaHei UI", 9)
FONT_BOLD = ("Microsoft YaHei UI", 11, "bold")
FONT_TITLE = ("Microsoft YaHei UI", 14, "bold")

STAGE_LABELS = {"calf": "牛仔", "young": "青年牛", "adult": "成年牛"}


def format_remaining(seconds: float) -> str:
    """把剩余秒数格式化成 MM:SS 或 H:MM:SS。"""
    total = max(0, int(seconds + 0.999))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return "{}:{:02d}:{:02d}".format(hours, minutes, secs)
    return "{:02d}:{:02d}".format(minutes, secs)


def _mix(color1: str, color2: str, ratio: float) -> str:
    """两个 #RRGGBB 按比例线性插值。"""
    out = []
    for i in (1, 3, 5):
        a = int(color1[i:i + 2], 16)
        b = int(color2[i:i + 2], 16)
        out.append("{:02X}".format(int(round(a + (b - a) * ratio))))
    return "#" + "".join(out)


class PastureCanvas(tk.Canvas):
    WIDTH = 760
    HEIGHT = 460

    def __init__(self, master):
        super().__init__(
            master, width=self.WIDTH, height=self.HEIGHT, bg=GRASS,
            highlightthickness=2, highlightbackground=FENCE, cursor="hand2",
        )
        self._draw_scenery()

    def texts(self) -> List[str]:
        result = []
        for item in self.find_all():
            if self.type(item) == "text":
                result.append(self.itemcget(item, "text"))
        return result

    def show_float(self, text: str, x: float, y: float):
        item = self.create_text(
            x, y, text=text, fill="#B5651D",
            font=("Microsoft YaHei UI", 12, "bold"), tags=("float",),
        )

        def remove():
            try:
                self.delete(item)
            except tk.TclError:
                pass

        self.after(1000, remove)

    def _draw_scenery(self):
        bands = 12
        step = self.HEIGHT / bands
        for i in range(bands):
            self.create_rectangle(
                2, i * step, self.WIDTH - 2, (i + 1) * step,
                fill=_mix(GRASS_TOP, GRASS_BOTTOM, i / (bands - 1)),
                outline="", tags=("scenery",),
            )
        for band in ((60, 74), (170, 182), (300, 314), (400, 410)):
            self.create_rectangle(
                2, band[0], self.WIDTH - 2, band[1],
                fill=GRASS_DARK, outline="", tags=("scenery",),
            )

    def render(self, state, now: float, positions: Dict[int, Tuple[float, float]],
               facings=None):
        self.delete("cow")
        facings = facings or {}
        for cow in state.cows:
            x, y = positions.get(cow.id, (40.0, 40.0))
            self._draw_cow(cow, x, y, stage_of(cow, now), cow.pregnant,
                           udder_ready(cow, now), facings.get(cow.id, 1))

    @staticmethod
    def _box(cx, cy, w, h, cut):
        """带切角的长方体轮廓点（配合 smooth 得到圆角矩形）。"""
        return [
            cx - w / 2 + cut, cy - h / 2, cx + w / 2 - cut, cy - h / 2,
            cx + w / 2, cy - h / 2 + cut, cx + w / 2, cy + h / 2 - cut,
            cx + w / 2 - cut, cy + h / 2, cx - w / 2 + cut, cy + h / 2,
            cx - w / 2, cy + h / 2 - cut, cx - w / 2, cy - h / 2 + cut,
        ]

    def _draw_cow(self, cow, x: float, y: float, stage: str,
                  pregnant: bool, full: bool, facing: int = 1):
        """侧视奶牛：平背平腹的长方形躯干、方头带鼻吻、直立四肢带蹄、尾梢。"""
        scale = {"calf": 0.55, "young": 0.75, "adult": 1.0}[stage]
        tags = ("cow", "cow-{}".format(cow.id))
        bw, bh = 58.0 * scale, 30.0 * scale
        if pregnant:
            bh *= 1.08  # 孕期身体略圆（规格 §7.2）
        cut = 8.0 * scale
        leg_h = 12.0 * scale

        def px(lx: float) -> float:
            return x + lx * facing

        # 后腿（先画，乳房随后叠在其上）
        for fx in (-0.30, -0.15):
            a, b = sorted((px(fx * bw - 2.6 * scale), px(fx * bw + 2.6 * scale)))
            self.create_rectangle(a, y + bh / 2 - 4 * scale, b,
                                  y + bh / 2 + leg_h, fill=COW_WHITE,
                                  outline=COW_BLACK, tags=tags)
            self.create_rectangle(a, y + bh / 2 + leg_h - 3 * scale, b,
                                  y + bh / 2 + leg_h, fill=COW_BLACK,
                                  outline="", tags=tags)
        # 乳房（仅成年牛）
        if stage == "adult":
            a, b = sorted((px(0.02 * bw), px(0.18 * bw)))
            self.create_oval(a, y + bh * 0.40, b, y + bh * 0.64,
                             fill=COW_UDDE, outline="#D69A9A", tags=tags)
        # 前腿
        for fx in (0.18, 0.33):
            a, b = sorted((px(fx * bw - 2.6 * scale), px(fx * bw + 2.6 * scale)))
            self.create_rectangle(a, y + bh / 2 - 4 * scale, b,
                                  y + bh / 2 + leg_h, fill=COW_WHITE,
                                  outline=COW_BLACK, tags=tags)
            self.create_rectangle(a, y + bh / 2 + leg_h - 3 * scale, b,
                                  y + bh / 2 + leg_h, fill=COW_BLACK,
                                  outline="", tags=tags)
        # 躯干：平背平腹、切角圆角的长方形
        self.create_polygon(self._box(x, y, bw, bh, cut), smooth=True,
                            fill=COW_WHITE, outline=COW_BLACK, width=2, tags=tags)
        # 黑白花斑（按 id 三种排布，全部落在躯干轮廓内）
        variant = cow.id % 3
        if variant == 0:
            a, b = sorted((px(-0.28 * bw), px(0.02 * bw)))
            self.create_oval(a, y - 0.40 * bh, b, y + 0.02 * bh,
                             fill=COW_BLACK, outline="", tags=tags)
            a, b = sorted((px(0.10 * bw), px(0.36 * bw)))
            self.create_oval(a, y + 0.04 * bh, b, y + 0.38 * bh,
                             fill=COW_BLACK, outline="", tags=tags)
        elif variant == 1:
            a, b = sorted((px(-0.40 * bw), px(-0.14 * bw)))
            self.create_oval(a, y - 0.26 * bh, b, y + 0.10 * bh,
                             fill=COW_BLACK, outline="", tags=tags)
            a, b = sorted((px(0.08 * bw), px(0.38 * bw)))
            self.create_oval(a, y - 0.40 * bh, b, y - 0.06 * bh,
                             fill=COW_BLACK, outline="", tags=tags)
        else:
            a, b = sorted((px(-0.14 * bw), px(0.14 * bw)))
            self.create_oval(a, y - 0.40 * bh, b, y + 0.16 * bh,
                             fill=COW_BLACK, outline="", tags=tags)
            a, b = sorted((px(0.24 * bw), px(0.42 * bw)))
            self.create_oval(a, y + 0.02 * bh, b, y + 0.34 * bh,
                             fill=COW_BLACK, outline="", tags=tags)
        # 尾巴：沿臀部下垂带毛梢
        tx0 = px(-bw / 2 + 1.5 * scale)
        self.create_line(tx0, y - bh * 0.30, px(-bw / 2 - 2 * scale), y + bh * 0.12,
                         px(-bw / 2 - 1 * scale), y + bh * 0.38,
                         fill=COW_BLACK, width=max(1, int(2.2 * scale)), tags=tags)
        ta, tb = sorted((px(-bw / 2 - 4.5 * scale), px(-bw / 2 + 0.5 * scale)))
        self.create_oval(ta, y + bh * 0.34, tb, y + bh * 0.58,
                         fill=COW_BLACK, outline="", tags=tags)
        # 头：方脸、宽鼻吻、耳朵平展
        hw, hh = 21.0 * scale, 25.0 * scale
        hx = px(bw / 2 + 8 * scale)
        hy = y - bh / 2 + 11 * scale
        self.create_polygon(self._box(hx, hy, hw, hh, 5 * scale), smooth=True,
                            fill=COW_WHITE, outline=COW_BLACK, width=2, tags=tags)
        mw, mh = 15.0 * scale, 11.0 * scale
        mx = px(bw / 2 + 14.0 * scale)
        my = hy + hh / 2 - mh / 2 - 1 * scale
        self.create_polygon(self._box(mx, my, mw, mh, 3 * scale), smooth=True,
                            fill=COW_NOSE, outline="#B7878C", width=1, tags=tags)
        for nx in (-3.6, 3.6):
            a, b = sorted((px(bw / 2 + 14.0 * scale + nx * scale) - 1.4 * scale,
                           px(bw / 2 + 14.0 * scale + nx * scale) + 1.4 * scale))
            self.create_oval(a, my + 1.5 * scale, b, my + 4.2 * scale,
                             fill=COW_BLACK, outline="", tags=tags)
        for ex in (-11.5, 11.5):
            a, b = sorted((px(bw / 2 + 8 * scale + ex * scale) - 4.5 * scale,
                           px(bw / 2 + 8 * scale + ex * scale) + 4.5 * scale))
            self.create_oval(a, hy - hh / 2 - 1 * scale, b, hy - hh / 2 + 3.5 * scale,
                             fill=COW_BLACK, outline="", tags=tags)
        ea, eb = sorted((px(bw / 2 + 11.5 * scale) - 1.8 * scale,
                         px(bw / 2 + 11.5 * scale) + 1.8 * scale))
        self.create_oval(ea, hy - 4 * scale, eb, hy - 0.5 * scale,
                         fill=COW_BLACK, outline="", tags=tags)
        # 标记与名字
        marker_y = y - bh / 2 - 22 * scale
        if pregnant:
            self._heart(px(-10 * scale), marker_y, scale)
        if full:
            self._drop(px(12 * scale), marker_y, scale)
        self.create_text(
            x, y + bh / 2 + leg_h + 4, text=cow.name, anchor="n",
            font=FONT_SMALL, fill="#2F4A24", tags=tags,
        )

    def _heart(self, cx: float, cy: float, scale: float):
        r = 4.5 * scale
        self.create_oval(cx - r, cy - r * 0.6, cx, cy + r * 0.5,
                         fill=HEART_PINK, outline="", tags=("cow",))
        self.create_oval(cx, cy - r * 0.6, cx + r, cy + r * 0.5,
                         fill=HEART_PINK, outline="", tags=("cow",))
        self.create_polygon(cx - r * 0.95, cy + r * 0.15, cx + r * 0.95, cy + r * 0.15,
                            cx, cy + r * 1.5, fill=HEART_PINK, outline="", tags=("cow",))

    def _drop(self, cx: float, cy: float, scale: float):
        r = 4.5 * scale
        self.create_oval(cx - r, cy, cx + r, cy + r * 2,
                         fill=MILK_WHITE, outline="#9A9A9A", tags=("cow",))
        self.create_polygon(cx, cy - r * 1.4, cx - r * 0.9, cy + r * 0.5,
                            cx + r * 0.9, cy + r * 0.5,
                            fill=MILK_WHITE, outline="#9A9A9A", tags=("cow",))


class CowApp(tk.Tk):
    WALK_X = (70.0, 690.0)
    WALK_Y = (90.0, 380.0)
    WALK_SPEEDS = {"calf": 32.0, "young": 26.0, "adult": 22.0}

    def __init__(self, save_path=None, start_loops: bool = True,
                 clock=time.time, anim_seed: int = 0):
        super().__init__()
        self.clock = clock
        self._rng = random.Random(anim_seed)
        self._targets: Dict[int, Dict[str, float]] = {}
        self.save_path = Path(save_path) if save_path else (
            Path(__file__).resolve().parent / "save.json")
        self.title("奶牛牧场")
        self.geometry("1280x680")
        self.minsize(1260, 640)
        self.configure(bg=BG)
        self._readonly = False
        self._status_reset_id = None
        self.selected_id = None
        self.positions: Dict[int, Tuple[float, float]] = {}
        self.machine_rows: List = []
        self.load_error = None
        load_warning = None
        try:
            self.state, load_warning = load_state(self.save_path)
        except SaveUnreadableError as exc:
            self.state = new_game(self.clock())
            self._readonly = True
            self.load_error = str(exc)
        self.state.catch_up(self.clock())
        self._build_ui()
        self.refresh()
        if self.load_error:
            self.set_status(self.load_error, seconds=8)
        elif load_warning:
            self.set_status(load_warning, seconds=8)
        if not self._readonly:
            self._save()  # 规格 §8.2：离线结算成功后落盘一次，防崩溃重复结算
        if start_loops:
            self.after(1000, self._tick)
            self.after(10000, self._autosave)
            self.after(300, self._animate)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- 布局 ----------

    def _build_ui(self):
        header = tk.Frame(self, bg=HEADER_BG)
        header.pack(side="top", fill="x")
        self.coins_var = tk.StringVar()
        self.cows_var = tk.StringVar()
        self.ready_var = tk.StringVar()
        self.income_var = tk.StringVar()
        for var in (self.coins_var, self.cows_var, self.ready_var, self.income_var):
            tk.Label(header, textvariable=var, bg=HEADER_BG, fg=TEXT,
                     font=FONT_BOLD).pack(side="left", padx=12, pady=6)
        self.expand_label = tk.Label(header, text="已全部扩建", bg=HEADER_BG,
                                     fg=MUTED, font=FONT_BOLD)
        self.expand_button = tk.Button(
            header, font=FONT, bd=0, relief="flat", bg="#DCEBD7",
            activebackground="#C9DFC2", disabledforeground="#B0A897",
            command=self._on_expand_click)
        self.expand_button.pack(side="right", padx=12)

        status = tk.Frame(self, bg=CARD_BG)
        status.pack(side="bottom", fill="x")
        self.status_var = tk.StringVar(value="点一头上满奶的牛挤奶")
        tk.Label(status, textvariable=self.status_var, bg=CARD_BG, fg=MUTED,
                 font=FONT, anchor="w").pack(side="left", padx=12, pady=4,
                                             fill="x", expand=True)

        shop = tk.Frame(self, bg=HEADER_BG)
        shop.pack(side="bottom", fill="x")
        self.buy_calf_button = tk.Button(
            shop, font=FONT, bd=0, relief="flat", bg="#DCEBD7",
            disabledforeground="#B0A897", command=self._on_buy_calf_click)
        self.buy_calf_button.pack(side="left", padx=8, pady=4)
        self.buy_feed_button = tk.Button(
            shop, font=FONT, bd=0, relief="flat", bg="#DCEBD7",
            disabledforeground="#B0A897", command=self._on_buy_feed_click)
        self.buy_feed_button.pack(side="left", padx=8)
        self.buy_machine_button = tk.Button(
            shop, font=FONT, bd=0, relief="flat", bg="#DCEBD7",
            disabledforeground="#B0A897", command=self._on_buy_machine_click)
        self.buy_machine_button.pack(side="left", padx=8)
        self.process_all_button = tk.Button(
            shop, text="全部投料", font=FONT, bd=0, relief="flat", bg="#DCEBD7",
            disabledforeground="#B0A897", command=self._on_process_all_click)
        self.process_all_button.pack(side="right", padx=8)

        action = tk.Frame(self, bg=CARD_BG)
        action.pack(side="bottom", fill="x")
        self.action_var = tk.StringVar()
        tk.Label(action, textvariable=self.action_var, bg=CARD_BG, fg=TEXT,
                 font=FONT, anchor="w").pack(side="left", padx=12, pady=4,
                                             fill="x", expand=True)
        self.milk_button = tk.Button(
            action, text="挤奶", font=FONT, bd=0, relief="flat", bg="#DCEBD7",
            disabledforeground="#B0A897", command=self._on_milking_click)
        self.milk_button.pack(side="right", padx=8)
        self.feed_button = tk.Button(
            action, text="喂食", font=FONT, bd=0, relief="flat", bg="#DCEBD7",
            disabledforeground="#B0A897", command=self._on_feed_click)
        self.feed_button.pack(side="right", padx=8)
        self.sell_cow_button = tk.Button(
            action, text="卖牛", font=FONT, bd=0, relief="flat", bg="#F2D7C2",
            disabledforeground="#B0A897", command=self._on_sell_cow_click)
        self.sell_cow_button.pack(side="right", padx=8)

        main = tk.Frame(self, bg=BG)
        main.pack(side="top", fill="both", expand=True, padx=8, pady=4)
        warehouse = tk.Frame(main, bg=WAREHOUSE_BG, width=340)
        warehouse.pack(side="right", fill="y")
        warehouse.pack_propagate(False)
        self.warehouse_frame = warehouse
        tk.Label(warehouse, text="仓库", bg=WAREHOUSE_BG, fg=TEXT,
                 font=FONT_TITLE).pack(anchor="w", padx=12, pady=(10, 2))
        self.sell_buttons = {}
        self.warehouse_vars = {}
        for key, name, price in (("milk", "牛奶", MILK_PRICE),
                                 ("cheese", "奶酪", CHEESE_PRICE)):
            row = tk.Frame(warehouse, bg=WAREHOUSE_BG)
            row.pack(fill="x", padx=12, pady=4)
            var = tk.StringVar()
            self.warehouse_vars[key] = var
            tk.Label(row, textvariable=var, bg=WAREHOUSE_BG, fg=TEXT,
                     font=FONT).pack(side="left")
            button = tk.Button(
                row, text="卖出", font=FONT_SMALL, bd=0, relief="flat",
                bg="#DCEBD7", disabledforeground="#B0A897",
                command=lambda k=key: self._on_sell_click(k))
            button.pack(side="right")
            self.sell_buttons[key] = button
        tk.Label(warehouse, text="加工器", bg=WAREHOUSE_BG, fg=TEXT,
                 font=FONT_BOLD).pack(anchor="w", padx=12, pady=(10, 0))
        self.machine_frame = tk.Frame(warehouse, bg=WAREHOUSE_BG)
        self.machine_frame.pack(fill="x", padx=12, pady=2)
        self.sell_all_button = tk.Button(
            warehouse, text="全部卖出", font=FONT, bd=0, relief="flat",
            bg="#DCEBD7", disabledforeground="#B0A897",
            command=self._on_sell_all_click)
        self.sell_all_button.pack(side="bottom", fill="x", padx=12, pady=12)
        self.milk_all_button = tk.Button(
            warehouse, text="一键挤奶", font=FONT_BOLD, bd=0, relief="flat",
            bg="#BFDCAE", activebackground="#AECF9A",
            disabledforeground="#B0A897", command=self._on_milk_all_click)
        self.milk_all_button.pack(side="bottom", fill="x", padx=12, pady=(0, 4))

        farm_area = tk.Frame(main, bg=BG)
        farm_area.pack(side="left", fill="both", expand=True)
        self.pasture = PastureCanvas(farm_area)
        self.pasture.pack()
        self.pasture.bind("<Button-1>", self._on_pasture_click)

    # ---------- 刷新 ----------

    def refresh(self):
        now = self.clock()
        self.state.catch_up(now)
        ready = sum(1 for c in self.state.cows if udder_ready(c, now))
        self._update_header(ready, now)
        self._sync_positions()
        self.pasture.render(self.state, now, self.positions, self._facings())
        self._update_warehouse()
        self._update_action(now)
        self._update_shop()
        self._update_machines(now)
        title = "奶牛牧场"
        if ready:
            title = "奶牛牧场（{} 可挤）".format(ready)
        self.title(title)

    def _update_header(self, ready: int, now: float):
        self.coins_var.set("金币 {}".format(self.state.coins))
        preg = sum(1 for c in self.state.cows if c.pregnant)
        text = "牛 {}/{}".format(len(self.state.cows), self.state.capacity)
        if preg:
            text += "（孕{}）".format(preg)
        self.cows_var.set(text)
        self.ready_var.set("可挤奶 {}".format(ready))
        self.income_var.set("累计收入 {}".format(self.state.total_income))
        if self.state.capacity >= MAX_CAPACITY:
            self.expand_button.pack_forget()
            self.expand_label.pack(side="right", padx=12)
            return
        self.expand_label.pack_forget()
        self.expand_button.pack(side="right", padx=12)
        price = CAPACITY_PRICES[self.state.capacity - INITIAL_CAPACITY]
        if self.state.coins < price:
            self.expand_button.configure(text="金币不够", state="disabled")
        else:
            self.expand_button.configure(
                text="扩建牧场 {}".format(price), state="normal")

    def _sync_positions(self):
        alive = {c.id for c in self.state.cows}
        for cow_id in list(self.positions):
            if cow_id not in alive:
                del self.positions[cow_id]
                self._targets.pop(cow_id, None)
        for cow in self.state.cows:
            if cow.id not in self.positions:
                self.positions[cow.id] = self._initial_position(cow.id)
            if cow.id not in self._targets:
                tx, ty = self._random_target()
                self._targets[cow.id] = {"tx": tx, "ty": ty, "dwell": 0.0}

    def _initial_position(self, cow_id: int) -> Tuple[float, float]:
        return (90.0 + (cow_id * 173) % 570, 110.0 + (cow_id * 97) % 240)

    def _facings(self) -> Dict[int, int]:
        """朝向跟随当前行走目标；停留/无目标时保持朝右。"""
        facings = {}
        for cow in self.state.cows:
            motion = self._targets.get(cow.id)
            pos = self.positions.get(cow.id)
            if motion is None or pos is None:
                facings[cow.id] = 1
            else:
                facings[cow.id] = 1 if motion["tx"] >= pos[0] else -1
        return facings

    def _random_target(self) -> Tuple[float, float]:
        return (self._rng.uniform(*self.WALK_X), self._rng.uniform(*self.WALK_Y))

    # ---------- 走动动画（纯装饰：只读核心，不写状态、不进存档） ----------

    def _animate_step(self, dt: float):
        now = self.clock()
        for cow in self.state.cows:
            motion = self._targets.get(cow.id)
            if motion is None or cow.id not in self.positions:
                continue
            x, y = self.positions[cow.id]
            if motion["dwell"] > 0.0:
                motion["dwell"] -= dt
                if motion["dwell"] <= 0.0:
                    motion["tx"], motion["ty"] = self._random_target()
                continue
            dx = motion["tx"] - x
            dy = motion["ty"] - y
            dist = math.hypot(dx, dy)
            step = self.WALK_SPEEDS[stage_of(cow, now)] * dt
            if dist <= step or dist == 0.0:
                self.positions[cow.id] = (motion["tx"], motion["ty"])
                motion["dwell"] = self._rng.uniform(2.0, 8.0)
            else:
                self.positions[cow.id] = (x + dx / dist * step,
                                          y + dy / dist * step)
        self.pasture.render(self.state, now, self.positions, self._facings())

    def _animate(self):
        self._animate_step(0.3)
        self.after(300, self._animate)

    def _update_warehouse(self):
        for key, name, price in (("milk", "牛奶", MILK_PRICE),
                                 ("cheese", "奶酪", CHEESE_PRICE)):
            count = self.state.stock(key)
            self.warehouse_vars[key].set(
                "{} ×{}（{}/份）".format(name, count, price))
            self.sell_buttons[key].configure(
                state="normal" if count > 0 else "disabled")
        value = self.state.stock_value()
        self.sell_all_button.configure(
            text="全部卖出（{}）".format(value),
            state="normal" if value > 0 else "disabled")

    def _feed_disable_reason(self, cow, now: float):
        """置灰原因写进按钮文字（规格 §7.5）；None 表示可以喂。"""
        if stage_of(cow, now) == "adult":
            return "已成年"
        if cow.fed_count >= FEED_MAX:
            return "已喂满"
        if now - cow.last_fed_at < FEED_COOLDOWN:
            return "冷却中"
        if self.state.feed_count <= 0:
            return "无饲料"
        return None

    def _update_action(self, now: float):
        cow = None
        if self.selected_id is not None:
            cow = self.state.find_cow(self.selected_id)
            if cow is None:
                self.selected_id = None
        if cow is None:
            self.action_var.set("未选中任何牛，点一头试试")
            for button in (self.milk_button, self.feed_button, self.sell_cow_button):
                button.configure(state="disabled")
            return
        stage = stage_of(cow, now)
        parts = ["{}（{}）".format(cow.name, STAGE_LABELS[stage])]
        full = False
        if stage == "adult":
            if cow.pregnant:
                parts.append("怀孕 还需 {}".format(
                    format_remaining(cow.due_at - now)))
            elif cow.recovery_until > now:
                parts.append("产后休养 还需 {}".format(
                    format_remaining(cow.recovery_until - now)))
            elif ready_at(cow) <= now:
                if free_slot_left(self.state):
                    parts.append("可孕")
                else:
                    parts.append("可孕（等空位）")
            full = udder_ready(cow, now)
            if full:
                parts.append("满奶！")
            else:
                anchor = max(cow.last_milked_at, adult_at(cow))
                parts.append("下次挤奶 {}".format(
                    format_remaining(anchor + MILK_INTERVAL - now)))
        else:
            next_stage_at = adult_at(cow) if stage == "young" else (
                cow.born_at + GROWTH_YOUNG - cow.fed_count * FEED_CREDIT)
            parts.append("长大还需 {}".format(
                format_remaining(next_stage_at - now)))
        self.action_var.set("  ".join(parts))
        self.milk_button.configure(
            state="normal" if full else "disabled",
            bg="#F7E1A8" if full else "#DCEBD7")
        reason = self._feed_disable_reason(cow, now)
        if reason is None:
            self.feed_button.configure(
                text="喂食（背包 {} 份）".format(self.state.feed_count),
                state="normal")
        else:
            self.feed_button.configure(
                text="喂食（{}）".format(reason), state="disabled")
        self.sell_cow_button.configure(
            text="卖牛 {}".format(COW_SELL_PRICES[stage]), state="normal")

    def _update_shop(self):
        if not free_slot_left(self.state):
            self.buy_calf_button.configure(text="牧场满了", state="disabled")
        elif self.state.coins < CALF_PRICE:
            self.buy_calf_button.configure(text="金币不够", state="disabled")
        else:
            self.buy_calf_button.configure(
                text="买牛仔 {}".format(CALF_PRICE), state="normal")
        if self.state.coins < FEED_PRICE:
            self.buy_feed_button.configure(text="金币不够", state="disabled")
        else:
            self.buy_feed_button.configure(
                text="高级饲料 {}（背包 {}）".format(
                    FEED_PRICE, self.state.feed_count), state="normal")
        if len(self.state.machines) >= MAX_MACHINES:
            self.buy_machine_button.configure(text="加工器已达上限",
                                              state="disabled")
        else:
            price = MACHINE_PRICES[len(self.state.machines)]
            if self.state.coins < price:
                self.buy_machine_button.configure(text="金币不够",
                                                  state="disabled")
            else:
                self.buy_machine_button.configure(
                    text="买加工器 {}".format(price), state="normal")

    def _update_machines(self, now: float):
        if len(self.machine_rows) != len(self.state.machines):
            for child in self.machine_frame.winfo_children():
                child.destroy()
            self.machine_rows = []
            for index in range(len(self.state.machines)):
                row = tk.Frame(self.machine_frame, bg=WAREHOUSE_BG)
                row.pack(fill="x", pady=1)
                var = tk.StringVar()
                tk.Label(row, textvariable=var, bg=WAREHOUSE_BG, fg=TEXT,
                         font=FONT_SMALL).pack(side="left")
                # 行内左状态右按钮；340px 面板内长文案留给标签，按钮保持短
                button = tk.Button(
                    row, text="投料", font=FONT_SMALL, bd=0, relief="flat",
                    bg="#DCEBD7", disabledforeground="#B0A897",
                    command=lambda i=index: self._on_process_click(i))
                button.pack(side="right")
                self.machine_rows.append((var, button))
        self.process_all_button.configure(
            state="normal" if self.state.machines else "disabled")
        for index, started in enumerate(self.state.machines):
            var, button = self.machine_rows[index]
            if started is None:
                var.set("#{} 空闲（3奶→1酪）".format(index + 1))
                button.configure(
                    state="normal"
                    if self.state.stock("milk") >= CHEESE_MILK_COST else "disabled")
            else:
                done = min(1.0, max(0.0, (now - started) / CHEESE_TIME))
                blocks = "▓" * int(done * 6 + 0.5) + "░" * (
                    6 - int(done * 6 + 0.5))
                var.set("#{} {} {}".format(
                    index + 1, blocks,
                    format_remaining(started + CHEESE_TIME - now)))
                button.configure(state="disabled")

    # ---------- 状态栏 ----------

    def set_status(self, text: str, seconds: int = 3):
        self.status_var.set(text)
        if self._status_reset_id is not None:
            self.after_cancel(self._status_reset_id)

        def reset():
            self._status_reset_id = None
            self.status_var.set("点一头上满奶的牛挤奶")

        self._status_reset_id = self.after(seconds * 1000, reset)

    # ---------- 事件入口 ----------

    def _on_pasture_click(self, event):
        items = self.pasture.find_overlapping(
            event.x - 1, event.y - 1, event.x + 1, event.y + 1)
        for item in items:
            for tag in self.pasture.gettags(item):
                if isinstance(tag, str) and tag.startswith("cow-"):
                    self._on_cow_click(int(tag[4:]))
                    return
        self.selected_id = None
        self.refresh()

    def _on_cow_click(self, cow_id: int):
        now = self.clock()
        cow = self.state.find_cow(cow_id)
        if cow is None:
            return
        if udder_ready(cow, now):
            self._do_milk(cow, now)
        else:
            self.selected_id = cow_id
            self.refresh()

    def _do_milk(self, cow, now: float):
        try:
            self.state.milk(cow.id, now)
        except ValueError as exc:
            self.set_status(str(exc))
            self.refresh()
            return
        x, y = self.positions.get(cow.id, (40.0, 40.0))
        self.pasture.show_float("+1 牛奶", x, y - 34)
        self.set_status("挤了 {} 一瓶奶".format(cow.name))
        self._save()
        self.refresh()

    def _on_milking_click(self):
        if self.selected_id is None:
            return
        cow = self.state.find_cow(self.selected_id)
        if cow is not None:
            self._do_milk(cow, self.clock())

    def _on_milk_all_click(self):
        milked = self.state.milk_all(self.clock())
        if milked:
            self.set_status("一键挤奶 {} 头，牛奶 +{}".format(milked, milked))
            self._save()
        else:
            self.set_status("没有蓄满奶的牛")
        self.refresh()

    def _on_feed_click(self):
        if self.selected_id is None:
            return
        cow = self.state.find_cow(self.selected_id)
        if cow is None:
            return
        try:
            self.state.feed(cow.id, self.clock())
        except ValueError as exc:
            self.set_status(str(exc))
        else:
            self.set_status("喂了 {} 一份高级饲料".format(cow.name))
            self._save()
        self.refresh()

    def _on_sell_cow_click(self):
        if self.selected_id is None:
            return
        cow = self.state.find_cow(self.selected_id)
        if cow is None:
            return
        was_pregnant = cow.pregnant
        try:
            got = self.state.sell_cow(cow.id, self.clock())
        except ValueError as exc:
            self.set_status(str(exc))
        else:
            self.selected_id = None
            if was_pregnant:
                self.set_status("卖出了 {}（连同腹中牛犊），+{} 金币".format(
                    cow.name, got), seconds=5)
            else:
                self.set_status("卖出了 {}，+{} 金币".format(cow.name, got))
            self._save()
        self.refresh()

    def _on_buy_calf_click(self):
        try:
            self.state.buy_calf(self.clock())
        except ValueError as exc:
            self.set_status(str(exc))
        else:
            self.set_status("买回一头牛仔")
            self._save()
        self.refresh()

    def _on_buy_feed_click(self):
        try:
            count = self.state.buy_feed()
        except ValueError as exc:
            self.set_status(str(exc))
        else:
            self.set_status("购入高级饲料，背包 {} 份".format(count))
            self._save()
        self.refresh()

    def _on_buy_machine_click(self):
        try:
            self.state.buy_machine()
        except ValueError as exc:
            self.set_status(str(exc))
        else:
            self.set_status("购入加工器 #{}".format(len(self.state.machines)))
            self._save()
        self.refresh()

    def _on_expand_click(self):
        try:
            self.state.expand_capacity()
        except ValueError as exc:
            self.set_status(str(exc))
        else:
            self.set_status("牧场扩建到 {} 个位置".format(self.state.capacity))
            self._save()
        self.refresh()

    def _on_process_click(self, index: int):
        try:
            self.state.process(index, self.clock())
        except ValueError as exc:
            self.set_status(str(exc))
        else:
            self.set_status("投料成功，{} 分钟后出奶酪".format(CHEESE_TIME // 60))
            self._save()
        self.refresh()

    def _on_process_all_click(self):
        started = self.state.process_all(self.clock())
        if started:
            self.set_status("启动了 {} 台加工器".format(started))
            self._save()
        else:
            self.set_status("没有可投料的加工器（需空闲且库存 ≥ {} 牛奶）".format(
                CHEESE_MILK_COST))
        self.refresh()

    def _on_sell_click(self, item: str):
        name = {"milk": "牛奶", "cheese": "奶酪"}[item]
        count = self.state.stock(item)
        if count <= 0:
            self.set_status("仓库没有{}".format(name))
            return
        got = self.state.sell_stock(item)
        self.set_status("卖出{} ×{}，+{} 金币".format(name, count, got))
        self._save()
        self.refresh()

    def _on_sell_all_click(self):
        total = self.state.sell_all_stock()
        if total:
            self.set_status("全部卖出，+{} 金币".format(total))
            self._save()
        else:
            self.set_status("仓库是空的")
        self.refresh()

    # ---------- 保存与循环 ----------

    def _save(self):
        if self._readonly:
            return
        try:
            save_state(self.state, self.save_path)
        except OSError as exc:
            self.set_status("保存失败：{}".format(exc))

    def _on_close(self):
        self._save()
        self.destroy()

    def _tick(self):
        self.refresh()
        self.after(1000, self._tick)

    def _autosave(self):
        self._save()
        self.after(10000, self._autosave)


def _enable_dpi_awareness():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def main():
    _enable_dpi_awareness()
    app = CowApp()
    app.mainloop()


if __name__ == "__main__":
    main()
