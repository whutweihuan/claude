# -*- coding: utf-8 -*-
"""小菜园桌面版（tkinter）。运行: python farm_gui.py"""

import time
import tkinter as tk
from pathlib import Path
from typing import List

from farm_core import (
    CROPS, INITIAL_PLOTS, LAND_PRICES, MAX_PLOTS, load_state, save_state,
)

BG = "#F6F1E7"
HEADER_BG = "#E9DFC9"
CARD_BG = "#EFE6D6"
WAREHOUSE_BG = "#F3ECDD"
SOIL = "#8B5E3C"
SOIL_DARK = "#734A2E"
LOCKED_SOIL = "#B9AA95"
TEXT = "#3F3327"
MUTED = "#8A7A66"
GREEN = "#4F8F3F"
HIGHLIGHT = "#E2A33B"

FONT = ("Microsoft YaHei UI", 10)
FONT_SMALL = ("Microsoft YaHei UI", 9)
FONT_BOLD = ("Microsoft YaHei UI", 11, "bold")
FONT_TITLE = ("Microsoft YaHei UI", 14, "bold")


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


class PlotCard(tk.Frame):
    WIDTH = 200
    CANVAS_HEIGHT = 134

    def __init__(self, master, index, on_click, on_water):
        super().__init__(master, bg=CARD_BG, padx=4, pady=4)
        self.index = index
        self.on_click = on_click
        self.on_water = on_water

        self.canvas = tk.Canvas(
            self, width=self.WIDTH, height=self.CANVAS_HEIGHT,
            bg=CARD_BG, highlightthickness=0, cursor="hand2",
        )
        self.canvas.pack()
        self.canvas.bind("<Button-1>", lambda event: self.on_click(self.index))

        self.water_button = tk.Button(
            self, text="浇水", font=FONT, bd=0, relief="flat",
            bg="#DCEBD7", activebackground="#C9DFC2",
            disabledforeground="#B0A897",
            command=lambda: self.on_water(self.index),
        )
        self.water_button.pack(fill="x", pady=(2, 0))

    def texts(self) -> List[str]:
        result = []
        for item in self.canvas.find_all():
            if self.canvas.type(item) == "text":
                result.append(self.canvas.itemcget(item, "text"))
        return result

    def render(self, state, index, now):
        self.canvas.delete("all")

        if index >= state.unlocked_plots:
            self._draw_soil(locked=True)
            self._text(100, 80, "未开垦", color="#6E6458", size=12)
            self.water_button.configure(state="disabled")
            return

        plot = state.plots[index]
        if plot is None:
            self._draw_soil()
            self._text(100, 70, "空地", color="#F3E4CF", size=13, bold=True)
            selected = CROPS.get(state.selected_crop)
            if selected is not None:
                self._text(100, 94, "点击种下" + selected.name, color="#F0DCC0", size=9)
            self.water_button.configure(state="disabled")
            return

        crop = CROPS.get(plot.crop_id)
        if crop is None:
            self._draw_soil()
            self._text(100, 80, "空地", color="#F3E4CF", size=13)
            self.water_button.configure(state="disabled")
            return

        progress = state.progress(index, now)
        mature = state.is_mature(index, now)
        self._draw_soil()
        if mature:
            self.canvas.create_rectangle(
                2, 2, self.WIDTH - 2, self.CANVAS_HEIGHT - 2,
                outline=HIGHLIGHT, width=3,
            )
        self._draw_plant(crop, progress, mature)
        self._text(100, 12, crop.name, color=TEXT, size=11, bold=True)
        if mature:
            self._text(100, 31, "可收获", color="#B5651D", size=10, bold=True)
        else:
            remaining = state.remaining_seconds(index, now)
            self._text(100, 31, "还需 " + format_remaining(remaining),
                       color="#4A3B2A", size=9)
            self._draw_progress_bar(progress)
        self.water_button.configure(
            state="normal" if state.can_water(index, now) else "disabled"
        )

    def _draw_soil(self, locked: bool = False):
        color = LOCKED_SOIL if locked else SOIL
        self.canvas.create_rectangle(4, 44, self.WIDTH - 4, 122, fill=color, outline="")
        if not locked:
            for y in range(58, 120, 14):
                self.canvas.create_line(10, y, self.WIDTH - 10, y,
                                        fill=SOIL_DARK, width=1)

    def _draw_plant(self, crop, progress: float, mature: bool):
        base_y = 116
        stem_height = 10 + 48 * min(1.0, progress / 0.85)
        top_y = base_y - stem_height
        self.canvas.create_line(100, base_y, 100, top_y + 4,
                                fill=crop.leaf_color, width=3)

        leaf = 5 + 7 * min(1.0, progress)
        for ratio in (0.35, 0.62):
            y = base_y - stem_height * ratio
            self.canvas.create_oval(100 - leaf - 4, y - 3, 100 - 4, y + 3,
                                    fill=crop.leaf_color, outline="")
            self.canvas.create_oval(100 + 4, y - 3, 100 + leaf + 4, y + 3,
                                    fill=crop.leaf_color, outline="")

        if progress >= 0.5:
            radius = (4 if not mature else 9) + 6 * min(1.0, (progress - 0.5) / 0.5)
            self._draw_fruit(crop, top_y, radius)

    def _draw_fruit(self, crop, top_y: float, radius: float):
        color = crop.fruit_color
        if crop.crop_id == "nangua":
            self.canvas.create_oval(
                100 - radius, top_y - radius + 2,
                100 + radius, top_y + radius + 2,
                fill=color, outline="#7A4A16",
            )
        elif crop.crop_id == "yumi":
            self.canvas.create_oval(
                100 - radius * 0.7, top_y - radius * 1.3,
                100 + radius * 0.7, top_y + radius * 1.3,
                fill=color, outline="#9A7B22",
            )
        elif crop.crop_id == "huluobo":
            self.canvas.create_oval(
                100 - radius * 0.8, top_y - radius,
                100 + radius * 0.8, top_y + radius * 1.2,
                fill=color, outline="#9A4E1C",
            )
        else:
            self.canvas.create_oval(
                100 - radius, top_y - radius,
                100 + radius, top_y + radius,
                fill=color, outline="#A33A2E",
            )

    def _draw_progress_bar(self, progress: float):
        x1, y1, x2, y2 = 45, 124, 155, 130
        self.canvas.create_rectangle(x1, y1, x2, y2, fill="#D8C9B0", outline="")
        if progress > 0:
            self.canvas.create_rectangle(
                x1, y1, x1 + (x2 - x1) * progress, y2,
                fill=GREEN, outline="",
            )

    def _text(self, x, y, text, color=TEXT, size=10, bold=False):
        font = ("Microsoft YaHei UI", size, "bold") if bold else ("Microsoft YaHei UI", size)
        self.canvas.create_text(x, y, text=text, fill=color, font=font)


class FarmApp(tk.Tk):
    def __init__(self, save_path=None, start_loops=True, clock=time.time):
        super().__init__()
        self.save_path = Path(save_path) if save_path else Path(__file__).with_name("save.json")
        self.start_loops = start_loops
        self.clock = clock
        self.state, self.load_warning = load_state(self.save_path)
        self._alive = True
        self._status_reset_id = None

        self.title("小菜园")
        self.geometry("1180x680")
        self.minsize(1000, 600)
        self.configure(bg=BG)

        self._build_ui()
        self.refresh()
        if self.load_warning:
            self.set_status(self.load_warning)

        if self.start_loops:
            self.after(1000, self._tick)
            self.after(10000, self._autosave)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        self.header = tk.Frame(self, bg=HEADER_BG, padx=16, pady=8)
        self.header.pack(side="top", fill="x")

        self.coins_var = tk.StringVar()
        self.harvests_var = tk.StringVar()
        self.income_var = tk.StringVar()
        for var in (self.coins_var, self.harvests_var, self.income_var):
            tk.Label(self.header, textvariable=var, font=FONT_BOLD,
                     bg=HEADER_BG, fg=TEXT).pack(side="left", padx=(0, 22))

        self.land_button = tk.Button(
            self.header, text="开垦", font=FONT, bd=0, relief="flat",
            bg="#D9C7A7", activebackground="#CDB891", padx=14, pady=3,
            command=self._on_buy_land_click,
        )
        self.land_button.pack(side="right")

        self.status_var = tk.StringVar(value="选一种种子，点空地种下")
        self.status_label = tk.Label(
            self, textvariable=self.status_var, anchor="w", font=FONT_SMALL,
            bg="#E4DAC6", fg=MUTED, padx=16, pady=5,
        )
        self.status_label.pack(side="bottom", fill="x")

        self.seed_frame = tk.Frame(self, bg=BG, padx=12, pady=8)
        self.seed_frame.pack(side="bottom", fill="x")
        tk.Label(self.seed_frame, text="种子：", font=FONT, bg=BG, fg=TEXT).pack(
            side="left", padx=(0, 6)
        )
        self.seed_buttons = {}
        for crop in CROPS.values():
            button = tk.Button(
                self.seed_frame,
                text="{} {}/{}".format(
                    crop.name, format_duration(crop.grow_seconds), crop.seed_price
                ),
                font=FONT, bd=1, relief="raised", padx=8, pady=3,
                command=lambda crop_id=crop.crop_id: self._on_seed_click(crop_id),
            )
            button.pack(side="left", padx=3)
            self.seed_buttons[crop.crop_id] = button

        self.harvest_all_button = tk.Button(
            self.seed_frame, text="一键收获", font=FONT, bd=0, relief="flat",
            bg="#D9C7A7", activebackground="#CDB891", padx=12, pady=3,
            command=self._on_harvest_all_click,
        )
        self.harvest_all_button.pack(side="right")

        body = tk.Frame(self, bg=BG, padx=12, pady=12)
        body.pack(side="top", fill="both", expand=True)

        self.warehouse_frame = tk.Frame(
            body, bg=WAREHOUSE_BG, width=280, padx=12, pady=12,
        )
        self.warehouse_frame.pack(side="right", fill="y", padx=(12, 0))
        self.warehouse_frame.pack_propagate(False)
        tk.Label(self.warehouse_frame, text="仓库", font=FONT_TITLE,
                 bg=WAREHOUSE_BG, fg=TEXT).pack(anchor="w", pady=(0, 6))

        self.sell_all_button = tk.Button(
            self.warehouse_frame, text="全部卖出（0 金币）", font=FONT,
            bd=0, relief="flat", bg="#D9C7A7", activebackground="#CDB891",
            padx=8, pady=4, command=self._on_sell_all_click,
        )
        self.sell_all_button.pack(side="bottom", fill="x", pady=(12, 0))

        self.warehouse_vars = {}
        self.warehouse_subtotal_vars = {}
        self.sell_buttons = {}
        for crop in CROPS.values():
            row = tk.Frame(self.warehouse_frame, bg=WAREHOUSE_BG)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=crop.name, width=4, anchor="w",
                     font=FONT, bg=WAREHOUSE_BG, fg=TEXT).pack(side="left")
            count_var = tk.StringVar(value="×0")
            tk.Label(row, textvariable=count_var, width=3, anchor="w",
                     font=FONT, bg=WAREHOUSE_BG, fg=TEXT).pack(side="left")
            tk.Label(row, text="{}/个".format(crop.sell_price), width=6, anchor="w",
                     font=FONT_SMALL, bg=WAREHOUSE_BG, fg=MUTED).pack(side="left")
            subtotal_var = tk.StringVar(value="0")
            tk.Label(row, textvariable=subtotal_var, width=4, anchor="e",
                     font=FONT_SMALL, bg=WAREHOUSE_BG, fg=MUTED).pack(side="left")
            button = tk.Button(
                row, text="卖出", font=FONT_SMALL, bd=0, relief="flat",
                bg="#DCEBD7", activebackground="#C9DFC2", padx=4, pady=1,
                command=lambda crop_id=crop.crop_id: self._on_sell_click(crop_id),
            )
            button.pack(side="right")
            self.warehouse_vars[crop.crop_id] = count_var
            self.warehouse_subtotal_vars[crop.crop_id] = subtotal_var
            self.sell_buttons[crop.crop_id] = button

        self.farm_frame = tk.Frame(body, bg=BG)
        self.farm_frame.pack(side="left", fill="both", expand=True)
        self.plot_cards = []
        for index in range(MAX_PLOTS):
            card = PlotCard(
                self.farm_frame, index, self._on_plot_click, self._on_water_click,
            )
            card.grid(row=index // 4, column=index % 4, padx=6, pady=6)
            self.plot_cards.append(card)

    def refresh(self):
        now = self.clock()
        for index, card in enumerate(self.plot_cards):
            card.render(self.state, index, now)
        self._update_header()
        self._update_seed_buttons()
        self._update_warehouse()
        self._update_harvest_all_button(now)
        self._update_title(now)
        return now

    def _update_header(self):
        self.coins_var.set("金币 {}".format(self.state.coins))
        self.harvests_var.set("累计收获 {} 次".format(self.state.total_harvests))
        self.income_var.set("累计收入 {}".format(self.state.total_income))
        if self.state.unlocked_plots >= MAX_PLOTS:
            self.land_button.configure(text="已全部开垦", state="disabled")
        else:
            price = LAND_PRICES[self.state.unlocked_plots - INITIAL_PLOTS]
            self.land_button.configure(text="开垦 {}".format(price), state="normal")

    def _update_title(self, now: float):
        ripe = sum(
            1 for index in range(MAX_PLOTS) if self.state.is_mature(index, now)
        )
        self.title("小菜园（{} 可收）".format(ripe) if ripe else "小菜园")

    def _update_seed_buttons(self):
        for crop_id, button in self.seed_buttons.items():
            crop = CROPS[crop_id]
            selected = crop_id == self.state.selected_crop
            affordable = self.state.coins >= crop.seed_price
            button.configure(
                relief="sunken" if selected else "raised",
                bg="#CDE0C7" if affordable else "#DDD4C4",
                fg=TEXT if affordable else "#9A8F7F",
            )

    def _update_warehouse(self):
        total = 0
        for crop_id, count_var in self.warehouse_vars.items():
            crop = CROPS[crop_id]
            count = self.state.warehouse.get(crop_id, 0)
            subtotal = count * crop.sell_price
            count_var.set("×{}".format(count))
            self.warehouse_subtotal_vars[crop_id].set(str(subtotal))
            button = self.sell_buttons[crop_id]
            if count > 0:
                button.configure(state="normal", bg="#DCEBD7", fg=TEXT)
            else:
                button.configure(state="disabled", bg="#E7E0D3", fg="#B0A897")
            total += subtotal
        self.sell_all_button.configure(
            text="全部卖出（{} 金币）".format(total),
            state="normal" if total > 0 else "disabled",
        )

    def _update_harvest_all_button(self, now):
        ripe = any(
            self.state.is_mature(index, now) for index in range(MAX_PLOTS)
        )
        self.harvest_all_button.configure(state="normal" if ripe else "disabled")

    def set_status(self, text, seconds=3):
        self.status_var.set(text)
        if self._status_reset_id is not None:
            try:
                self.after_cancel(self._status_reset_id)
            except tk.TclError:
                pass
        self._status_reset_id = self.after(seconds * 1000, self._reset_status)

    def _reset_status(self):
        self._status_reset_id = None
        self.status_var.set("选一种种子，点空地种下")

    def _on_seed_click(self, crop_id):
        crop = CROPS.get(crop_id)
        if crop is None:
            return
        self.state.selected_crop = crop_id
        self.set_status("已选择{}".format(crop.name))
        self._save()
        self.refresh()

    def _on_plot_click(self, index):
        if index >= MAX_PLOTS:
            return
        if index >= self.state.unlocked_plots:
            self.set_status("这块地还没开垦")
            return
        now = self.clock()
        plot = self.state.plots[index]
        if plot is None:
            crop_id = self.state.selected_crop
            crop = CROPS.get(crop_id)
            try:
                self.state.plant(index, crop_id, now)
            except ValueError as exc:
                self.set_status(str(exc))
                return
            self.set_status("种下了{}".format(crop.name))
            self._save()
            self.refresh()
            return
        crop = CROPS.get(plot.crop_id)
        if crop is None:
            self.set_status("这块地没有作物")
            return
        if self.state.is_mature(index, now):
            try:
                self.state.harvest(index, now)
            except ValueError as exc:
                self.set_status(str(exc))
                return
            self.set_status("收获了{}".format(crop.name))
            self._save()
            self.refresh()
            return
        remaining = self.state.remaining_seconds(index, now)
        self.set_status("{}还需 {}".format(crop.name, format_remaining(remaining)))

    def _on_water_click(self, index):
        try:
            self.state.water(index, self.clock())
        except ValueError as exc:
            self.set_status(str(exc))
            return
        self.set_status("浇水成功，生长加快")
        self._save()
        self.refresh()

    def _on_harvest_all_click(self):
        count = self.state.harvest_all(self.clock())
        if count:
            self.set_status("收获了 {} 份作物".format(count))
        else:
            self.set_status("没有可收获的作物")
        self._save()
        self.refresh()

    def _on_sell_click(self, crop_id):
        crop = CROPS.get(crop_id)
        if crop is None:
            return
        amount = self.state.sell(crop_id)
        if amount:
            self.set_status("卖出{}，+{} 金币".format(crop.name, amount))
        else:
            self.set_status("仓库里没有{}".format(crop.name))
        self._save()
        self.refresh()

    def _on_sell_all_click(self):
        amount = self.state.sell_all()
        if amount:
            self.set_status("全部卖出，+{} 金币".format(amount))
        else:
            self.set_status("仓库是空的")
        self._save()
        self.refresh()

    def _on_buy_land_click(self):
        try:
            unlocked = self.state.buy_land()
        except ValueError as exc:
            self.set_status(str(exc))
            return
        self.set_status("已开垦第 {} 块地".format(unlocked))
        self._save()
        self.refresh()

    def _save(self):
        try:
            save_state(self.state, self.save_path)
        except OSError as exc:
            self.set_status("保存失败：{}".format(exc))

    def _on_close(self):
        self._save()
        self._alive = False
        self.destroy()

    def _tick(self):
        if not self._alive:
            return
        self.refresh()
        self.after(1000, self._tick)

    def _autosave(self):
        if not self._alive:
            return
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
    app = FarmApp()
    app.mainloop()


if __name__ == "__main__":
    main()
