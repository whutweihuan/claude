# -*- coding: utf-8 -*-
"""小菜园核心逻辑：作物、地块、经济与存档。不依赖 Tkinter。"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

MAX_PLOTS = 8
INITIAL_PLOTS = 4
INITIAL_COINS = 60
LAND_PRICES = (200, 500, 1000, 1800)
WATER_RATIO = 0.10
WATER_MAX = 3
WATER_COOLDOWN = 10 * 60


@dataclass(frozen=True)
class Crop:
    crop_id: str
    name: str
    grow_seconds: int
    seed_price: int
    sell_price: int
    leaf_color: str
    fruit_color: str


CROPS: Dict[str, Crop] = {
    "xiaobaicai": Crop("xiaobaicai", "小白菜", 30 * 60, 10, 25, "#4F9D4F", "#8BD17C"),
    "huluobo": Crop("huluobo", "胡萝卜", 60 * 60, 25, 65, "#4F9D4F", "#E07B39"),
    "fanqie": Crop("fanqie", "番茄", 120 * 60, 45, 135, "#3F8F3F", "#E04A3F"),
    "yumi": Crop("yumi", "玉米", 240 * 60, 80, 260, "#5A9E3A", "#F2C94C"),
    "nangua": Crop("nangua", "南瓜", 480 * 60, 140, 480, "#4A8F3A", "#E8912D"),
}


@dataclass
class Plot:
    crop_id: str
    planted_at: float
    water_count: int = 0
    last_water_at: float = 0.0


@dataclass
class FarmState:
    coins: int = INITIAL_COINS
    unlocked_plots: int = INITIAL_PLOTS
    selected_crop: str = "xiaobaicai"
    total_harvests: int = 0
    total_income: int = 0
    warehouse: Dict[str, int] = field(default_factory=dict)
    plots: List[Optional[Plot]] = field(default_factory=lambda: [None] * MAX_PLOTS)

    def _require_index(self, index: int) -> None:
        if not 0 <= index < MAX_PLOTS:
            raise ValueError("地块不存在")

    def saved_seconds(self, plot: Plot) -> float:
        return plot.water_count * CROPS[plot.crop_id].grow_seconds * WATER_RATIO

    def elapsed(self, plot: Plot, now: float) -> float:
        return max(0.0, now - plot.planted_at) + self.saved_seconds(plot)

    def plant(self, index: int, crop_id: str, now: float) -> None:
        self._require_index(index)
        if index >= self.unlocked_plots:
            raise ValueError("这块地还没开垦")
        if self.plots[index] is not None:
            raise ValueError("这块地已经有作物了")
        crop = CROPS.get(crop_id)
        if crop is None:
            raise ValueError("未知作物")
        if self.coins < crop.seed_price:
            raise ValueError("金币不够")
        self.coins -= crop.seed_price
        self.plots[index] = Plot(crop_id, now)

    def remaining_seconds(self, index: int, now: float) -> float:
        self._require_index(index)
        plot = self.plots[index]
        if plot is None:
            return 0.0
        crop = CROPS.get(plot.crop_id)
        if crop is None:
            return 0.0
        return max(0.0, crop.grow_seconds - self.elapsed(plot, now))

    def progress(self, index: int, now: float) -> float:
        self._require_index(index)
        plot = self.plots[index]
        if plot is None:
            return 0.0
        crop = CROPS.get(plot.crop_id)
        if crop is None:
            return 0.0
        return min(1.0, self.elapsed(plot, now) / crop.grow_seconds)

    def is_mature(self, index: int, now: float) -> bool:
        self._require_index(index)
        return self.plots[index] is not None and self.remaining_seconds(index, now) == 0.0

    def can_water(self, index: int, now: float) -> bool:
        self._require_index(index)
        plot = self.plots[index]
        if plot is None:
            return False
        if self.remaining_seconds(index, now) == 0.0:
            return False
        if plot.water_count >= WATER_MAX:
            return False
        if now - plot.last_water_at < WATER_COOLDOWN:
            return False
        return True

    def water(self, index: int, now: float) -> None:
        self._require_index(index)
        plot = self.plots[index]
        if plot is None:
            raise ValueError("这块地没有作物")
        if self.remaining_seconds(index, now) == 0.0:
            raise ValueError("作物已经成熟")
        if plot.water_count >= WATER_MAX:
            raise ValueError("已经浇过 3 次水了")
        if now - plot.last_water_at < WATER_COOLDOWN:
            raise ValueError("浇水冷却中")
        plot.water_count += 1
        plot.last_water_at = now

    def harvest(self, index: int, now: float) -> str:
        self._require_index(index)
        plot = self.plots[index]
        if plot is None:
            raise ValueError("这块地没有作物")
        if self.remaining_seconds(index, now) > 0.0:
            raise ValueError("还没成熟")
        crop_id = plot.crop_id
        self.warehouse[crop_id] = self.warehouse.get(crop_id, 0) + 1
        self.plots[index] = None
        self.total_harvests += 1
        return crop_id

    def harvest_all(self, now: float) -> int:
        harvested = 0
        for index in range(MAX_PLOTS):
            if self.plots[index] is not None and self.remaining_seconds(index, now) == 0.0:
                self.harvest(index, now)
                harvested += 1
        return harvested
