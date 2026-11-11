#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""贪吃蛇游戏逻辑（与界面无关，可单独测试）。

运行测试: python -m unittest test_snake -v
启动游戏: python snake_gui.py
"""

import random

UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)

_DIRECTIONS = (UP, DOWN, LEFT, RIGHT)


class SnakeGame:
    """网格上的贪吃蛇：固定步进，撞墙或撞到自己即结束。"""

    def __init__(
        self,
        width=20,
        height=20,
        body=None,
        direction=RIGHT,
        food=None,
        rng=None,
    ):
        self.width = width
        self.height = height
        self.rng = rng or random.Random()
        self._initial_body = list(body) if body is not None else None
        self._initial_direction = tuple(direction)
        self._initial_food = tuple(food) if food is not None else None
        self.reset()

    # ----- 状态管理 -----

    def reset(self):
        """回到新开一局的状态。"""
        cx, cy = self.width // 2, self.height // 2
        if self._initial_body is not None:
            self.body = list(self._initial_body)
        else:
            self.body = [(cx, cy), (cx - 1, cy), (cx - 2, cy)]
        self.direction = self._initial_direction
        self._pending = []
        self.score = 0
        self.game_over = False
        self.food = self._initial_food
        if self.food is None:
            self._spawn_food()

    # ----- 操作 -----

    def turn(self, direction):
        """请求转向。反向或重复的方向被忽略，最多缓冲两步。"""
        direction = tuple(direction)
        if direction not in _DIRECTIONS:
            return
        last = self._pending[-1] if self._pending else self.direction
        if direction == last:
            return
        if direction[0] == -last[0] and direction[1] == -last[1]:
            return
        if len(self._pending) < 2:
            self._pending.append(direction)

    def step(self):
        """前进一格：移动、吃食物、判定碰撞。"""
        if self.game_over:
            return

        if self._pending:
            self.direction = self._pending.pop(0)

        head = self.body[0]
        new_head = (head[0] + self.direction[0], head[1] + self.direction[1])

        # 撞墙
        if not (0 <= new_head[0] < self.width and 0 <= new_head[1] < self.height):
            self.game_over = True
            return

        growing = new_head == self.food
        # 不增长时，尾巴这一格会在同一步腾出来，可以进入
        occupied = self.body if growing else self.body[:-1]
        if new_head in occupied:
            self.game_over = True
            return

        self.body.insert(0, new_head)
        if growing:
            self.score += 1
            self._spawn_food()
        else:
            self.body.pop()

    # ----- 内部 -----

    def _spawn_food(self):
        occupied = set(self.body)
        free = [
            (x, y)
            for x in range(self.width)
            for y in range(self.height)
            if (x, y) not in occupied
        ]
        self.food = self.rng.choice(free) if free else None
