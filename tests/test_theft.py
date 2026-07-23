"""Tests for Plan 4 Task 3: theft (StealFromStorageTask) scenario-level emergence.

Empirical tuning notes (see docs/plan-4-progress.md for the full account): the raid scorer
depends on FactionContext.food_deficit_seconds, which in turn depends on SimMetrics's rolling
consumption-rate window. With only 3-6 agents per faction eating infrequently, a naive setup
made this signal too spiky (frequently falling back to the "abundant" sentinel even under real
scarcity) and made ASYMMETRIC's initial-bread-only asymmetry self-correct before real
desperation could build. Fixed via: UTILITY_CONSUMPTION_WINDOW_SECONDS widened to 300s, and
scenarios.ASYMMETRIC given a persistent (not just transient) production handicap via
faction_bakeries=[1, 0] — faction 1 can mill flour but never bake it into bread, so it reliably
runs down over time regardless of seed, without confounding both factions equally the way a
uniform agent-count bump did (that made raiding directionless — see scenario docstring).
"""
from src.core.simulation import Simulation
from src.core import scenarios, config

_DT = 1 / 60
_SEEDS = [1, 2, 3]
_RUN_SECONDS = 500.0  # ASYMMETRIC's faction 1 doesn't hit real deficit until ~t=310-320s
                       # (initial bread cushion + travel/production lag); empirically the
                       # single raid observed per seed lands shortly after that point.


def _run(sim, seconds):
    ticks = int(seconds / _DT)
    for _ in range(ticks):
        sim.update(_DT)


def test_asymmetric_produces_directional_raids():
    """Faction 1 (resource-poor, no bakery) should raid faction 0 — not the reverse."""
    f1_raider_total = 0
    f0_raider_total = 0
    for seed in _SEEDS:
        sim = Simulation(seed=seed, scenario=scenarios.ASYMMETRIC)
        _run(sim, _RUN_SECONDS)
        theft_events = [e for e in sim.events.recent(config.EVENT_LOG_MAX_SIZE) if e.event_type == "theft"]
        f1_raider_total += sum(1 for e in theft_events if e.faction_id == 1)
        f0_raider_total += sum(1 for e in theft_events if e.faction_id == 0)

    assert f1_raider_total > 0, "Expected faction 1 (resource-poor) to raid at least once across seeds"
    assert f0_raider_total == 0, (
        f"Expected zero raids in the faction 0 -> faction 1 direction, got {f0_raider_total}"
    )


def test_default_produces_zero_raids():
    total_theft = 0
    for seed in _SEEDS:
        sim = Simulation(seed=seed, scenario=scenarios.DEFAULT)
        _run(sim, _RUN_SECONDS)
        total_theft += sim.events.count_since("theft", 0.0)

    assert total_theft == 0, f"Expected zero raids in DEFAULT, got {total_theft}"


def test_theft_event_fields():
    """Force conditions that guarantee a raid, then check the emitted event's shape."""
    sim = Simulation(seed=1, scenario=scenarios.ASYMMETRIC)
    _run(sim, _RUN_SECONDS)

    theft_events = [e for e in sim.events.recent(sim.events._events.maxlen) if e.event_type == "theft"]
    assert theft_events, "Expected at least one theft event in this deterministic scenario/seed"

    e = theft_events[0]
    assert e.faction_id == 1          # raider (actor)
    assert e.other_faction_id == 0    # victim
    assert e.resource_type == "BREAD"
    assert e.position is not None
    assert int(e.detail) > 0          # amount stolen, stored as a string (see SimEvent.detail)
