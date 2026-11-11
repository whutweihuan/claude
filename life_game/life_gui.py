#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""康威生命游戏桌面版（tkinter）。运行: python life_gui.py"""

import tkinter as tk

import life

GRID_WIDTH = 40
GRID_HEIGHT = 28
CELL = 18
DEFAULT_DELAY_MS = 180

BG = "#0f1117"
PANEL = "#171a24"
BOARD_BG = "#0b0d13"
GRID_LINE = "#1f2534"
CELL_ALIVE = "#7aa2f7"
TEXT = "#e6e9f2"
MUTED = "#8b93a8"
BUTTON_BG = "#252a3a"
BUTTON_ACTIVE = "#323a50"
ACCENT = "#3b5bdb"
ACCENT_ACTIVE = "#4c6ef5"

FONT = "Microsoft YaHei UI"


class LifeApp:
    """生命游戏的桌面界面：在网格上画图，然后开始演化。"""

    def __init__(self, root, board=None):
        self.root = root
        self.board = board or life.LifeBoard(GRID_WIDTH, GRID_HEIGHT)
        self.running = False
        self._after_id = None
        self._paint_value = None
        self._delay_ms = DEFAULT_DELAY_MS

        root.title("康威生命游戏")
        root.configure(bg=BG)
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.bind("<space>", self._on_space)
        root.bind("<Key-n>", self._on_step_key)
        root.bind("<Key-N>", self._on_step_key)
        root.bind("<Key-c>", self._on_clear_key)
        root.bind("<Key-C>", self._on_clear_key)
        root.bind("<Key-r>", self._on_random_key)
        root.bind("<Key-R>", self._on_random_key)

        self._build_ui()
        self.refresh()
        self._fit_window()

    # ----- 界面搭建 -----

    def title(self):
        return self.root.title()

    def _build_ui(self):
        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True, padx=18, pady=18)

        left = tk.Frame(main, bg=BG)
        left.pack(side="left", fill="both", expand=True)

        title = tk.Label(
            left, text="康威生命游戏", bg=BG, fg=TEXT,
            font=(FONT, 21, "bold"), anchor="w",
        )
        title.pack(fill="x")
        subtitle = tk.Label(
            left, text="点击或拖动格子，画出初始图形，再让它自己演化。",
            bg=BG, fg=MUTED, font=(FONT, 10), anchor="w",
        )
        subtitle.pack(fill="x", pady=(2, 12))

        self.canvas = tk.Canvas(
            left, width=self.board.width * CELL, height=self.board.height * CELL,
            bg=BOARD_BG, highlightthickness=0, cursor="crosshair",
        )
        self.canvas.pack(anchor="nw")
        self.canvas.bind("<ButtonPress-1>", self._on_left_press)
        self.canvas.bind("<B1-Motion>", self._on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_left_release)
        self.canvas.bind("<ButtonPress-3>", self._on_right_press)
        self.canvas.bind("<B3-Motion>", self._on_right_drag)

        panel = tk.Frame(main, bg=PANEL, padx=14, pady=14)
        panel.pack(side="right", fill="y", padx=(18, 0))

        self.status_var = tk.StringVar()
        self.generation_var = tk.StringVar()
        self.population_var = tk.StringVar()
        self.generation_label = tk.Label(
            panel, textvariable=self.generation_var, bg=PANEL, fg=TEXT,
            font=(FONT, 14, "bold"), anchor="w",
        )
        self.generation_label.pack(fill="x")
        self.population_label = tk.Label(
            panel, textvariable=self.population_var, bg=PANEL, fg=MUTED,
            font=(FONT, 10), anchor="w",
        )
        self.population_label.pack(fill="x", pady=(0, 10))

        self.start_button = self._button(
            panel, "开始", self._toggle_running, primary=True,
        )
        self.start_button.pack(fill="x", pady=2)

        self.step_button = self._button(panel, "单步", self._step_once)
        self.step_button.pack(fill="x", pady=2)

        row = tk.Frame(panel, bg=PANEL)
        row.pack(fill="x", pady=2)
        self.clear_button = self._button(row, "清空", self._clear_board)
        self.clear_button.pack(side="left", fill="x", expand=True, padx=(0, 3))
        self.random_button = self._button(row, "随机", self._randomize_board)
        self.random_button.pack(side="left", fill="x", expand=True, padx=(3, 0))

        speed_head = tk.Frame(panel, bg=PANEL)
        speed_head.pack(fill="x", pady=(10, 0))
        tk.Label(
            speed_head, text="演化速度", bg=PANEL, fg=MUTED,
            font=(FONT, 10), anchor="w",
        ).pack(side="left")
        self.speed_label_var = tk.StringVar()
        tk.Label(
            speed_head, textvariable=self.speed_label_var, bg=PANEL, fg=TEXT,
            font=(FONT, 10), anchor="e",
        ).pack(side="right")
        self.speed_var = tk.IntVar(value=DEFAULT_DELAY_MS)
        self.speed_scale = tk.Scale(
            panel, from_=50, to=1000, resolution=50, orient="horizontal",
            variable=self.speed_var, command=self._on_speed_change,
            bg=PANEL, fg=TEXT, troughcolor="#2a3146",
            activebackground=ACCENT, highlightthickness=0,
            sliderrelief="flat", showvalue=False, bd=0,
            sliderlength=18, width=10,
        )
        self.speed_scale.pack(fill="x", pady=(0, 8))

        tk.Label(
            panel, text="预设图形", bg=PANEL, fg=MUTED,
            font=(FONT, 10), anchor="w",
        ).pack(fill="x", pady=(2, 2))
        for name in life.PATTERNS:
            button = self._button(
                panel, name, lambda n=name: self._load_preset(n),
            )
            button.pack(fill="x", pady=1)

        tk.Label(
            panel,
            text="左键绘制 · 右键擦除\n拖动可以连续画\n空格 开始 / 暂停 · N 单步\nC 清空 · R 随机",
            bg=PANEL, fg=MUTED, font=(FONT, 9),
            justify="left", anchor="w",
        ).pack(fill="x", pady=(8, 0))

        self._on_speed_change(str(DEFAULT_DELAY_MS))

    def _button(self, parent, text, command, primary=False):
        return tk.Button(
            parent, text=text, command=command,
            bg=ACCENT if primary else BUTTON_BG,
            fg="#ffffff" if primary else TEXT,
            activebackground=ACCENT_ACTIVE if primary else BUTTON_ACTIVE,
            activeforeground="#ffffff" if primary else TEXT,
            font=(FONT, 10), relief="flat", bd=0,
            padx=10, pady=5, cursor="hand2", anchor="center",
        )

    def _fit_window(self):
        self.root.update_idletasks()
        width = self.root.winfo_reqwidth()
        height = self.root.winfo_reqheight()
        self.root.minsize(width, height)
        x = max(0, (self.root.winfo_screenwidth() - width) // 2)
        y = max(0, (self.root.winfo_screenheight() - height) // 2)
        self.root.geometry("%dx%d+%d+%d" % (width, height, x, y))

    # ----- 绘制与状态 -----

    def refresh(self):
        self._draw()
        self.status_var.set(
            "第 %d 代  ·  存活 %d" % (self.board.generation, self.board.population)
        )
        self.generation_var.set("第 %d 代" % self.board.generation)
        self.population_var.set("存活 %d" % self.board.population)

    def _draw(self):
        canvas = self.canvas
        canvas.delete("all")
        width = self.board.width * CELL
        height = self.board.height * CELL

        for col in range(1, self.board.width):
            x = col * CELL
            canvas.create_line(x, 0, x, height, fill=GRID_LINE)
        for row in range(1, self.board.height):
            y = row * CELL
            canvas.create_line(0, y, width, y, fill=GRID_LINE)

        for x, y in self.board.cells:
            canvas.create_rectangle(
                x * CELL + 1, y * CELL + 1,
                (x + 1) * CELL - 1, (y + 1) * CELL - 1,
                fill=CELL_ALIVE, outline="",
            )

    def _cell_at(self, event):
        x = int(event.x) // CELL
        y = int(event.y) // CELL
        if 0 <= x < self.board.width and 0 <= y < self.board.height:
            return x, y
        return None

    # ----- 画图 -----

    def _on_left_press(self, event):
        cell = self._cell_at(event)
        if cell is None:
            return
        self._stop_simulation()
        self._paint_value = not self.board.is_alive(*cell)
        self.board.toggle(*cell)
        self.refresh()

    def _on_left_drag(self, event):
        if self._paint_value is None:
            return
        cell = self._cell_at(event)
        if cell is None:
            return
        self.board.set_alive(cell[0], cell[1], self._paint_value)
        self.refresh()

    def _on_left_release(self, event):
        self._paint_value = None

    def _on_right_press(self, event):
        cell = self._cell_at(event)
        if cell is None:
            return
        self._stop_simulation()
        self.board.set_alive(cell[0], cell[1], False)
        self.refresh()

    def _on_right_drag(self, event):
        cell = self._cell_at(event)
        if cell is None:
            return
        self.board.set_alive(cell[0], cell[1], False)
        self.refresh()

    # ----- 演化控制 -----

    def _toggle_running(self):
        if self.running:
            self._stop_simulation(resume_label=True)
        else:
            self.running = True
            self.start_button.configure(text="暂停")
            self._schedule()

    def _schedule(self):
        self._cancel_timer()
        self._after_id = self.root.after(self._delay_ms, self._tick)

    def _cancel_timer(self):
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None

    def _tick(self):
        self._after_id = None
        if not self.running:
            return
        self.board.step()
        self.refresh()
        if self.running:
            self._schedule()

    def _stop_simulation(self, resume_label=False):
        self._cancel_timer()
        self.running = False
        self.start_button.configure(text="继续" if resume_label else "开始")

    def _step_once(self):
        self._stop_simulation()
        self.board.step()
        self.refresh()

    def _clear_board(self):
        self._stop_simulation()
        self.board.clear()
        self.refresh()

    def _randomize_board(self, density=0.3):
        self._stop_simulation()
        self.board.randomize(density=density)
        self.refresh()

    def _load_preset(self, name):
        self._stop_simulation()
        self.board.load_named_pattern(name)
        self.refresh()

    def _on_speed_change(self, value):
        self._delay_ms = int(float(value))
        self.speed_label_var.set("%d ms/代" % self._delay_ms)
        if self.running:
            self._schedule()

    # ----- 快捷键与关闭 -----

    def _on_space(self, event):
        self._toggle_running()
        return "break"

    def _on_step_key(self, event):
        self._step_once()
        return "break"

    def _on_clear_key(self, event):
        self._clear_board()
        return "break"

    def _on_random_key(self, event):
        self._randomize_board()
        return "break"

    def _on_close(self):
        self._cancel_timer()
        self.root.destroy()


def main():
    root = tk.Tk()
    LifeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
