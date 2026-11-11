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
