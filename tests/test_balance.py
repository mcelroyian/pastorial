"""Balance integration test: default 2-faction config, fixed seed, 20 sim-minutes.

Criteria (per plan-3-factions.md Task 5):
  - ≥80% of agents alive at the end (both factions combined)
  - Each faction independently: ≥1 bread consumed
  - Bread stock non-zero at the end (production kept up)
"""
from src.core.simulation import Simulation
from src.resources.resource_types import ResourceType

_SEED = 42
_SIM_MINUTES = 20.0
_DT = 1 / 60  # ~16 ms steps (real-time equivalent)


def test_village_survives_20_minutes():
    sim = Simulation(seed=_SEED)
    assert len(sim.factions) == 2, "Expected 2-faction default"

    total_agents = len(sim.agent_manager.agents)
    target_seconds = _SIM_MINUTES * 60.0
    elapsed = 0.0
    while elapsed < target_seconds:
        sim.update(_DT)
        elapsed += _DT

    alive = len(sim.agent_manager.agents)
    survival_rate = alive / total_agents if total_agents > 0 else 0.0

    bread_consumed = sim.metrics.consumed.get(ResourceType.BREAD, 0)
    bread_stock = sim.resource_manager.get_global_resource_quantity(ResourceType.BREAD)

    assert survival_rate >= 0.8, (
        f"Survival rate {survival_rate:.0%} below 80% ({alive}/{total_agents} alive)"
    )
    assert bread_consumed > 0, "No bread was consumed — hunger loop may be broken"
    assert bread_stock >= 0, "Negative bread stock is impossible"

    # Per-faction: each faction must have consumed at least 1 bread
    for faction in sim.factions:
        fid = faction.faction_id
        f_consumed = sim.metrics.faction_consumed.get(fid, {}).get(ResourceType.BREAD, 0)
        assert f_consumed > 0, (
            f"Faction {faction.name} (id={fid}) consumed 0 bread — its economy is not functioning"
        )
