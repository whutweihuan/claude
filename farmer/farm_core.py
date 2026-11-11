# -*- coding: utf-8 -*-
"""小菜园核心逻辑：作物、地块、经济与存档。不依赖 Tkinter。"""

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

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

    def sell(self, crop_id: str) -> int:
        count = self.warehouse.get(crop_id, 0)
        crop = CROPS.get(crop_id)
        if count <= 0 or crop is None:
            return 0
        amount = count * crop.sell_price
        self.coins += amount
        self.total_income += amount
        self.warehouse.pop(crop_id, None)
        return amount

    def sell_all(self) -> int:
        total = 0
        for crop_id in list(self.warehouse.keys()):
            total += self.sell(crop_id)
        return total

    def warehouse_value(self) -> int:
        return sum(
            count * CROPS[crop_id].sell_price
            for crop_id, count in self.warehouse.items()
            if crop_id in CROPS and count > 0
        )

    def buy_land(self) -> int:
        if self.unlocked_plots >= MAX_PLOTS:
            raise ValueError("土地已经全部开垦")
        price = LAND_PRICES[self.unlocked_plots - INITIAL_PLOTS]
        if self.coins < price:
            raise ValueError("金币不够")
        self.coins -= price
        self.unlocked_plots += 1
        return self.unlocked_plots

    def to_dict(self) -> dict:
        return {
            "version": 1,
            "coins": self.coins,
            "unlocked_plots": self.unlocked_plots,
            "selected_crop": self.selected_crop,
            "total_harvests": self.total_harvests,
            "total_income": self.total_income,
            "warehouse": dict(self.warehouse),
            "plots": [
                None if plot is None else {
                    "crop": plot.crop_id,
                    "planted_at": plot.planted_at,
                    "water_count": plot.water_count,
                    "last_water_at": plot.last_water_at,
                }
                for plot in self.plots
            ],
            "saved_at": time.time(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FarmState":
        if not isinstance(data, dict):
            raise ValueError("存档格式不正确")

        coins = data.get("coins")
        if not (_is_plain_int(coins) and coins >= 0):
            raise ValueError("存档金币不合法")

        unlocked = data.get("unlocked_plots")
        if not (_is_plain_int(unlocked) and INITIAL_PLOTS <= unlocked <= MAX_PLOTS):
            raise ValueError("存档土地数量不合法")

        raw_plots = data.get("plots")
        if not isinstance(raw_plots, list) or len(raw_plots) != MAX_PLOTS:
            raise ValueError("存档地块不合法")

        state = cls(coins=coins, unlocked_plots=unlocked)
        for index, raw in enumerate(raw_plots):
            if raw is None:
                continue
            if not isinstance(raw, dict):
                raise ValueError("存档地块不合法")
            crop_id = raw.get("crop")
            planted_at = raw.get("planted_at")
            if not isinstance(crop_id, str) or not _is_number(planted_at):
                raise ValueError("存档地块不合法")
            if crop_id not in CROPS:
                continue
            water_count = raw.get("water_count", 0)
            if not (_is_plain_int(water_count) and 0 <= water_count <= WATER_MAX):
                raise ValueError("存档浇水次数不合法")
            last_water_at = raw.get("last_water_at", 0.0)
            if not _is_number(last_water_at):
                raise ValueError("存档浇水时间不合法")
            state.plots[index] = Plot(
                crop_id, float(planted_at), water_count, float(last_water_at)
            )

        raw_warehouse = data.get("warehouse", {})
        if not isinstance(raw_warehouse, dict):
            raise ValueError("存档仓库不合法")
        for crop_id, count in raw_warehouse.items():
            if not (_is_plain_int(count) and count >= 0):
                raise ValueError("存档仓库不合法")
            if crop_id in CROPS and count > 0:
                state.warehouse[crop_id] = count

        selected = data.get("selected_crop", "xiaobaicai")
        if isinstance(selected, str) and selected in CROPS:
            state.selected_crop = selected
        state.total_harvests = _non_negative_or_zero(data.get("total_harvests", 0))
        state.total_income = _non_negative_or_zero(data.get("total_income", 0))
        return state


def _is_plain_int(value) -> bool:
    return type(value) is int


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _non_negative_or_zero(value) -> int:
    if _is_plain_int(value) and value >= 0:
        return value
    return 0


def save_state(state: FarmState, path: Union[str, Path]) -> None:
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(state.to_dict(), fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_state(path: Union[str, Path]) -> Tuple[FarmState, Optional[str]]:
    path = Path(path)
    if not path.exists():
        return FarmState(), None
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return FarmState.from_dict(data), None
    except (OSError, ValueError, json.JSONDecodeError):
        backup = path.with_name(
            "{}.corrupt-{}.json".format(path.stem, int(time.time()))
        )
        try:
            os.replace(path, backup)
        except OSError:
            pass
        return FarmState(), "存档损坏，已开始新的一局"
