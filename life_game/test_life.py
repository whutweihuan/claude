#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""life.py 核心逻辑测试。运行: python -m unittest test_life -v"""

import unittest

from life import LifeBoard


class BoardStateTests(unittest.TestCase):
    def test_new_board_is_empty(self):
        board = LifeBoard(8, 6)
        self.assertEqual((board.width, board.height), (8, 6))
        self.assertEqual(board.generation, 0)
        self.assertEqual(board.population, 0)

    def test_toggle_changes_cell_state_and_returns_new_value(self):
        board = LifeBoard(8, 6)
        self.assertTrue(board.toggle(2, 3))
        self.assertTrue(board.is_alive(2, 3))
        self.assertFalse(board.toggle(2, 3))
        self.assertFalse(board.is_alive(2, 3))

    def test_toggle_ignores_coordinates_outside_board(self):
        board = LifeBoard(8, 6)
        self.assertFalse(board.toggle(-1, 0))
        self.assertFalse(board.toggle(8, 0))
        self.assertFalse(board.toggle(0, 6))
        self.assertEqual(board.population, 0)

    def test_set_alive_can_draw_and_erase(self):
        board = LifeBoard(8, 6)
        board.set_alive(1, 1)
        board.set_alive(2, 1, False)
        self.assertTrue(board.is_alive(1, 1))
        self.assertFalse(board.is_alive(2, 1))

    def test_population_counts_live_cells(self):
        board = LifeBoard(8, 6, cells=[(0, 0), (1, 0), (2, 0)])
        self.assertEqual(board.population, 3)

    def test_clear_removes_cells_and_resets_generation(self):
        board = LifeBoard(8, 6, cells=[(1, 1), (2, 1), (3, 1)])
        board.step()
        board.clear()
        self.assertEqual(board.population, 0)
        self.assertEqual(board.generation, 0)


class LifeRulesTests(unittest.TestCase):
    def test_live_cell_with_fewer_than_two_neighbors_dies(self):
        board = LifeBoard(8, 8, cells=[(3, 3)])
        board.step()
        self.assertEqual(board.population, 0)

    def test_live_cell_with_two_neighbors_survives(self):
        board = LifeBoard(8, 8, cells=[(2, 2), (2, 3), (3, 2)])
        board.step()
        self.assertTrue(board.is_alive(2, 2))

    def test_live_cell_with_three_neighbors_survives(self):
        block = [(1, 1), (2, 1), (1, 2), (2, 2)]
        board = LifeBoard(8, 8, cells=block)
        board.step()
        for x, y in block:
            self.assertTrue(board.is_alive(x, y))

    def test_live_cell_with_more_than_three_neighbors_dies(self):
        board = LifeBoard(8, 8, cells=[
            (2, 2),
            (1, 1), (2, 1), (3, 1),
            (1, 2), (3, 2),
        ])
        board.step()
        self.assertFalse(board.is_alive(2, 2))

    def test_dead_cell_with_exactly_three_neighbors_is_born(self):
        board = LifeBoard(8, 8, cells=[(1, 1), (2, 1), (3, 1)])
        self.assertFalse(board.is_alive(2, 2))
        board.step()
        self.assertTrue(board.is_alive(2, 2))

    def test_block_is_still_life(self):
        block = {(1, 1), (2, 1), (1, 2), (2, 2)}
        board = LifeBoard(8, 8, cells=block)
        board.step()
        self.assertEqual(board.cells, block)

    def test_blinker_oscillates_with_period_two(self):
        board = LifeBoard(8, 8, cells=[(1, 2), (2, 2), (3, 2)])
        board.step()
        self.assertEqual(board.cells, {(2, 1), (2, 2), (2, 3)})
        board.step()
        self.assertEqual(board.cells, {(1, 2), (2, 2), (3, 2)})

    def test_glider_moves_one_cell_diagonally_after_four_generations(self):
        start = {(1, 0), (2, 1), (0, 2), (1, 2), (2, 2)}
        board = LifeBoard(12, 12, cells=start)
        for _ in range(4):
            board.step()
        expected = {(x + 1, y + 1) for x, y in start}
        self.assertEqual(board.cells, expected)

    def test_step_increments_generation_once(self):
        board = LifeBoard(8, 8, cells=[(1, 2), (2, 2), (3, 2)])
        board.step()
        self.assertEqual(board.generation, 1)
        board.step()
        self.assertEqual(board.generation, 2)

    def test_step_clips_cells_to_board_bounds(self):
        board = LifeBoard(4, 4, cells=[(0, 0), (0, 1), (1, 0)])
        for _ in range(5):
            board.step()
        for x, y in board.cells:
            self.assertTrue(0 <= x < board.width)
            self.assertTrue(0 <= y < board.height)


class PatternTests(unittest.TestCase):
    def test_load_pattern_translates_coordinates(self):
        board = LifeBoard(8, 8)
        board.load_pattern([(0, 0), (1, 0), (2, 0)], origin=(3, 2))
        self.assertEqual(board.cells, {(3, 2), (4, 2), (5, 2)})
        self.assertEqual(board.generation, 0)

    def test_load_pattern_clips_cells_outside_board(self):
        board = LifeBoard(5, 5)
        board.load_pattern([(0, 0), (1, 0), (4, 4)], origin=(3, 4))
        self.assertEqual(board.cells, {(3, 4), (4, 4)})

    def test_load_pattern_clears_existing_cells_by_default(self):
        board = LifeBoard(8, 8, cells=[(0, 0)])
        board.load_pattern([(1, 1)])
        self.assertEqual(board.cells, {(1, 1)})

    def test_load_pattern_can_be_added_without_clearing(self):
        board = LifeBoard(8, 8, cells=[(0, 0)])
        board.load_pattern([(1, 1)], clear=False)
        self.assertEqual(board.cells, {(0, 0), (1, 1)})

    def test_load_named_pattern_centers_it_on_board(self):
        board = LifeBoard(21, 21)
        board.load_named_pattern("滑翔机")
        min_x = min(x for x, _ in board.cells)
        max_x = max(x for x, _ in board.cells)
        min_y = min(y for _, y in board.cells)
        max_y = max(y for _, y in board.cells)
        self.assertLessEqual(abs((min_x + max_x) - 20), 1)
        self.assertLessEqual(abs((min_y + max_y) - 20), 1)
        self.assertEqual(board.population, 5)

    def test_unknown_named_pattern_raises_key_error(self):
        with self.assertRaises(KeyError):
            LifeBoard(8, 8).load_named_pattern("不存在的图形")

    def test_pulsar_oscillates_with_period_three(self):
        board = LifeBoard(40, 30)
        board.load_named_pattern("脉冲星")
        start = set(board.cells)
        self.assertEqual(len(start), 48)
        for _ in range(3):
            board.step()
        self.assertEqual(board.cells, start)

    def test_gosper_glider_gun_keeps_growing(self):
        board = LifeBoard(60, 40)
        board.load_named_pattern("高斯帕滑翔机枪")
        self.assertEqual(board.population, 36)
        for _ in range(30):
            board.step()
        self.assertGreater(board.population, 36)

    def test_randomize_full_density_fills_board_and_resets_generation(self):
        board = LifeBoard(5, 4, cells=[(0, 0)])
        board.step()
        board.randomize(density=1.0)
        self.assertEqual(board.population, 20)
        self.assertEqual(board.generation, 0)

    def test_randomize_zero_density_clears_board(self):
        board = LifeBoard(5, 4, cells=[(0, 0), (1, 1)])
        board.randomize(density=0.0)
        self.assertEqual(board.population, 0)
        self.assertEqual(board.generation, 0)

    def test_randomize_rejects_invalid_density(self):
        board = LifeBoard(5, 4)
        with self.assertRaises(ValueError):
            board.randomize(density=-0.1)
        with self.assertRaises(ValueError):
            board.randomize(density=1.1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
