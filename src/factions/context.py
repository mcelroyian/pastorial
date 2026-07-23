"""FactionContext — per-faction, per-planning-tick derived snapshot.

Built fresh each 5s planning tick (see TaskManager._build_faction_context) and consumed by
Task.compute_score. Distinct lifecycle from Faction (a static registry dataclass), hence its
own module — Task 2/3/4 add behavior that populates recent_deaths/threat_level; this dataclass
shape is meant to not need to change again then.
"""
import dataclasses
from typing import Dict, Optional, TYPE_CHECKING

from pygame.math import Vector2

from ..core import config
from ..resources.resource_types import ResourceType

if TYPE_CHECKING:
    from ..core.events import EventLog

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
    threat_level: float = 0.0                     # decaying hostility accumulator, computed
                                                    # lazily each tick from EventLog (Task 4) —
                                                    # no stored state, see compute_threat_level

    @staticmethod
    def compute_food_deficit_seconds(stock: Dict[ResourceType, int],
                                      consumption_rate: Dict[ResourceType, float],
                                      cap: float) -> float:
        rate = consumption_rate.get(ResourceType.BREAD, 0.0)
        bread_stock = stock.get(ResourceType.BREAD, 0)
        if rate <= _EPSILON:
            return cap if bread_stock > 0 else 0.0
        return bread_stock / rate

    @staticmethod
    def compute_threat_level(events: Optional['EventLog'], faction_id: int, sim_time: float) -> float:
        """Age-weighted decay sum over EventLog entries where this faction was the victim.

        Deliberately lazy/query-time (like SimMetrics's rolling windows) rather than a stored,
        incrementally-decayed accumulator — nothing needs to persist across ticks, and this
        stays correct even if a tick is skipped. theft (other_faction_id == faction_id) is
        weighted far above claim_contention (faction_id == faction_id, i.e. "my preferred node
        was denied to me") per the plan doc ("theft high, contention low").

        The contention component is additionally capped (THREAT_CONTENTION_CAP), separately
        from its per-event weight: wild-node contention is ambient and near-continuous in any
        scenario with overlapping territory (empirically ~400 denial events per 500 sim-seconds
        in ASYMMETRIC — see docs/plan-4-progress.md), so an uncapped decay sum over it saturates
        threat_level from ordinary foraging alone, well before any real hostility (theft) occurs
        — this was caught by test_theft.py regressing (guards were forming and blocking the one
        raid the test depends on, purely from contention, at ~t=30s). Capping keeps contention a
        genuinely minor, bounded nudge; theft remains the actual trigger for guard-worthy threat.
        """
        if events is None or config.THREAT_DECAY_HALFLIFE_SECONDS <= 0:
            return 0.0
        cutoff = sim_time - config.THREAT_LOOKBACK_SECONDS
        theft_total = 0.0
        contention_total = 0.0
        for event in events.since(cutoff):
            if event.event_type == "theft" and event.other_faction_id == faction_id:
                weight = config.THREAT_WEIGHT_THEFT
            elif event.event_type == "claim_contention" and event.faction_id == faction_id:
                weight = config.THREAT_WEIGHT_CONTENTION
            else:
                continue
            age = max(0.0, sim_time - event.sim_time)
            decayed = weight * (0.5 ** (age / config.THREAT_DECAY_HALFLIFE_SECONDS))
            if event.event_type == "theft":
                theft_total += decayed
            else:
                contention_total += decayed
        return theft_total + min(contention_total, config.THREAT_CONTENTION_CAP)
