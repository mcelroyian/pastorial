"""FactionContext — per-faction, per-planning-tick derived snapshot.

Built fresh each 5s planning tick (see TaskManager._build_faction_context) and consumed by
Task.compute_score. Distinct lifecycle from Faction (a static registry dataclass), hence its
own module — Task 2/3/4 add behavior that populates recent_deaths/threat_level; this dataclass
shape is meant to not need to change again then.
"""
import dataclasses
from typing import Dict

from pygame.math import Vector2

from ..resources.resource_types import ResourceType

_EPSILON = 1e-6


@dataclasses.dataclass
class FactionContext:
    faction_id: int
    sim_time: float

    stock: Dict[ResourceType, int]               # current stock by type (faction-scoped)
    consumption_rate: Dict[ResourceType, float]   # units/sec, rolling recent rate
    agents_alive: int
    recent_deaths: int                            # count within the rolling window
    food_deficit_seconds: float                   # stock[BREAD] / consumption_rate[BREAD] —
                                                    # the master scarcity signal
    home_centroid: Vector2                        # faction.home_region center, grid coords
    threat_level: float = 0.0                     # decaying hostility accumulator — inert
                                                    # (0.0) until Task 4

    @staticmethod
    def compute_food_deficit_seconds(stock: Dict[ResourceType, int],
                                      consumption_rate: Dict[ResourceType, float],
                                      cap: float) -> float:
        rate = consumption_rate.get(ResourceType.BREAD, 0.0)
        bread_stock = stock.get(ResourceType.BREAD, 0)
        if rate <= _EPSILON:
            return cap if bread_stock > 0 else 0.0
        return bread_stock / rate
