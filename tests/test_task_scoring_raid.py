"""Tests for Plan 4 Task 3 raid scoring (StealFromStorageTask.compute_score).

The load-bearing assertion for this whole rung: raiding must score strictly worse than
peaceful options in normal conditions (peace_bias dominates), and only cross over into
outscoring them once food_deficit_seconds gets severe. See docs/plan-4-emergent-conflict.md
Task 3 section — "get this inequality right and everything else follows."
"""
import dataclasses

from src.core.simulation import Simulation
from src.core import config
from src.resources.resource_types import ResourceType
from src.tasks.task import GatherAndDeliverTask, StealFromStorageTask, _food_deficit_urgency


def _set_stock(sim, faction_id, resource_type, quantity):
    for sp in sim.resource_manager.storage_points_for(faction_id):
        if resource_type in sp.accepted_resource_types:
            sp.stored_resources[resource_type] = quantity
            return
    raise AssertionError(f"No storage point accepts {resource_type} for faction {faction_id}")


def test_raid_score_low_in_abundance():
    """Fresh sim, no consumption yet -> food_deficit_seconds is capped (abundant). Raid score
    must be deeply negative and below a comparable gather task's score — peace_bias wins."""
    sim = Simulation(seed=42)
    fid = sim.factions[0].faction_id
    tm = sim.factions[0].task_manager
    ctx = tm._build_faction_context()

    steal = StealFromStorageTask(priority=0, quantity_to_steal=5)
    gather = GatherAndDeliverTask(priority=0, resource_type_to_gather=ResourceType.BERRY,
                                   quantity_to_gather=20)

    steal_score = steal.compute_score(ctx, sim.resource_manager)
    gather_score = gather.compute_score(ctx, sim.resource_manager)

    assert steal_score < 0
    assert steal_score < gather_score


def test_raid_score_disqualified_when_no_enemy_bread():
    sim = Simulation(seed=42)
    fid = sim.factions[0].faction_id
    other_fid = sim.factions[1].faction_id
    tm = sim.factions[0].task_manager

    _set_stock(sim, other_fid, ResourceType.BREAD, 0)
    ctx = tm._build_faction_context()

    steal = StealFromStorageTask(priority=0, quantity_to_steal=5)
    score = steal.compute_score(ctx, sim.resource_manager)

    assert score == -1e9


def test_raid_score_rises_monotonically_as_deficit_worsens():
    sim = Simulation(seed=42)
    tm = sim.factions[0].task_manager
    base_ctx = tm._build_faction_context()
    steal = StealFromStorageTask(priority=0, quantity_to_steal=5)

    scores = []
    for deficit_seconds in [1e6, 100.0, 50.0, 10.0, 0.0]:
        ctx = dataclasses.replace(base_ctx, food_deficit_seconds=deficit_seconds)
        scores.append(steal.compute_score(ctx, sim.resource_manager))

    assert scores == sorted(scores), f"Expected monotonic ramp as deficit worsens, got {scores}"
    assert scores[-1] > scores[0]


def test_food_deficit_urgency_shape():
    # Abundant (capped sentinel) -> ~0 urgency; imminent starvation -> ~1 urgency.
    assert _food_deficit_urgency(config.FOOD_DEFICIT_SECONDS_CAP) == 0.0
    assert _food_deficit_urgency(0.0) == 1.0
    assert 0.0 < _food_deficit_urgency(config.RAID_FOOD_DEFICIT_HORIZON_SECONDS / 2) < 1.0


def test_raid_outscores_gather_under_severe_deficit():
    """The crossover the whole rung depends on: construct a severe-deficit context and confirm
    raiding actually can win somewhere on the curve, not just "always worse.\""""
    sim = Simulation(seed=42)
    tm = sim.factions[0].task_manager
    base_ctx = tm._build_faction_context()
    severe_ctx = dataclasses.replace(base_ctx, food_deficit_seconds=0.0)

    steal = StealFromStorageTask(priority=0, quantity_to_steal=5)
    gather = GatherAndDeliverTask(priority=0, resource_type_to_gather=ResourceType.BERRY,
                                   quantity_to_gather=20)

    steal_score = steal.compute_score(severe_ctx, sim.resource_manager)
    gather_score = gather.compute_score(severe_ctx, sim.resource_manager)

    assert steal_score > gather_score
