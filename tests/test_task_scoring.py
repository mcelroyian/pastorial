"""Tests for Plan 4 Task 1 utility scoring (relative ordering only, per spec)."""
from src.core.simulation import Simulation
from src.core import config
from src.resources.resource_types import ResourceType
from src.tasks.task import GatherAndDeliverTask, DeliverWheatToMillTask

_DT = 1 / 60


def _set_stock(sim, faction_id, resource_type, quantity):
    """Directly overwrite this faction's stock for resource_type (first matching storage point)."""
    for sp in sim.resource_manager.storage_points_for(faction_id):
        if resource_type in sp.accepted_resource_types:
            sp.stored_resources[resource_type] = quantity
            return
    raise AssertionError(f"No storage point accepts {resource_type} for faction {faction_id}")


def test_low_flour_full_wheat_processing_outscores_gathering():
    sim = Simulation(seed=42)
    fid = sim.factions[0].faction_id
    tm = sim.factions[0].task_manager

    _set_stock(sim, fid, ResourceType.FLOUR_POWDER, 0)    # low flour -> drives process urgency high
    _set_stock(sim, fid, ResourceType.WHEAT, 200)          # full wheat -> drives gather urgency low
    ctx = tm._build_faction_context()

    gather_wheat = GatherAndDeliverTask(priority=0, resource_type_to_gather=ResourceType.WHEAT,
                                         quantity_to_gather=15)
    process_wheat = DeliverWheatToMillTask(priority=0, quantity_to_retrieve=10)

    gather_score = gather_wheat.compute_score(ctx, sim.resource_manager)
    process_score = process_wheat.compute_score(ctx, sim.resource_manager)

    assert process_score > gather_score


def test_empty_stores_everything_gathers_with_high_urgency():
    sim = Simulation(seed=42)
    fid = sim.factions[0].faction_id
    tm = sim.factions[0].task_manager

    gather_berry = GatherAndDeliverTask(priority=0, resource_type_to_gather=ResourceType.BERRY,
                                         quantity_to_gather=20)
    gather_wheat = GatherAndDeliverTask(priority=0, resource_type_to_gather=ResourceType.WHEAT,
                                         quantity_to_gather=15)

    _set_stock(sim, fid, ResourceType.BERRY, config.MIN_BERRY_STOCK_LEVEL // 2)
    ctx_half = tm._build_faction_context()
    half_score = gather_berry.compute_score(ctx_half, sim.resource_manager)

    _set_stock(sim, fid, ResourceType.BERRY, 0)
    _set_stock(sim, fid, ResourceType.WHEAT, 0)
    ctx_empty = tm._build_faction_context()
    empty_score = gather_berry.compute_score(ctx_empty, sim.resource_manager)

    # Urgency strictly increases as stock drops toward 0 — a smooth ramp, not a threshold cliff.
    assert empty_score > half_score
    # With everything empty, gathering scores positively (favorably) for every resource.
    assert gather_wheat.compute_score(ctx_empty, sim.resource_manager) > 0
    assert empty_score > 0


def test_rescore_updates_pending_task_priority():
    """A pending task's cached priority (=score) changes across the 5s rescore cadence when
    stock conditions change — proves the periodic-refresh wiring actually runs, not just
    compute_score in isolation."""
    sim = Simulation(seed=7)
    fid = sim.factions[0].faction_id
    tm = sim.factions[0].task_manager

    task = GatherAndDeliverTask(priority=1, resource_type_to_gather=ResourceType.BERRY,
                                 quantity_to_gather=20)
    tm.add_task(task)

    _set_stock(sim, fid, ResourceType.BERRY, config.MIN_BERRY_STOCK_LEVEL)  # at target -> low urgency
    tm.update(dt=6.0, manual_mode=True, sim_time=sim.sim_time + 6.0)
    score_full = task.priority

    _set_stock(sim, fid, ResourceType.BERRY, 0)  # empty -> urgency should rise
    tm.update(dt=6.0, manual_mode=True, sim_time=sim.sim_time + 12.0)
    score_empty = task.priority

    assert score_empty > score_full
