"""Same seed must produce identical end state (proves no wall-clock nondeterminism in gameplay)."""
import pytest
from src.core.simulation import Simulation
from src.resources.resource_types import ResourceType

_TICKS = 2000
_DT = 1 / 60


def _run(seed):
    sim = Simulation(seed=seed)
    for _ in range(_TICKS):
        sim.update(_DT)
    rm = sim.resource_manager
    return {
        "berry": rm.get_global_resource_quantity(ResourceType.BERRY),
        "wheat": rm.get_global_resource_quantity(ResourceType.WHEAT),
        "flour": rm.get_global_resource_quantity(ResourceType.FLOUR_POWDER),
        "bread": rm.get_global_resource_quantity(ResourceType.BREAD),
        "agents": len(sim.agent_manager.agents),
        "sim_time": round(sim.sim_time, 6),
    }


def test_same_seed_deterministic():
    a = _run(seed=99)
    b = _run(seed=99)
    assert a == b


def test_different_seeds_differ():
    a = _run(seed=1)
    b = _run(seed=2)
    # At least one metric should differ between seeds
    assert a != b
