# -*- coding: utf-8 -*-
"""奶牛牧场核心逻辑：成长、繁殖、挤奶、经济与存档。不依赖 Tkinter。"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

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
        """把所有时间驱动事件结算到 now（任务 5/6 扩展）。"""
        if now > self.settled_until:
            self.settled_until = now

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
