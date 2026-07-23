"""Tests for Plan 4 Task 4: defense (GuardTask, threat_level, guard-aware raiding).

Empirical tuning note (see docs/plan-4-progress.md for the full account): threat_level's
contention component had to be weighted and capped far more conservatively than a literal
reading of "an order of magnitude below theft" would suggest. Wild-node contention is
near-continuous under any territorial overlap (~400 denial events per 500 sim-seconds observed
in ASYMMETRIC), so an uncapped/lightly-capped decay sum over it alone was enough to push
GuardTask's score positive well before any real hostility (theft) occurred — this first showed
up as tests/test_theft.py::test_theft_event_fields regressing (a guard formed from ambient
contention at ~t=30s and blocked the one raid that seed depends on). THREAT_WEIGHT_CONTENTION
and THREAT_CONTENTION_CAP are tuned so the contention component alone can never clear
GuardTask's distance_cost floor; only theft (weight 10, uncapped) does that.
"""
import dataclasses

import pytest
from pygame.math import Vector2

from src.core.simulation import Simulation
from src.core import scenarios, config
from src.core.events import EventLog
from src.resources.resource_types import ResourceType
from src.tasks.task import StealFromStorageTask, GuardTask
from src.tasks.task_types import TaskStatus
from src.factions.context import FactionContext
from src.agents.manager import AgentManager

_DT = 1 / 60
_SEEDS = [1, 2, 3]
_RUN_SECONDS = 500.0  # matches tests/test_theft.py — same scenario, same window


def _run(sim, seconds):
    ticks = int(seconds / _DT)
    for _ in range(ticks):
        sim.update(_DT)


def _set_stock(sim, faction_id, resource_type, quantity):
    for sp in sim.resource_manager.storage_points_for(faction_id):
        if resource_type in sp.accepted_resource_types:
            sp.stored_resources[resource_type] = quantity
            return sp
    raise AssertionError(f"No storage point accepts {resource_type} for faction {faction_id}")


# ---------------------------------------------------------------------------
# AgentManager.get_agents_near
# ---------------------------------------------------------------------------

class _FakeAgent:
    def __init__(self, position, faction_id):
        self.position = position
        self.owner_faction_id = faction_id


def test_get_agents_near_filters_by_radius_and_faction():
    am = AgentManager(grid=None, task_manager=None)
    am.agents = [
        _FakeAgent(Vector2(0, 0), faction_id=0),
        _FakeAgent(Vector2(1, 0), faction_id=0),   # within radius, same faction
        _FakeAgent(Vector2(10, 0), faction_id=0),  # outside radius
        _FakeAgent(Vector2(1, 1), faction_id=1),   # within radius, other faction
    ]
    origin = Vector2(0, 0)

    same_faction = am.get_agents_near(origin, radius=2.0, faction_id=0)
    assert len(same_faction) == 2
    assert all(a.owner_faction_id == 0 for a in same_faction)

    any_faction = am.get_agents_near(origin, radius=2.0)
    assert len(any_faction) == 3

    assert am.get_agents_near(origin, radius=2.0, faction_id=1) == [am.agents[3]]


# ---------------------------------------------------------------------------
# FactionContext.compute_threat_level
# ---------------------------------------------------------------------------

def test_threat_level_weights_theft_above_contention():
    theft_events = EventLog()
    theft_events.update(100.0)
    theft_events.record("theft", faction_id=1, other_faction_id=0)
    threat_from_theft = FactionContext.compute_threat_level(theft_events, faction_id=0, sim_time=100.0)

    contention_events = EventLog()
    contention_events.update(100.0)
    contention_events.record("claim_contention", faction_id=0, other_faction_id=1)
    threat_from_contention = FactionContext.compute_threat_level(
        contention_events, faction_id=0, sim_time=100.0
    )

    assert threat_from_theft == pytest.approx(config.THREAT_WEIGHT_THEFT)
    assert threat_from_theft > threat_from_contention > 0


def test_threat_level_contention_component_is_capped():
    events = EventLog()
    events.update(0.0)
    for _ in range(500):  # saturate the ring buffer (EVENT_LOG_MAX_SIZE)
        events.record("claim_contention", faction_id=0, other_faction_id=1)

    threat = FactionContext.compute_threat_level(events, faction_id=0, sim_time=0.0)
    assert threat == pytest.approx(config.THREAT_CONTENTION_CAP)


def test_threat_level_decays_over_time_and_expires_past_lookback():
    events = EventLog()
    events.update(0.0)
    events.record("theft", faction_id=1, other_faction_id=0)

    fresh = FactionContext.compute_threat_level(events, faction_id=0, sim_time=0.0)
    half_life_later = FactionContext.compute_threat_level(
        events, faction_id=0, sim_time=config.THREAT_DECAY_HALFLIFE_SECONDS
    )
    past_lookback = FactionContext.compute_threat_level(
        events, faction_id=0, sim_time=config.THREAT_LOOKBACK_SECONDS + 1.0
    )

    assert fresh == pytest.approx(config.THREAT_WEIGHT_THEFT)
    assert half_life_later == pytest.approx(fresh / 2, rel=0.02)
    assert past_lookback == 0.0


def test_threat_decay_stops_guard_from_scoring_positive():
    """'Threat decays: force threat high, run quiet sim-minutes, guards stop being generated'
    (plan doc, Task 4 verify) — exercised directly via sim_time, not a full tick loop, mirroring
    how tests/test_task_scoring_raid.py checks decay/monotonicity without running the sim."""
    sim = Simulation(seed=7, scenario=scenarios.DEFAULT)
    tm0 = sim.factions[0].task_manager

    sim.events.update(0.0)
    sim.events.record("theft", faction_id=1, other_faction_id=0, position=Vector2(0, 0),
                       resource_type="BREAD", detail="5")

    tm0.sim_time = 0.0
    ctx_fresh = tm0._build_faction_context()
    assert ctx_fresh.threat_level > 0

    tm0.sim_time = config.THREAT_LOOKBACK_SECONDS + 1.0
    ctx_later = tm0._build_faction_context()
    assert ctx_later.threat_level == 0.0

    storage = sim.resource_manager.storage_points_for(0)[0]
    guard = GuardTask(priority=0, storage_point=storage)
    assert guard.compute_score(ctx_later, sim.resource_manager) <= 0


# ---------------------------------------------------------------------------
# Guard effect on StealFromStorageTask (direct, isolated from scoring/emergence)
# ---------------------------------------------------------------------------

def test_guard_blocks_steal_completion():
    sim = Simulation(seed=1)
    victim = sim.factions[0]
    storage = _set_stock(sim, victim.faction_id, ResourceType.BREAD, 10)

    defender = next(a for a in sim.agent_manager.agents if a.owner_faction_id == victim.faction_id)
    defender.position = Vector2(storage.position)

    guard_task = GuardTask(priority=100, storage_point=storage)
    guard_task.agent_id = defender.id
    guard_task.status = TaskStatus.IN_PROGRESS
    victim.task_manager.assigned_tasks[defender.id] = guard_task

    raider = next(a for a in sim.agent_manager.agents if a.owner_faction_id != victim.faction_id)
    steal = StealFromStorageTask(priority=0, quantity_to_steal=5)
    steal.target_storage_ref = storage
    steal.victim_faction_id = victim.faction_id
    steal.reserved_at_storage_for_pickup_quantity = storage.reserve_for_pickup(
        steal.task_id, ResourceType.BREAD, 5, faction_id=raider.owner_faction_id, force=True
    )

    steal._on_steal_complete(raider, steal, sim.resource_manager)

    assert steal.status == TaskStatus.FAILED
    assert steal.quantity_stolen == 0
    repelled = [e for e in sim.events.since(0.0) if e.event_type == "raid_repelled"]
    assert len(repelled) == 1
    assert repelled[0].faction_id == raider.owner_faction_id
    assert repelled[0].other_faction_id == victim.faction_id


def test_steal_succeeds_without_a_guard():
    """Same setup as above, minus the guard assignment — proves the block is guard-specific,
    not a side effect of some other Task 4 change to the steal path."""
    sim = Simulation(seed=1)
    victim = sim.factions[0]
    storage = _set_stock(sim, victim.faction_id, ResourceType.BREAD, 10)

    raider = next(a for a in sim.agent_manager.agents if a.owner_faction_id != victim.faction_id)
    steal = StealFromStorageTask(priority=0, quantity_to_steal=5)
    steal.target_storage_ref = storage
    steal.victim_faction_id = victim.faction_id
    steal.reserved_at_storage_for_pickup_quantity = storage.reserve_for_pickup(
        steal.task_id, ResourceType.BREAD, 5, faction_id=raider.owner_faction_id, force=True
    )

    steal._on_steal_complete(raider, steal, sim.resource_manager)

    assert steal.status != TaskStatus.FAILED
    assert steal.quantity_stolen == 5
    assert not [e for e in sim.events.since(0.0) if e.event_type == "raid_repelled"]


def test_guard_agent_not_on_guard_task_does_not_block():
    """An agent merely standing near the target (e.g. passing through to eat) must not grant
    free deterrence — only agents actively assigned a GuardTask for this building count
    (config.MIN_DEFENDERS_TO_BLOCK_STEAL); see _count_guards_near."""
    sim = Simulation(seed=1)
    victim = sim.factions[0]
    storage = _set_stock(sim, victim.faction_id, ResourceType.BREAD, 10)

    bystander = next(a for a in sim.agent_manager.agents if a.owner_faction_id == victim.faction_id)
    bystander.position = Vector2(storage.position)  # right on top, but not on a GuardTask

    raider = next(a for a in sim.agent_manager.agents if a.owner_faction_id != victim.faction_id)
    steal = StealFromStorageTask(priority=0, quantity_to_steal=5)
    steal.target_storage_ref = storage
    steal.victim_faction_id = victim.faction_id
    steal.reserved_at_storage_for_pickup_quantity = storage.reserve_for_pickup(
        steal.task_id, ResourceType.BREAD, 5, faction_id=raider.owner_faction_id, force=True
    )

    steal._on_steal_complete(raider, steal, sim.resource_manager)

    assert steal.quantity_stolen == 5
    assert not [e for e in sim.events.since(0.0) if e.event_type == "raid_repelled"]


def test_raid_score_drops_when_target_guarded():
    """The other half of the guard tradeoff: even before a raid is attempted, a guarded target
    scores worse (risk_cost) than the same target unguarded — this is what makes raiding
    'shift toward undefended targets' rather than just fail on arrival."""
    sim = Simulation(seed=42)
    other_fid = sim.factions[1].faction_id
    tm = sim.factions[0].task_manager
    storage = _set_stock(sim, other_fid, ResourceType.BREAD, 20)
    ctx = tm._build_faction_context()

    steal = StealFromStorageTask(priority=0, quantity_to_steal=5)
    score_unguarded = steal.compute_score(ctx, sim.resource_manager)

    defender = next(a for a in sim.agent_manager.agents if a.owner_faction_id == other_fid)
    defender.position = Vector2(storage.position)
    guard_task = GuardTask(priority=100, storage_point=storage)
    guard_task.agent_id = defender.id
    sim.factions[other_fid].task_manager.assigned_tasks[defender.id] = guard_task

    score_guarded = steal.compute_score(ctx, sim.resource_manager)

    assert score_guarded < score_unguarded


# ---------------------------------------------------------------------------
# GuardTask.compute_score
# ---------------------------------------------------------------------------

def test_guard_score_scales_with_threat_and_needs_stock_worth_protecting():
    sim = Simulation(seed=42)
    tm = sim.factions[0].task_manager
    storage = _set_stock(sim, 0, ResourceType.BERRY, config.GUARD_STOCK_VALUE_CAP)

    base_ctx = tm._build_faction_context()
    ctx_no_threat = dataclasses.replace(base_ctx, threat_level=0.0)
    ctx_high_threat = dataclasses.replace(base_ctx, threat_level=config.THREAT_WEIGHT_THEFT)

    guard = GuardTask(priority=0, storage_point=storage)
    score_no_threat = guard.compute_score(ctx_no_threat, sim.resource_manager)
    score_high_threat = guard.compute_score(ctx_high_threat, sim.resource_manager)

    assert score_no_threat <= 0
    assert score_high_threat > score_no_threat
    assert score_high_threat > 0


# ---------------------------------------------------------------------------
# Scenario-level emergence: ASYMMETRIC guards appear reactively, after theft
# ---------------------------------------------------------------------------

def test_asymmetric_guard_appears_after_theft():
    """Once faction 0 (the victim) suffers a theft, it should generate a guard at or after that
    point — the reactive defense the plan doc calls for. Not every seed produces a raid at all
    (see tests/test_theft.py's own caveat); only seeds with >=1 theft are asserted on here."""
    seeds_with_theft = 0
    seeds_with_guard_after_theft = 0
    for seed in _SEEDS:
        sim = Simulation(seed=seed, scenario=scenarios.ASYMMETRIC)
        tm0 = sim.factions[0].task_manager
        guard_seen_at = None

        ticks = int(_RUN_SECONDS / _DT)
        for _ in range(ticks):
            sim.update(_DT)
            if guard_seen_at is None:
                board = list(tm0.pending_tasks) + list(tm0.assigned_tasks.values())
                if any(isinstance(t, GuardTask) and t.priority > 0 for t in board):
                    guard_seen_at = sim.sim_time

        theft_events = [e for e in sim.events.since(0.0) if e.event_type == "theft"]
        if theft_events:
            seeds_with_theft += 1
            first_theft_t = theft_events[0].sim_time
            if guard_seen_at is not None and guard_seen_at >= first_theft_t:
                seeds_with_guard_after_theft += 1

    assert seeds_with_theft > 0, "Expected at least one seed to produce a raid"
    assert seeds_with_guard_after_theft == seeds_with_theft, (
        "Expected a guard to appear at/after every theft event's sim_time, in every seed "
        "that produced a theft"
    )
