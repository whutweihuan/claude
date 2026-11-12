# -*- coding: utf-8 -*-
"""奶牛牧场桌面版（tkinter）。运行: python cow_gui.py"""

import time
import tkinter as tk
from pathlib import Path
from typing import Dict, List, Tuple

from cow_core import (
    CALF_PRICE, CAPACITY_PRICES, CHEESE_MILK_COST, CHEESE_PRICE, CHEESE_TIME,
    COW_SELL_PRICES, FEED_PRICE, GESTATION, MAX_CAPACITY, MAX_MACHINES,
    MACHINE_PRICES, MILK_INTERVAL, MILK_PRICE, POSTPARTUM, SaveUnreadableError,
    adult_at, free_slot_left, load_state, new_game, save_state, stage_of,
    udder_ready,
)

BG = "#F6F1E7"
HEADER_BG = "#E9DFC9"
CARD_BG = "#EFE6D6"
WAREHOUSE_BG = "#F3ECDD"
GRASS = "#7FB069"
GRASS_DARK = "#6E9E58"
FENCE = "#F4F1EA"
TEXT = "#3F3327"
MUTED = "#8A7A66"
GREEN = "#4F8F3F"
HIGHLIGHT = "#E2A33B"
COW_WHITE = "#F4F1EA"
COW_BLACK = "#3A3A3A"
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


def format_duration(seconds: int) -> str:
    if seconds % 3600 == 0:
        return "{}时".format(seconds // 3600)
    return "{}分".format(seconds // 60)


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
        for band in ((60, 74), (170, 182), (300, 314), (400, 410)):
            self.create_rectangle(
                2, band[0], self.WIDTH - 2, band[1],
                fill=GRASS_DARK, outline="", tags=("scenery",),
            )

    def render(self, state, now: float, positions: Dict[int, Tuple[float, float]]):
        self.delete("cow")
        for cow in state.cows:
            x, y = positions.get(cow.id, (40.0, 40.0))
            self._draw_cow(cow, x, y, stage_of(cow, now),
                           cow.pregnant, udder_ready(cow, now))

    def _draw_cow(self, cow, x: float, y: float, stage: str,
                  pregnant: bool, full: bool):
        scale = {"calf": 0.55, "young": 0.75, "adult": 1.0}[stage]
        tags = ("cow", "cow-{}".format(cow.id))
        bw, bh = 56 * scale, 26 * scale
        leg = 10 * scale
        for fx in (-0.30, -0.12, 0.12, 0.30):
            self.create_line(
                x + fx * bw, y + bh / 2, x + fx * bw, y + bh / 2 + leg,
                fill=COW_BLACK, width=max(1, int(2 * scale)), tags=tags,
            )
        self.create_line(
            x - bw / 2, y - bh * 0.15, x - bw / 2 - 7 * scale, y + bh * 0.35,
            fill=COW_BLACK, width=max(1, int(2 * scale)), tags=tags,
        )
        self.create_oval(
            x - bw / 2, y - bh / 2, x + bw / 2, y + bh / 2,
            fill=COW_WHITE, outline=COW_BLACK, width=2, tags=tags,
        )
        if cow.id % 2 == 0:
            self.create_oval(
                x - 0.30 * bw, y - 0.34 * bh, x - 0.02 * bw, y + 0.30 * bh,
                fill=COW_BLACK, outline="", tags=tags,
            )
        else:
            self.create_oval(
                x + 0.05 * bw, y - 0.30 * bh, x + 0.32 * bw, y + 0.24 * bh,
                fill=COW_BLACK, outline="", tags=tags,
            )
        self.create_oval(
            x - 0.10 * bw, y + 0.02 * bh, x + 0.12 * bw, y + 0.42 * bh,
            fill=COW_BLACK, outline="", tags=tags,
        )
        hx = x + bw / 2 + 7 * scale
        self.create_oval(
            hx - 7 * scale, y - 11 * scale, hx + 7 * scale, y + 2 * scale,
            fill=COW_WHITE, outline=COW_BLACK, width=2, tags=tags,
        )
        self.create_oval(
            hx - 3 * scale, y - 15 * scale, hx + 2 * scale, y - 10 * scale,
            fill=COW_BLACK, outline="", tags=tags,
        )
        self.create_oval(
            hx + 1 * scale, y - 8 * scale, hx + 3 * scale, y - 6 * scale,
            fill=COW_BLACK, outline="", tags=tags,
        )
        marker_y = y - bh / 2 - 20 * scale
        if pregnant:
            self._heart(x - 10 * scale, marker_y, scale)
        if full:
            self._drop(x + 12 * scale, marker_y, scale)
        self.create_text(
            x, y + bh / 2 + leg + 4, text=cow.name, anchor="n",
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
    def __init__(self, save_path=None, start_loops: bool = True,
                 clock=time.time):
        super().__init__()
        self.clock = clock
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
        try:
            self.state, _ = load_state(self.save_path)
        except SaveUnreadableError as exc:
            self.state = new_game(self.clock())
            self._readonly = True
            self.load_error = str(exc)
        self.state.catch_up(self.clock())
        self._build_ui()
        self.refresh()
        if self.load_error:
            self.set_status(self.load_error, seconds=8)
        if start_loops:
            self.after(1000, self._tick)
            self.after(10000, self._autosave)
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
        self.machine_frame = tk.Frame(shop, bg=HEADER_BG)
        self.machine_frame.pack(side="right", padx=8)

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
        self.pasture.render(self.state, now, self.positions)
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
            self.expand_button.configure(text="已全部扩建", state="disabled")
        else:
            price = CAPACITY_PRICES[self.state.capacity - 4]
            self.expand_button.configure(
                text="扩建牧场 {}".format(price),
                state="normal" if self.state.coins >= price else "disabled")

    def _sync_positions(self):
        alive = {c.id for c in self.state.cows}
        for cow_id in list(self.positions):
            if cow_id not in alive:
                del self.positions[cow_id]
        for cow in self.state.cows:
            if cow.id not in self.positions:
                self.positions[cow.id] = self._initial_position(cow.id)

    def _initial_position(self, cow_id: int) -> Tuple[float, float]:
        return (150.0 + (cow_id * 173) % 560, 150.0 + (cow_id * 97) % 200)

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
        if stage == "adult":
            if cow.pregnant:
                parts.append("怀孕 还需 {}".format(
                    format_remaining(cow.due_at - now)))
            elif cow.recovery_until > now:
                parts.append("产后休养 还需 {}".format(
                    format_remaining(cow.recovery_until - now)))
            if udder_ready(cow, now):
                parts.append("满奶！")
            else:
                anchor = max(cow.last_milked_at, adult_at(cow))
                parts.append("下次挤奶 {}".format(
                    format_remaining(anchor + MILK_INTERVAL - now)))
        else:
            next_stage_at = adult_at(cow) if stage == "young" else (
                cow.born_at + 45 * 60 - cow.fed_count * 900)
            parts.append("长大还需 {}".format(
                format_remaining(next_stage_at - now)))
        self.action_var.set("  ".join(parts))
        self.milk_button.configure(
            state="normal" if (stage == "adult" and udder_ready(cow, now))
            else "disabled")
        self.feed_button.configure(
            text="喂食（背包 {} 份）".format(self.state.feed_count),
            state="normal" if self.state.can_feed(cow.id, now) else "disabled")
        self.sell_cow_button.configure(
            text="卖牛 {}".format(COW_SELL_PRICES[stage]), state="normal")

    def _update_shop(self):
        if not free_slot_left(self.state):
            self.buy_calf_button.configure(text="牧场满了", state="disabled")
        else:
            self.buy_calf_button.configure(
                text="买牛仔 {}".format(CALF_PRICE),
                state="normal" if self.state.coins >= CALF_PRICE else "disabled")
        self.buy_feed_button.configure(
            text="高级饲料 {}（背包 {}）".format(FEED_PRICE, self.state.feed_count),
            state="normal" if self.state.coins >= FEED_PRICE else "disabled")
        if len(self.state.machines) >= MAX_MACHINES:
            self.buy_machine_button.configure(text="加工器已达上限", state="disabled")
        else:
            price = MACHINE_PRICES[len(self.state.machines)]
            self.buy_machine_button.configure(
                text="买加工器 {}".format(price),
                state="normal" if self.state.coins >= price else "disabled")

    def _update_machines(self, now: float):
        if len(self.machine_rows) != len(self.state.machines):
            for child in self.machine_frame.winfo_children():
                child.destroy()
            self.machine_rows = []
            for index in range(len(self.state.machines)):
                row = tk.Frame(self.machine_frame, bg=HEADER_BG)
                row.pack(side="left", padx=4)
                var = tk.StringVar()
                tk.Label(row, textvariable=var, bg=HEADER_BG, fg=TEXT,
                         font=FONT_SMALL).pack(side="top")
                button = tk.Button(
                    row, text="投料（{}牛奶）".format(CHEESE_MILK_COST),
                    font=FONT_SMALL, bd=0, relief="flat", bg="#DCEBD7",
                    disabledforeground="#B0A897",
                    command=lambda i=index: self._on_process_click(i))
                button.pack(side="top")
                self.machine_rows.append((var, button))
        self.process_all_button.configure(
            state="normal" if self.state.machines else "disabled")
        for index, started in enumerate(self.state.machines):
            var, button = self.machine_rows[index]
            if started is None:
                var.set("#{} 空闲".format(index + 1))
                button.configure(
                    state="normal"
                    if self.state.stock("milk") >= CHEESE_MILK_COST else "disabled")
            else:
                var.set("#{} 制作中 {}".format(
                    index + 1, format_remaining(started + CHEESE_TIME - now)))
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
        try:
            got = self.state.sell_cow(cow.id, self.clock())
        except ValueError as exc:
            self.set_status(str(exc))
        else:
            self.selected_id = None
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
