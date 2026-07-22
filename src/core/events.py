"""Event log — sim-wide ring buffer of typed hostility-precursor and observability events.

Plan 4 Task 2. Owned by Simulation, updated once per tick with the current sim_time so that
deep call sites (e.g. GatherAndDeliverTask.prepare, which has no direct sim_time access) can
self-timestamp via record(). Later rungs (Task 3 theft, Task 4+ attack/death) append new
event_type values here — this module is not touched again structurally, only extended.
"""
import collections
import dataclasses
from typing import Deque, List, Optional

from pygame.math import Vector2

from . import config


@dataclasses.dataclass(frozen=True)
class SimEvent:
    sim_time: float
    event_type: str                       # "claim_contention", later "theft", "attack", "death"
    faction_id: Optional[int]
    other_faction_id: Optional[int] = None
    position: Optional[Vector2] = None
    resource_type: Optional[str] = None   # ResourceType.name, kept as str to avoid coupling
    detail: str = ""


class EventLog:
    """Ring buffer (bounded deque) of SimEvent. Owned by Simulation; sim_time updated once/tick."""

    def __init__(self, max_events: Optional[int] = None):
        self._events: Deque[SimEvent] = collections.deque(
            maxlen=max_events or config.EVENT_LOG_MAX_SIZE
        )
        self._current_sim_time: float = 0.0

    def update(self, sim_time: float) -> None:
        self._current_sim_time = sim_time

    def record(self, event_type: str, **fields) -> None:
        self._events.append(SimEvent(sim_time=self._current_sim_time, event_type=event_type, **fields))

    def recent(self, n: int = 5) -> List[SimEvent]:
        """Newest-first, up to n events."""
        return list(self._events)[-n:][::-1]

    def count_since(self, event_type: str, since_sim_time: float) -> int:
        return sum(1 for e in self._events if e.event_type == event_type and e.sim_time >= since_sim_time)
