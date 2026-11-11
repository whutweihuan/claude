#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""snake.py 的自动化测试。运行: python -m unittest test_snake -v"""

import random
import unittest

from snake import SnakeGame


class SnakeTests(unittest.TestCase):
    def make_game(self, **kwargs):
        kwargs.setdefault("rng", random.Random(42))
        return SnakeGame(**kwargs)

    # ----- 初始状态 -----

    def test_initial_snake_has_three_cells_moving_right(self):
        game = self.make_game()
        self.assertEqual(len(game.body), 3)
        self.assertEqual(game.direction, (1, 0))
        self.assertEqual(game.score, 0)
        self.assertFalse(game.game_over)

    def test_food_spawns_inside_grid_and_off_snake(self):
        game = self.make_game()
        x, y = game.food
        self.assertTrue(0 <= x < game.width)
        self.assertTrue(0 <= y < game.height)
        self.assertNotIn(game.food, game.body)

    # ----- 移动与转向 -----

    def test_step_moves_head_one_cell_and_tail_follows(self):
        game = self.make_game()
        head = game.body[0]
        tail = game.body[-1]
        game.step()
        self.assertEqual(game.body[0], (head[0] + 1, head[1]))
        self.assertEqual(len(game.body), 3)
        self.assertNotEqual(game.body[-1], tail)

    def test_turn_changes_direction_on_next_step(self):
        game = self.make_game()
        game.turn((0, -1))
        game.step()
        self.assertEqual(game.direction, (0, -1))
        self.assertEqual(game.body[0], (game.body[1][0], game.body[1][1] - 1))

    def test_reverse_turn_is_ignored(self):
        game = self.make_game()  # 向右
        game.turn((-1, 0))
        game.step()
        self.assertEqual(game.direction, (1, 0))

    def test_two_quick_turns_are_buffered(self):
        game = self.make_game()  # 向右
        game.turn((0, -1))
        game.turn((-1, 0))  # 相对第一次转向，合法
        game.step()
        self.assertEqual(game.direction, (0, -1))
        game.step()
        self.assertEqual(game.direction, (-1, 0))

    # ----- 吃食物 -----

    def test_eating_food_grows_snake_and_adds_score(self):
        game = self.make_game(
            body=[(5, 5), (4, 5), (3, 5)], direction=(1, 0), food=(6, 5)
        )
        game.step()
        self.assertEqual(game.score, 1)
        self.assertEqual(len(game.body), 4)
        self.assertEqual(game.body[0], (6, 5))
        self.assertNotEqual(game.food, (6, 5))
        self.assertNotIn(game.food, game.body)

    # ----- 碰撞 -----

    def test_hitting_wall_ends_game(self):
        game = self.make_game(
            body=[(19, 5), (18, 5), (17, 5)], direction=(1, 0), food=(0, 0)
        )
        game.step()
        self.assertTrue(game.game_over)

    def test_hitting_own_body_ends_game(self):
        game = self.make_game(
            body=[(5, 5), (5, 4), (6, 4), (6, 5), (6, 6), (5, 6), (4, 6)],
            direction=(1, 0),
            food=(0, 0),
        )
        game.step()
        self.assertTrue(game.game_over)

    def test_moving_into_vacated_tail_cell_is_allowed(self):
        game = self.make_game(
            body=[(5, 5), (5, 6), (4, 6), (4, 5)],
            direction=(-1, 0),
            food=(0, 0),
        )
        game.step()
        self.assertFalse(game.game_over)
        self.assertEqual(game.body[0], (4, 5))
        self.assertEqual(len(game.body), 4)

    # ----- 重置 -----

    def test_reset_restores_initial_state(self):
        game = self.make_game(
            body=[(19, 5), (18, 5), (17, 5)], direction=(1, 0), food=(0, 0)
        )
        game.step()
        self.assertTrue(game.game_over)
        game.reset()
        self.assertFalse(game.game_over)
        self.assertEqual(game.score, 0)
        self.assertEqual(len(game.body), 3)
        self.assertEqual(game.direction, (1, 0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
