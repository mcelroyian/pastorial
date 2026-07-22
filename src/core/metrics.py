"""SimMetrics — lightweight event-based metrics for balance analysis."""
import collections
import logging
from typing import Dict, List, Tuple

from src.resources.resource_types import ResourceType


class SimMetrics:
    """
    Owned by Simulation. Records coarse-grained counters and periodic snapshots.
    Instrument via metrics.record(event_name, **fields).
    """

    SNAPSHOT_INTERVAL = 10.0  # sim-seconds between time-series samples

    def __init__(self):
        self.logger = logging.getLogger(__name__)

        # Cumulative counters keyed by ResourceType
        self.gathered: Dict[ResourceType, int] = collections.defaultdict(int)
        self.produced: Dict[ResourceType, int] = collections.defaultdict(int)
        self.consumed: Dict[ResourceType, int] = collections.defaultdict(int)

        # Per-faction cumulative counters keyed by (faction_id, ResourceType)
        self.faction_produced: Dict[int, Dict[ResourceType, int]] = collections.defaultdict(lambda: collections.defaultdict(int))
        self.faction_consumed: Dict[int, Dict[ResourceType, int]] = collections.defaultdict(lambda: collections.defaultdict(int))
        self.faction_deaths: Dict[int, int] = collections.defaultdict(int)

        # Task outcome counters keyed by task_type_name
        self.tasks_completed: Dict[str, int] = collections.defaultdict(int)
        self.tasks_failed: Dict[str, int] = collections.defaultdict(int)

        self.agent_deaths: int = 0
        self.agent_count: int = 0  # updated each snapshot

        # Time series: list of (sim_time, snapshot_dict)
        self.snapshots: List[Tuple[float, dict]] = []
        self._next_snapshot_at: float = self.SNAPSHOT_INTERVAL

        # Rolling windows for "recent" queries (Plan 4 Task 1 — FactionContext inputs).
        # Entries: (sim_time, faction_id, resource_type, quantity) / (sim_time, faction_id).
        # Pruned lazily at query time — no separate decay tick needed.
        self._current_sim_time: float = 0.0
        self._consumption_events: collections.deque = collections.deque()
        self._death_events: collections.deque = collections.deque()

    # ------------------------------------------------------------------
    # Event API
    # ------------------------------------------------------------------

    def record(self, event: str, **fields) -> None:
        faction_id = fields.get("faction_id")
        if event == "gathered":
            self.gathered[fields["resource_type"]] += fields.get("quantity", 1)
        elif event == "produced":
            qty = fields.get("quantity", 1)
            self.produced[fields["resource_type"]] += qty
            if faction_id is not None:
                self.faction_produced[faction_id][fields["resource_type"]] += qty
        elif event == "consumed":
            qty = fields.get("quantity", 1)
            self.consumed[fields["resource_type"]] += qty
            if faction_id is not None:
                self.faction_consumed[faction_id][fields["resource_type"]] += qty
                self._consumption_events.append(
                    (self._current_sim_time, faction_id, fields["resource_type"], qty)
                )
        elif event == "task_completed":
            self.tasks_completed[fields["task_type"]] += 1
        elif event == "task_failed":
            self.tasks_failed[fields["task_type"]] += 1
        elif event == "agent_death":
            self.agent_deaths += 1
            if faction_id is not None:
                self.faction_deaths[faction_id] += 1
                self._death_events.append((self._current_sim_time, faction_id))
            self.logger.info(f"[metrics] agent_death: {fields.get('agent_name', '?')}")
        else:
            self.logger.debug(f"[metrics] unhandled event '{event}': {fields}")

    # Retention horizon for the rolling deques — independent of any single query's `window`
    # argument, so pruning stays correct even if callers query with different window sizes.
    _EVENT_RETENTION_SECONDS = 300.0

    def _prune_events(self) -> None:
        cutoff = self._current_sim_time - self._EVENT_RETENTION_SECONDS
        while self._consumption_events and self._consumption_events[0][0] < cutoff:
            self._consumption_events.popleft()
        while self._death_events and self._death_events[0][0] < cutoff:
            self._death_events.popleft()

    def recent_consumption_rate(self, faction_id: int, resource_type: ResourceType,
                                 window: float = 60.0) -> float:
        """Gross units/sec of resource_type consumed by faction_id within the trailing window.

        Gross, not net-of-production — a faction whose bakery output exactly matches its
        eating rate still has a real, nonzero consumption rate even though stock is flat.
        """
        self._prune_events()
        cutoff = self._current_sim_time - window
        total = sum(
            qty for t, fid, rt, qty in self._consumption_events
            if t >= cutoff and fid == faction_id and rt == resource_type
        )
        divisor = min(window, self._current_sim_time) or 1.0
        return total / divisor

    def recent_deaths(self, faction_id: int, window: float = 60.0) -> int:
        """Count of faction_id's deaths within the trailing window."""
        self._prune_events()
        cutoff = self._current_sim_time - window
        return sum(1 for t, fid in self._death_events if t >= cutoff and fid == faction_id)

    def update(self, sim_time: float, resource_manager, agent_manager, factions=None) -> None:
        """Call once per sim tick to emit periodic snapshots."""
        self._current_sim_time = sim_time
        if sim_time < self._next_snapshot_at:
            return
        self._next_snapshot_at += self.SNAPSHOT_INTERVAL

        stock = {rt.name: resource_manager.get_global_resource_quantity(rt)
                 for rt in ResourceType}
        self.agent_count = len(agent_manager.agents)

        snap = {
            "sim_time": round(sim_time, 1),
            "agent_count": self.agent_count,
            "stock": stock,
            "gathered": {k.name: v for k, v in self.gathered.items()},
            "produced": {k.name: v for k, v in self.produced.items()},
            "consumed": {k.name: v for k, v in self.consumed.items()},
        }

        if factions:
            snap["faction_stock"] = {
                f.faction_id: {
                    rt.name: resource_manager.get_faction_resource_quantity(f.faction_id, rt)
                    for rt in ResourceType
                }
                for f in factions
            }
            snap["faction_agents"] = {
                f.faction_id: sum(1 for a in agent_manager.agents if a.owner_faction_id == f.faction_id)
                for f in factions
            }

        self.snapshots.append((sim_time, snap))

    # ------------------------------------------------------------------
    # Summary helper (used by balance_report.py)
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        return {
            "agent_deaths": self.agent_deaths,
            "final_agent_count": self.agent_count,
            "gathered": dict(self.gathered),
            "produced": dict(self.produced),
            "consumed": dict(self.consumed),
            "tasks_completed": dict(self.tasks_completed),
            "tasks_failed": dict(self.tasks_failed),
            "faction_deaths": dict(self.faction_deaths),
            "faction_produced": {k: dict(v) for k, v in self.faction_produced.items()},
            "faction_consumed": {k: dict(v) for k, v in self.faction_consumed.items()},
        }
