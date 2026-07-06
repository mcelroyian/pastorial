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

        # Task outcome counters keyed by task_type_name
        self.tasks_completed: Dict[str, int] = collections.defaultdict(int)
        self.tasks_failed: Dict[str, int] = collections.defaultdict(int)

        self.agent_deaths: int = 0
        self.agent_count: int = 0  # updated each snapshot

        # Time series: list of (sim_time, snapshot_dict)
        self.snapshots: List[Tuple[float, dict]] = []
        self._next_snapshot_at: float = self.SNAPSHOT_INTERVAL

    # ------------------------------------------------------------------
    # Event API
    # ------------------------------------------------------------------

    def record(self, event: str, **fields) -> None:
        if event == "gathered":
            self.gathered[fields["resource_type"]] += fields.get("quantity", 1)
        elif event == "produced":
            self.produced[fields["resource_type"]] += fields.get("quantity", 1)
        elif event == "consumed":
            self.consumed[fields["resource_type"]] += fields.get("quantity", 1)
        elif event == "task_completed":
            self.tasks_completed[fields["task_type"]] += 1
        elif event == "task_failed":
            self.tasks_failed[fields["task_type"]] += 1
        elif event == "agent_death":
            self.agent_deaths += 1
            self.logger.info(f"[metrics] agent_death: {fields.get('agent_name', '?')}")
        else:
            self.logger.debug(f"[metrics] unhandled event '{event}': {fields}")

    def update(self, sim_time: float, resource_manager, agent_manager) -> None:
        """Call once per sim tick to emit periodic snapshots."""
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
        }
