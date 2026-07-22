"""Tests for Plan 4 Task 2: contested wild resources (contention pressure, event log)."""
from src.core.simulation import Simulation
from src.core import scenarios, config
from src.resources.resource_types import ResourceType
from src.resources.berry_bush import BerryBush
from src.tasks.task import GatherAndDeliverTask

_DT = 1 / 60
_SEEDS = [1, 2, 3]
# Both scenarios' contention counts grow over a run (both factions constantly draw on the
# shared wild strip) and eventually saturate the event log's ring buffer given enough time —
# a 60s window captures the differentiating signal before that saturation erases it (empirically:
# DEFAULT sums to ~5 events across 3 seeds at 60s, SCARCITY to ~85+ — a wide, robust margin).
_RUN_SECONDS = 60.0


def _run(sim, seconds):
    ticks = int(seconds / _DT)
    for _ in range(ticks):
        sim.update(_DT)


def test_contention_pressure_lowers_gather_score():
    """A node with elevated contention_pressure should produce a lower compute_score than the
    same node at zero pressure, all else equal — proves the mechanism directly, isolated from
    the stochastic end-to-end scenario test below."""
    sim = Simulation(seed=42)
    tm = sim.factions[0].task_manager
    ctx = tm._build_faction_context()

    task = GatherAndDeliverTask(priority=0, resource_type_to_gather=ResourceType.BERRY,
                                 quantity_to_gather=20)

    nodes = [n for n in sim.resource_manager.nodes if isinstance(n, BerryBush)]
    assert nodes, "No wild berry bushes in sim"

    score_at_zero = task.compute_score(ctx, sim.resource_manager)

    for n in nodes:
        n.contention_pressure = config.CONTENTION_PRESSURE_CAP
    score_at_cap = task.compute_score(ctx, sim.resource_manager)

    assert score_at_cap < score_at_zero


def test_cross_faction_denial_tracks_claiming_faction():
    """claim() records which faction holds a node; same-faction re-claims are denied without
    contention semantics (that distinction is made by the caller, tested end-to-end below)."""
    sim = Simulation(seed=1)
    node = next(n for n in sim.resource_manager.nodes if isinstance(n, BerryBush))
    node.current_quantity = node.capacity

    import uuid
    agent_a, task_a = uuid.uuid4(), uuid.uuid4()
    agent_b, task_b = uuid.uuid4(), uuid.uuid4()

    assert node.claim(agent_a, task_a, faction_id=0)
    assert node.claimed_by_faction_id == 0

    assert not node.claim(agent_b, task_b, faction_id=1)
    assert node.claimed_by_faction_id == 0  # unchanged — original claim still holds

    node.release(agent_a, task_a)
    assert node.claimed_by_faction_id is None
    assert node.claim(agent_b, task_b, faction_id=1)
    assert node.claimed_by_faction_id == 1


def test_scarcity_has_more_contention_than_default_over_seeds():
    scarcity_counts = []
    default_counts = []
    for seed in _SEEDS:
        sim_s = Simulation(seed=seed, scenario=scenarios.SCARCITY)
        _run(sim_s, _RUN_SECONDS)
        scarcity_counts.append(sim_s.events.count_since("claim_contention", 0.0))

        sim_d = Simulation(seed=seed, scenario=scenarios.DEFAULT)
        _run(sim_d, _RUN_SECONDS)
        default_counts.append(sim_d.events.count_since("claim_contention", 0.0))

    total_scarcity = sum(scarcity_counts)
    total_default = sum(default_counts)

    assert total_scarcity > total_default, (
        f"Expected SCARCITY contention ({scarcity_counts}, sum={total_scarcity}) to exceed "
        f"DEFAULT contention ({default_counts}, sum={total_default})"
    )
    assert total_scarcity > 0, "SCARCITY produced zero contention events across all seeds"
    assert total_default <= 10, (
        f"DEFAULT contention should be rare; got {default_counts} (sum={total_default})"
    )
