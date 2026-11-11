#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""康威生命游戏核心逻辑（与界面无关，可单独测试）。"""

import random
from collections import Counter


# 预设图形：坐标相对图形左上角，界面载入时会自动居中。
PATTERNS = {
    "方块": (
        (0, 0), (1, 0),
        (0, 1), (1, 1),
    ),
    "闪烁灯": (
        (0, 0), (1, 0), (2, 0),
    ),
    "滑翔机": (
        (1, 0),
        (2, 1),
        (0, 2), (1, 2), (2, 2),
    ),
    "脉冲星": (
        (2, 0), (3, 0), (4, 0), (8, 0), (9, 0), (10, 0),
        (0, 2), (5, 2), (7, 2), (12, 2),
        (0, 3), (5, 3), (7, 3), (12, 3),
        (0, 4), (5, 4), (7, 4), (12, 4),
        (2, 5), (3, 5), (4, 5), (8, 5), (9, 5), (10, 5),
        (2, 7), (3, 7), (4, 7), (8, 7), (9, 7), (10, 7),
        (0, 8), (5, 8), (7, 8), (12, 8),
        (0, 9), (5, 9), (7, 9), (12, 9),
        (0, 10), (5, 10), (7, 10), (12, 10),
        (2, 12), (3, 12), (4, 12), (8, 12), (9, 12), (10, 12),
    ),
    "高斯帕滑翔机枪": (
        (24, 0),
        (22, 1), (24, 1),
        (12, 2), (13, 2), (20, 2), (21, 2), (34, 2), (35, 2),
        (11, 3), (15, 3), (20, 3), (21, 3), (34, 3), (35, 3),
        (0, 4), (1, 4), (10, 4), (16, 4), (20, 4), (21, 4),
        (0, 5), (1, 5), (10, 5), (14, 5), (16, 5), (17, 5), (22, 5), (24, 5),
        (10, 6), (16, 6), (24, 6),
        (11, 7), (15, 7),
        (12, 8), (13, 8),
    ),
}


class LifeBoard:
    """有限网格上的康威生命游戏。

    坐标 (x, y) 从左上角开始，x 向右递增，y 向下递增。
    网格外的邻居视为死亡，活细胞跑到网格外就会消失。
    """

    def __init__(self, width=40, height=28, cells=None):
        if width <= 0 or height <= 0:
            raise ValueError("width and height must be positive")
        self.width = int(width)
        self.height = int(height)
        self.cells = set()
        self.generation = 0
        if cells:
            for x, y in cells:
                self._add_if_inside(x, y)

    @property
    def population(self):
        return len(self.cells)

    def is_alive(self, x, y):
        return (x, y) in self.cells

    def toggle(self, x, y):
        """切换格子状态；坐标越界时忽略。返回切换后的状态。"""
        if not self._inside(x, y):
            return False
        if (x, y) in self.cells:
            self.cells.remove((x, y))
            return False
        self.cells.add((x, y))
        return True

    def set_alive(self, x, y, alive=True):
        """设置格子状态；坐标越界时忽略。"""
        if not self._inside(x, y):
            return
        if alive:
            self.cells.add((x, y))
        else:
            self.cells.discard((x, y))

    def clear(self):
        self.cells.clear()
        self.generation = 0

    def load_pattern(self, cells, origin=(0, 0), clear=True):
        """把一组相对坐标载入棋盘，越界部分裁掉，并重置代数。"""
        if clear:
            self.cells.clear()
        ox, oy = origin
        for x, y in cells:
            self._add_if_inside(x + ox, y + oy)
        self.generation = 0

    def load_named_pattern(self, name, origin=None, clear=True):
        """载入 PATTERNS 中的预设图形；origin 为 None 时居中放置。"""
        cells = PATTERNS[name]
        if origin is None:
            max_x = max(x for x, _ in cells)
            max_y = max(y for _, y in cells)
            origin = (
                (self.width - (max_x + 1)) // 2,
                (self.height - (max_y + 1)) // 2,
            )
        self.load_pattern(cells, origin=origin, clear=clear)

    def randomize(self, density=0.3, rng=None):
        """按给定密度随机填充棋盘，并重置代数。"""
        if not 0.0 <= density <= 1.0:
            raise ValueError("density must be between 0 and 1")
        rng = rng or random.Random()
        self.cells = {
            (x, y)
            for y in range(self.height)
            for x in range(self.width)
            if rng.random() < density
        }
        self.generation = 0

    def step(self):
        """演化一代。活细胞在 2/3 个活邻居时存活，死细胞在恰好 3 个活邻居时出生。"""
        neighbor_counts = Counter()
        for x, y in self.cells:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if self._inside(nx, ny):
                        neighbor_counts[(nx, ny)] += 1

        self.cells = {
            cell
            for cell, count in neighbor_counts.items()
            if count == 3 or (count == 2 and cell in self.cells)
        }
        self.generation += 1

    def _inside(self, x, y):
        return 0 <= x < self.width and 0 <= y < self.height

    def _add_if_inside(self, x, y):
        if self._inside(x, y):
            self.cells.add((x, y))
