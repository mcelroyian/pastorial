import pytest

from src.core.simulation import Simulation
from src.resources.resource_types import ResourceType
from src.resources.mill import Mill
from src.resources.bakery import Bakery


@pytest.fixture(scope="module")
def smoke_sim():
    sim = Simulation(seed=42)
    for _ in range(9000):
        sim.update(1 / 60)
    return sim


def test_smoke_no_exception(smoke_sim):
    pass  # reaching here means 9000 ticks ran without raising


def test_berries_stored(smoke_sim):
    assert smoke_sim.resource_manager.get_global_resource_quantity(ResourceType.BERRY) > 0


def test_wheat_gathered(smoke_sim):
    # Wheat flows: field → storage → mill (not held long-term in storage).
    # Verify it entered the chain via the mill's input buffer OR bread proves it.
    rm = smoke_sim.resource_manager
    mill_wheat_input = sum(
        st.current_input_quantity
        for st in rm.processing_stations
        if isinstance(st, Mill)
    )
    bread = sum(
        st.current_output_quantity.get(ResourceType.BREAD, 0)
        for st in rm.processing_stations
        if isinstance(st, Bakery)
    )
    assert mill_wheat_input + bread > 0, "No evidence of wheat being gathered or processed"


def test_flour_produced(smoke_sim):
    rm = smoke_sim.resource_manager
    flour_in_mill = sum(
        st.current_output_quantity
        for st in rm.processing_stations
        if isinstance(st, Mill)
    )
    flour_in_bakery = sum(
        st.current_input_quantity.get(ResourceType.FLOUR_POWDER, 0)
        for st in rm.processing_stations
        if isinstance(st, Bakery)
    )
    bread_produced = sum(
        st.current_output_quantity.get(ResourceType.BREAD, 0)
        for st in rm.processing_stations
        if isinstance(st, Bakery)
    )
    # bread_produced > 0 implies flour was processed even if buffers are empty at snapshot
    assert flour_in_mill + flour_in_bakery + bread_produced > 0, "No evidence of flour production"


def test_bread_produced(smoke_sim):
    # Bread is auto-distributed to storage, so check both bakery buffer and storage.
    bread_in_bakeries = sum(
        st.current_output_quantity.get(ResourceType.BREAD, 0)
        for st in smoke_sim.resource_manager.processing_stations
        if isinstance(st, Bakery)
    )
    bread_in_storage = smoke_sim.resource_manager.get_global_resource_quantity(ResourceType.BREAD)
    consumed = smoke_sim.metrics.consumed.get(ResourceType.BREAD, 0)
    assert bread_in_bakeries + bread_in_storage + consumed > 0, (
        "No bread in bakeries, storage, or consumed after 9000 ticks"
    )


def test_determinism():
    # Run sequentially so shared global random state doesn't cross-contaminate.
    sim1 = Simulation(seed=42)
    for _ in range(1000):
        sim1.update(1 / 60)
    count1 = sim1.resource_manager.get_global_resource_quantity(ResourceType.BERRY)

    sim2 = Simulation(seed=42)
    for _ in range(1000):
        sim2.update(1 / 60)
    count2 = sim2.resource_manager.get_global_resource_quantity(ResourceType.BERRY)

    assert count1 == count2, (
        f"Same seed produced different berry counts ({count1} vs {count2}) — non-determinism detected"
    )
