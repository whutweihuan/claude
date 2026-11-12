# -*- coding: utf-8 -*-
"""奶牛牧场核心逻辑：成长、繁殖、挤奶、经济与存档。不依赖 Tkinter。"""

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union


class SaveUnreadableError(Exception):
    """存档存在，但当前无法读取（被占用、权限不足或其它 I/O 错误）。"""

GROWTH_YOUNG = 45 * 60
GROWTH_ADULT = 135 * 60
FEED_CREDIT = 900
FEED_MAX = 3
FEED_COOLDOWN = 600
MILK_INTERVAL = 1200
GESTATION = 3600
POSTPARTUM = 1800
CHEESE_MILK_COST = 3
CHEESE_TIME = 1200

INITIAL_COINS = 200
INITIAL_CAPACITY = 4
MAX_CAPACITY = 12
MAX_MACHINES = 3
CALF_PRICE = 150
FEED_PRICE = 25
MILK_PRICE = 15
CHEESE_PRICE = 75
COW_SELL_PRICES = {"calf": 80, "young": 160, "adult": 350}
MACHINE_PRICES = (300, 700, 1500)
CAPACITY_PRICES = (200, 400, 700, 1000, 1500, 2200, 3000, 4000)

NAME_POOL: Tuple[str, ...] = (
    "花花", "妞妞", "大壮", "团团", "默默", "糖糖",
    "豆豆", "云朵", "麦子", "布丁", "奶茶", "雪球",
)


@dataclass
class Cow:
    id: int
    name: str
    born_at: float
    fed_count: int = 0
    last_fed_at: float = 0.0
    last_milked_at: float = 0.0
    pregnant: bool = False
    due_at: float = 0.0
    recovery_until: float = 0.0


def effective_age(cow: Cow, now: float) -> float:
    """有效年龄（秒），系统时间回拨时按 0 夹逼。"""
    return max(0.0, now - cow.born_at) + cow.fed_count * FEED_CREDIT


def adult_at(cow: Cow) -> float:
    return cow.born_at + GROWTH_ADULT - cow.fed_count * FEED_CREDIT


def stage_of(cow: Cow, now: float) -> str:
    age = effective_age(cow, now)
    if age < GROWTH_YOUNG:
        return "calf"
    if age < GROWTH_ADULT:
        return "young"
    return "adult"


def ready_at(cow: Cow) -> float:
    """最早可受孕时刻：产后休养与成年时刻中较晚者。"""
    return max(cow.recovery_until, adult_at(cow))


def udder_ready(cow: Cow, now: float) -> bool:
    if stage_of(cow, now) != "adult":
        return False
    anchor = max(cow.last_milked_at, adult_at(cow))
    return now - anchor >= MILK_INTERVAL


@dataclass
class GameState:
    coins: int = INITIAL_COINS
    capacity: int = INITIAL_CAPACITY
    cows: List[Cow] = None  # type: ignore[assignment]
    machines: List[Optional[float]] = None  # type: ignore[assignment]
    warehouse: Dict[str, int] = None  # type: ignore[assignment]
    feed_count: int = 0
    total_income: int = 0
    total_births: int = 0
    next_cow_id: int = 1
    settled_until: float = 0.0

    def __post_init__(self) -> None:
        if self.cows is None:
            self.cows = []
        if self.machines is None:
            self.machines = []
        if self.warehouse is None:
            self.warehouse = {}

    def stock(self, item: str) -> int:
        return self.warehouse.get(item, 0)

    def catch_up(self, now: float) -> None:
        """把所有时间驱动事件结算到 now。

        事件 = 孕妇的 due_at ∪ 未孕牛 max(ready_at, cursor)。事件时间一律锚定
        事件自身（生产 born_at=T、休养 =T+POSTPARTUM、受孕 due=T+GESTATION），
        因此“离线一跳”与“在线逐步”得到同一世界。同一 cursor 上排队无位的牛
        记入 passed_ids，仅在 cursor 前进后重新入队 → 循环必然终止。
        """
        self._settle_machines(now)
        cursor = self.settled_until
        passed_ids: set = set()
        while True:
            candidates = []
            for cow in self.cows:
                if cow.pregnant:
                    if cow.due_at <= now:
                        candidates.append(cow.due_at)
                else:
                    t = ready_at(cow)
                    if t <= now and cow.id not in passed_ids:
                        candidates.append(max(t, cursor))
            if not candidates:
                break
            moment = min(candidates)
            mothers = [c for c in self.cows if c.pregnant and c.due_at == moment]
            for mother in mothers:
                self._give_birth(mother, moment)
            if moment > cursor:
                cursor = moment
                passed_ids = set()
            self.conception_pass(moment)
            for cow in self.cows:
                if not cow.pregnant and ready_at(cow) <= cursor:
                    passed_ids.add(cow.id)
        self.settled_until = max(self.settled_until, cursor, now)
        self.conception_pass(self.settled_until)

    def _give_birth(self, mother: Cow, at: float) -> None:
        calf = Cow(
            id=self.next_cow_id,
            name=self.next_unused_name(),
            born_at=at,
            last_milked_at=at,
        )
        self.next_cow_id += 1
        self.cows.append(calf)
        self.total_births += 1
        mother.pregnant = False
        mother.due_at = 0.0
        mother.recovery_until = at + POSTPARTUM

    def _settle_machines(self, now: float) -> None:
        for i, started in enumerate(self.machines):
            if started is not None and started + CHEESE_TIME <= now:
                self.warehouse["cheese"] = self.stock("cheese") + 1
                self.machines[i] = None

    def process(self, machine_index: int, now: float) -> None:
        self.catch_up(now)
        if not 0 <= machine_index < len(self.machines):
            raise ValueError("没有这台加工器")
        if self.machines[machine_index] is not None:
            raise ValueError("加工器正忙")
        if self.stock("milk") < CHEESE_MILK_COST:
            raise ValueError("牛奶不够")
        self.warehouse["milk"] = self.stock("milk") - CHEESE_MILK_COST
        self.machines[machine_index] = now

    def process_all(self, now: float) -> int:
        started = 0
        for i in range(len(self.machines)):
            try:
                self.process(i, now)
            except ValueError:
                continue
            started += 1
        return started

    def find_cow(self, cow_id: int) -> Optional[Cow]:
        for cow in self.cows:
            if cow.id == cow_id:
                return cow
        return None

    def milk(self, cow_id: int, now: float) -> None:
        self.catch_up(now)
        cow = self.find_cow(cow_id)
        if cow is None:
            raise ValueError("没有这头牛")
        if not udder_ready(cow, now):
            raise ValueError("这头牛还没蓄满奶")
        self.warehouse["milk"] = self.stock("milk") + 1
        cow.last_milked_at = now

    def milk_all(self, now: float) -> int:
        milked = 0
        for cow in list(self.cows):
            if udder_ready(cow, now):
                self.milk(cow.id, now)
                milked += 1
        return milked

    def sell_stock(self, item: str) -> int:
        prices = {"milk": MILK_PRICE, "cheese": CHEESE_PRICE}
        if item not in prices:
            raise ValueError("未知商品")
        count = self.stock(item)
        if count <= 0:
            return 0
        amount = count * prices[item]
        self.coins += amount
        self.total_income += amount
        self.warehouse.pop(item, None)
        return amount

    def sell_all_stock(self) -> int:
        total = 0
        for item in ("milk", "cheese"):
            total += self.sell_stock(item)
        return total

    def stock_value(self) -> int:
        return (self.stock("milk") * MILK_PRICE
                + self.stock("cheese") * CHEESE_PRICE)

    def next_unused_name(self) -> str:
        used = {cow.name for cow in self.cows}
        for name in NAME_POOL:
            if name not in used:
                return name
        return "小牛 {}".format(self.next_cow_id)

    def conception_pass(self, at: float) -> None:
        """空位补位：ready_at ≤ at 的未孕牛按 (ready_at, id) 先进先出受孕。"""
        waiting = [c for c in self.cows
                   if not c.pregnant and ready_at(c) <= at]
        waiting.sort(key=lambda c: (ready_at(c), c.id))
        for cow in waiting:
            if not free_slot_left(self):
                break
            cow.pregnant = True
            cow.due_at = at + GESTATION

    def buy_calf(self, now: float) -> int:
        self.catch_up(now)
        if not free_slot_left(self):
            raise ValueError("牧场满了")
        if self.coins < CALF_PRICE:
            raise ValueError("金币不够")
        self.coins -= CALF_PRICE
        cow = Cow(
            id=self.next_cow_id,
            name=self.next_unused_name(),
            born_at=now,
            last_milked_at=now,
        )
        self.next_cow_id += 1
        self.cows.append(cow)
        return cow.id

    def sell_cow(self, cow_id: int, now: float) -> int:
        self.catch_up(now)
        cow = self.find_cow(cow_id)
        if cow is None:
            raise ValueError("没有这头牛")
        price = COW_SELL_PRICES[stage_of(cow, now)]
        self.cows.remove(cow)
        self.coins += price
        self.total_income += price
        self.conception_pass(now)  # 腾位即补位
        return price

    def buy_feed(self) -> int:
        if self.coins < FEED_PRICE:
            raise ValueError("金币不够")
        self.coins -= FEED_PRICE
        self.feed_count += 1
        return self.feed_count

    def buy_machine(self) -> None:
        if len(self.machines) >= MAX_MACHINES:
            raise ValueError("加工器已达上限")
        price = MACHINE_PRICES[len(self.machines)]
        if self.coins < price:
            raise ValueError("金币不够")
        self.coins -= price
        self.machines.append(None)

    def expand_capacity(self) -> None:
        if self.capacity >= MAX_CAPACITY:
            raise ValueError("牧场已扩建到上限")
        price = CAPACITY_PRICES[self.capacity - INITIAL_CAPACITY]
        if self.coins < price:
            raise ValueError("金币不够")
        self.coins -= price
        self.capacity += 1

    def can_feed(self, cow_id: int, now: float) -> bool:
        cow = self.find_cow(cow_id)
        if cow is None or stage_of(cow, now) == "adult":
            return False
        if cow.fed_count >= FEED_MAX or self.feed_count <= 0:
            return False
        return now - cow.last_fed_at >= FEED_COOLDOWN

    def feed(self, cow_id: int, now: float) -> None:
        self.catch_up(now)
        cow = self.find_cow(cow_id)
        if cow is None:
            raise ValueError("没有这头牛")
        if stage_of(cow, now) == "adult":
            raise ValueError("这头牛已经成年")
        if cow.fed_count >= FEED_MAX:
            raise ValueError("这头牛最多喂 3 次")
        if now - cow.last_fed_at < FEED_COOLDOWN:
            raise ValueError("投喂间隔不足 10 分钟")
        if self.feed_count <= 0:
            raise ValueError("没有高级饲料")
        self.feed_count -= 1
        cow.fed_count += 1
        cow.last_fed_at = now

    def to_dict(self) -> dict:
        return {
            "version": 1,
            "coins": self.coins,
            "capacity": self.capacity,
            "next_cow_id": self.next_cow_id,
            "cows": [
                {
                    "id": c.id, "name": c.name, "born_at": c.born_at,
                    "fed_count": c.fed_count, "last_fed_at": c.last_fed_at,
                    "last_milked_at": c.last_milked_at, "pregnant": c.pregnant,
                    "due_at": c.due_at, "recovery_until": c.recovery_until,
                }
                for c in self.cows
            ],
            "machines": list(self.machines),
            "warehouse": {k: v for k, v in self.warehouse.items()
                          if k in ("milk", "cheese") and v > 0},
            "feed_count": self.feed_count,
            "total_income": self.total_income,
            "total_births": self.total_births,
            "settled_until": self.settled_until,
            "saved_at": time.time(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GameState":
        if not isinstance(data, dict):
            raise ValueError("存档格式不正确")
        if not (_is_plain_int(data.get("coins")) and data["coins"] >= 0):
            raise ValueError("存档金币不合法")
        if not (_is_plain_int(data.get("capacity"))
                and INITIAL_CAPACITY <= data["capacity"] <= MAX_CAPACITY):
            raise ValueError("存档容量不合法")
        if not (_is_plain_int(data.get("next_cow_id")) and data["next_cow_id"] >= 1):
            raise ValueError("存档牛编号不合法")
        raw_cows = data.get("cows")
        if not isinstance(raw_cows, list):
            raise ValueError("存档牛群不合法")
        cows: List[Cow] = []
        seen_ids = set()
        for raw in raw_cows:
            if not isinstance(raw, dict):
                raise ValueError("存档牛不合法")
            cow_id = raw.get("id")
            if not (_is_plain_int(cow_id) and cow_id >= 1) or cow_id in seen_ids:
                raise ValueError("存档牛 id 不合法")
            seen_ids.add(cow_id)
            name = raw.get("name")
            if not (isinstance(name, str) and name):
                raise ValueError("存档牛名字不合法")
            for key in ("born_at", "last_fed_at", "last_milked_at",
                        "due_at", "recovery_until"):
                if not _is_number(raw.get(key)):
                    raise ValueError("存档牛时间不合法")
            fed_count = raw.get("fed_count")
            if not (_is_plain_int(fed_count) and 0 <= fed_count <= FEED_MAX):
                raise ValueError("存档喂食次数不合法")
            pregnant = raw.get("pregnant")
            if not isinstance(pregnant, bool):
                raise ValueError("存档怀孕状态不合法")
            cows.append(Cow(
                id=cow_id, name=name, born_at=float(raw["born_at"]),
                fed_count=fed_count, last_fed_at=float(raw["last_fed_at"]),
                last_milked_at=float(raw["last_milked_at"]), pregnant=pregnant,
                due_at=float(raw["due_at"]), recovery_until=float(raw["recovery_until"]),
            ))
        raw_machines = data.get("machines")
        if not isinstance(raw_machines, list) or len(raw_machines) > MAX_MACHINES:
            raise ValueError("存档加工器不合法")
        machines: List[Optional[float]] = []
        for item in raw_machines:
            if item is None:
                machines.append(None)
            elif _is_number(item) and item >= 0:
                machines.append(float(item))
            else:
                raise ValueError("存档加工器不合法")
        raw_warehouse = data.get("warehouse")
        if not isinstance(raw_warehouse, dict):
            raise ValueError("存档仓库不合法")
        warehouse: Dict[str, int] = {}
        for key in ("milk", "cheese"):
            value = raw_warehouse.get(key, 0)
            if not (_is_plain_int(value) and value >= 0):
                raise ValueError("存档仓库不合法")
            if value > 0:
                warehouse[key] = value
        for key in ("feed_count", "total_income", "total_births"):
            value = data.get(key)
            if not (_is_plain_int(value) and value >= 0):
                raise ValueError("存档计数不合法")
        if not _is_number(data.get("settled_until")):
            raise ValueError("存档结算时间不合法")
        return cls(
            coins=data["coins"], capacity=data["capacity"], cows=cows,
            machines=machines, warehouse=warehouse, feed_count=data["feed_count"],
            total_income=data["total_income"], total_births=data["total_births"],
            next_cow_id=data["next_cow_id"], settled_until=float(data["settled_until"]),
        )


def _is_plain_int(value) -> bool:
    return type(value) is int


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def save_state(state: GameState, path: Union[str, Path]) -> None:
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(state.to_dict(), fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _backup_corrupt_save(path: Path) -> None:
    backup = path.with_name(
        "{}.corrupt-{}.json".format(path.stem, int(time.time()))
    )
    try:
        os.replace(path, backup)
    except OSError:
        pass


def load_state(path: Union[str, Path]) -> Tuple[GameState, Optional[str]]:
    path = Path(path)
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return new_game(time.time()), None
    except ValueError:
        _backup_corrupt_save(path)
        return new_game(time.time()), "存档损坏，已开始新的一局"
    except OSError as exc:
        raise SaveUnreadableError(
            "读取存档失败：{}；本次不会保存".format(exc)
        )
    try:
        return GameState.from_dict(data), None
    except ValueError:
        _backup_corrupt_save(path)
        return new_game(time.time()), "存档损坏，已开始新的一局"


def free_slot_left(state: GameState) -> bool:
    """预留空位闸门：牛数 + 孕妇数 < 容量，才允许新生命入场。"""
    return len(state.cows) + sum(1 for c in state.cows if c.pregnant) < state.capacity


def new_game(now: float) -> GameState:
    first_cow = Cow(
        id=1,
        name="花花",
        born_at=now - 10800,
        last_milked_at=now,
    )
    return GameState(
        coins=INITIAL_COINS,
        capacity=INITIAL_CAPACITY,
        cows=[first_cow],
        machines=[],
        warehouse={},
        feed_count=0,
        next_cow_id=2,
        settled_until=now,
    )
