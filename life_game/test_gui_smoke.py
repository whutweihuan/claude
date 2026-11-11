#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tkinter 界面冒烟测试。运行: python -m unittest test_gui_smoke -v"""

import tkinter as tk
import unittest
from types import SimpleNamespace

import life
import life_gui


def cell_event(col, row):
    return SimpleNamespace(
        x=col * life_gui.CELL + life_gui.CELL // 2,
        y=row * life_gui.CELL + life_gui.CELL // 2,
    )


class GuiTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.board = life.LifeBoard(life_gui.GRID_WIDTH, life_gui.GRID_HEIGHT)
        self.app = life_gui.LifeApp(self.root, board=self.board)
        self.root.update_idletasks()

    def tearDown(self):
        try:
            self.app._on_close()
        except tk.TclError:
            pass

    def test_window_builds_board_canvas_and_controls(self):
        self.assertEqual(self.app.title(), "康威生命游戏")
        self.assertEqual(
            int(self.app.canvas.cget("width")),
            life_gui.GRID_WIDTH * life_gui.CELL,
        )
        self.assertEqual(
            int(self.app.canvas.cget("height")),
            life_gui.GRID_HEIGHT * life_gui.CELL,
        )
        self.assertEqual(self.app.start_button.cget("text"), "开始")
        self.assertIn("第 0 代", self.app.status_var.get())

    def test_left_click_toggles_cell_and_updates_status(self):
        self.app._on_left_press(cell_event(2, 3))
        self.app._on_left_release(cell_event(2, 3))
        self.assertTrue(self.board.is_alive(2, 3))
        self.assertIn("第 0 代", self.app.status_var.get())
        self.assertIn("存活 1", self.app.status_var.get())

    def test_left_drag_paints_same_state_across_cells(self):
        self.app._on_left_press(cell_event(1, 1))
        self.app._on_left_drag(cell_event(2, 1))
        self.app._on_left_drag(cell_event(3, 1))
        self.app._on_left_release(cell_event(3, 1))
        self.assertEqual(self.board.cells, {(1, 1), (2, 1), (3, 1)})

    def test_right_click_erases_cell(self):
        self.board.set_alive(4, 4)
        self.app._on_right_press(cell_event(4, 4))
        self.assertFalse(self.board.is_alive(4, 4))

    def test_drawing_pauses_running_simulation(self):
        self.app._toggle_running()
        self.assertTrue(self.app.running)
        self.app._on_left_press(cell_event(5, 5))
        self.assertFalse(self.app.running)
        self.assertIsNone(self.app._after_id)
        self.assertEqual(self.app.start_button.cget("text"), "开始")

    def test_start_button_toggles_running_state(self):
        self.app._toggle_running()
        self.assertTrue(self.app.running)
        self.assertEqual(self.app.start_button.cget("text"), "暂停")
        self.app._toggle_running()
        self.assertFalse(self.app.running)
        self.assertEqual(self.app.start_button.cget("text"), "继续")

    def test_step_once_advances_generation(self):
        self.board.load_pattern([(1, 1), (2, 1), (3, 1)])
        self.app._step_once()
        self.assertEqual(self.board.generation, 1)
        self.assertIn("第 1 代", self.app.status_var.get())

    def test_running_tick_evolves_and_schedules_next_frame(self):
        self.board.load_pattern([(1, 1), (2, 1), (3, 1)])
        self.app.running = True
        self.app._tick()
        self.assertEqual(self.board.generation, 1)
        self.assertIsNotNone(self.app._after_id)
        self.app._stop_simulation()

    def test_clear_board_resets_state(self):
        self.board.load_pattern([(1, 1), (2, 1), (3, 1)])
        self.board.step()
        self.app.refresh()
        self.app._clear_board()
        self.assertEqual(self.board.population, 0)
        self.assertEqual(self.board.generation, 0)
        self.assertIn("第 0 代", self.app.status_var.get())

    def test_randomize_board_can_fill_whole_board(self):
        self.app._randomize_board(density=1.0)
        self.assertEqual(
            self.board.population,
            life_gui.GRID_WIDTH * life_gui.GRID_HEIGHT,
        )

    def test_loading_preset_pauses_and_places_pattern(self):
        self.app._toggle_running()
        self.app._load_preset("滑翔机")
        self.assertFalse(self.app.running)
        self.assertEqual(self.board.population, 5)
        self.assertEqual(self.board.generation, 0)

    def test_speed_change_updates_delay(self):
        self.app._on_speed_change("650")
        self.assertEqual(self.app._delay_ms, 650)

    def test_layout_fits_requested_window(self):
        self.root.deiconify()
        self.root.update_idletasks()
        for name in ("canvas", "start_button", "step_button", "clear_button"):
            widget = getattr(self.app, name)
            self.assertLessEqual(
                widget.winfo_reqwidth(),
                self.root.winfo_screenwidth(),
                "%s 请求宽度超过屏幕" % name,
            )
        self.assertTrue(self.app.canvas.winfo_reqheight() > 0)

    def test_status_labels_fit_long_generation_and_population(self):
        self.root.deiconify()
        self.board.generation = 99999
        self.board.cells = {
            (x, y)
            for y in range(life_gui.GRID_HEIGHT)
            for x in range(life_gui.GRID_WIDTH)
        }
        self.app.refresh()
        self.root.update()
        for label in (self.app.generation_label, self.app.population_label):
            self.assertLessEqual(
                label.winfo_reqwidth(),
                label.winfo_width(),
                "状态文字被面板裁切",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
