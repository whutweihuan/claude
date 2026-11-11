#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""贪吃蛇桌面版（tkinter）。运行: python snake_gui.py"""

import tkinter as tk

import snake

GRID = 20
CELL = 24
BOARD = GRID * CELL
SPEED_MS = 125  # 固定节奏：每秒 8 格

BG = "#1e1e2e"
BOARD_BG = "#181825"
GRID_LINE = "#26263a"
SNAKE_BODY = "#a6e3a1"
SNAKE_HEAD = "#c9f0c4"
FOOD = "#f38ba8"
TEXT = "#cdd6f4"
MUTED = "#6c7086"

FONT = "Microsoft YaHei UI"

KEYS = {
    "Up": snake.UP,
    "Down": snake.DOWN,
    "Left": snake.LEFT,
    "Right": snake.RIGHT,
    "w": snake.UP,
    "W": snake.UP,
    "s": snake.DOWN,
    "S": snake.DOWN,
    "a": snake.LEFT,
    "A": snake.LEFT,
    "d": snake.RIGHT,
    "D": snake.RIGHT,
}


class SnakeApp:
    def __init__(self, root):
        self.root = root
        self.game = snake.SnakeGame(GRID, GRID)
        self.state = "ready"  # ready / running / paused / over
        self._after_id = None

        root.title("贪吃蛇")
        root.configure(bg=BG)
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.bind("<KeyPress>", self._on_key)

        self._build_ui()
        self.score_var.set("分数  0")
        self._draw()
        self._overlay("按方向键开始", "撞墙或撞到自己就结束")
        self._center_window()

    # ----- 界面 -----

    def _build_ui(self):
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=16, pady=(12, 8))

        self.score_var = tk.StringVar()
        tk.Label(
            header, textvariable=self.score_var, bg=BG, fg=TEXT,
            font=(FONT, 16, "bold"),
        ).pack(side="left")

        tk.Label(
            header, text="方向键 / WASD 转向   空格 暂停", bg=BG, fg=MUTED,
            font=(FONT, 10),
        ).pack(side="right")

        self.canvas = tk.Canvas(
            self.root, width=BOARD, height=BOARD,
            bg=BOARD_BG, highlightthickness=0,
        )
        self.canvas.pack(padx=16, pady=(0, 16))

    def _center_window(self):
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry("+%d+%d" % (x, y))

    def _draw(self):
        c = self.canvas
        c.delete("all")

        for i in range(1, GRID):
            c.create_line(i * CELL, 0, i * CELL, BOARD, fill=GRID_LINE)
            c.create_line(0, i * CELL, BOARD, i * CELL, fill=GRID_LINE)

        food = self.game.food
        if food is not None:
            x, y = food
            c.create_oval(
                x * CELL + 5, y * CELL + 5,
                x * CELL + CELL - 5, y * CELL + CELL - 5,
                fill=FOOD, outline="",
            )

        last = len(self.game.body) - 1
        for index, (x, y) in enumerate(reversed(self.game.body)):
            color = SNAKE_HEAD if index == last else SNAKE_BODY
            c.create_rectangle(
                x * CELL + 1, y * CELL + 1,
                x * CELL + CELL - 1, y * CELL + CELL - 1,
                fill=color, outline="",
            )

    def _overlay(self, title, subtitle):
        c = self.canvas
        mid = BOARD // 2
        c.create_rectangle(
            0, mid - 58, BOARD, mid + 58, fill=BOARD_BG, outline="",
        )
        c.create_text(mid, mid - 16, text=title, fill=TEXT, font=(FONT, 24, "bold"))
        c.create_text(mid, mid + 24, text=subtitle, fill=MUTED, font=(FONT, 12))

    def _update_score(self):
        self.score_var.set("分数  %d" % self.game.score)

    # ----- 游戏循环 -----

    def _schedule(self):
        self._cancel()
        self._after_id = self.root.after(SPEED_MS, self._tick)

    def _cancel(self):
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None

    def _tick(self):
        self._after_id = None
        if self.state != "running":
            return

        self.game.step()
        self._draw()
        self._update_score()

        if self.game.game_over:
            self.state = "over"
            self._overlay("游戏结束", "得分 %d · 按 R 重新开始" % self.game.score)
            return

        self._schedule()

    # ----- 输入 -----

    def _on_key(self, event):
        key = event.keysym

        if key in ("r", "R"):
            if self.state == "over":
                self._restart()
            return

        if key == "space":
            self._toggle_pause()
            return

        direction = KEYS.get(key)
        if direction is None:
            return

        if self.state == "ready":
            self.game.turn(direction)
            self.state = "running"
            self._draw()
            self._schedule()
        elif self.state == "running":
            self.game.turn(direction)

    def _toggle_pause(self):
        if self.state == "running":
            self.state = "paused"
            self._cancel()
            self._draw()
            self._overlay("已暂停", "按空格继续")
        elif self.state == "paused":
            self.state = "running"
            self._draw()
            self._schedule()
        elif self.state == "ready":
            self.state = "running"
            self._schedule()

    def _restart(self):
        self._cancel()
        self.game.reset()
        self.state = "ready"
        self._draw()
        self._update_score()
        self._overlay("按方向键开始", "撞墙或撞到自己就结束")

    def _on_close(self):
        self._cancel()
        self.root.destroy()


def main():
    root = tk.Tk()
    SnakeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
