"""Tests for SimMetrics."""
from src.core.simulation import Simulation
from src.resources.resource_types import ResourceType

_DT = 1 / 60
_TICKS = 6000  # 100 sim-seconds


def _run(seed=42, ticks=_TICKS):
    sim = Simulation(seed=seed)
    for _ in range(ticks):
        sim.update(_DT)
    return sim


def test_metrics_snapshots_taken():
    sim = _run(ticks=_TICKS)
    # At 100 sim-seconds with 10-second interval, expect ~10 snapshots
    assert len(sim.metrics.snapshots) >= 5


def test_metrics_tasks_completed_nonzero():
    sim = _run(ticks=_TICKS)
    total = sum(sim.metrics.tasks_completed.values())
    assert total > 0, "No tasks completed — metrics not wired"


def test_bread_consumed_after_eating():
    """After planting bread and running long enough, BREAD consumed > 0."""
    from src.resources.storage_point import StoragePoint
    import pygame

    sim = Simulation(seed=1)

    # Ensure a bread storage exists and has bread
    bread_sp = None
    for sp in sim.resource_manager.storage_points:
        if sp.accepted_resource_types and ResourceType.BREAD in sp.accepted_resource_types:
            bread_sp = sp
            break
    if bread_sp is None:
        for gx in range(sim.grid.width_in_cells):
            for gy in range(sim.grid.height_in_cells):
                if sim.grid.is_area_free(gx, gy, 1, 1):
                    bread_sp = StoragePoint(
                        position=pygame.math.Vector2(gx, gy),
                        overall_capacity=100,
                        accepted_resource_types=[ResourceType.BREAD],
                    )
                    sim.resource_manager.add_storage_point(bread_sp)
                    sim.grid.update_occupancy(bread_sp, gx, gy, 1, 1, is_placing=True)
                    break
            if bread_sp:
                break

    # Seed with plenty of bread and make agents hungry
    bread_sp.stored_resources[ResourceType.BREAD] = 50
    for agent in sim.agent_manager.agents:
        agent.needs.hunger = 0.1  # critical

    for _ in range(6000):
        sim.update(_DT)
        # Refill bread each tick so it doesn't run out
        bread_sp.stored_resources[ResourceType.BREAD] = max(
            bread_sp.stored_resources.get(ResourceType.BREAD, 0), 20
        )

    assert sim.metrics.consumed.get(ResourceType.BREAD, 0) > 0, (
        "BREAD should have been consumed (metrics.consumed[BREAD] == 0)"
    )
