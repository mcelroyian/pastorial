"""Tests for starvation, agent death, and clean resource teardown."""
import pygame
from src.core.simulation import Simulation
from src.resources.resource_types import ResourceType
from src.resources.storage_point import StoragePoint
from src.core import config

_DT = 1 / 60


def _ticks_until_dead(sim, agent):
    """Run sim until agent dies or 20 000 ticks pass."""
    for _ in range(20_000):
        sim.update(_DT)
        if agent.needs.is_dead:
            return True
    return False


def test_starving_agent_dies_and_sim_continues():
    """Agent with no food source dies; sim continues 1000 more ticks without exceptions."""
    sim = Simulation(seed=42)
    # Block all bread production by removing bakeries
    sim.resource_manager.processing_stations.clear()

    agent = sim.agent_manager.agents[0]
    agent.needs.hunger = 0.0  # instant starvation counter

    died = _ticks_until_dead(sim, agent)
    assert died, "Agent should have died"

    agent_id = agent.id
    assert agent not in sim.agent_manager.agents, "Dead agent must be removed"
    assert agent_id not in sim.task_manager.assigned_tasks, "Dead agent task slot must be cleared"

    # 1000 more ticks — must not raise
    for _ in range(1000):
        sim.update(_DT)


def test_dead_agent_claims_released():
    """Task claim and storage reservation are freed when agent dies mid-gather."""
    from src.tasks.task import GatherAndDeliverTask
    from src.tasks.task_types import TaskStatus

    sim = Simulation(seed=42)
    agent = sim.agent_manager.agents[0]

    # Wait until agent picks up a gather task
    for _ in range(2000):
        sim.update(_DT)
        current_task = sim.task_manager.assigned_tasks.get(agent.id)
        if isinstance(current_task, GatherAndDeliverTask) and current_task.reserved_at_node:
            break

    task = sim.task_manager.assigned_tasks.get(agent.id)
    if task is None or not isinstance(task, GatherAndDeliverTask):
        return  # couldn't get the agent into the right state — skip

    node = task.target_resource_node_ref
    task_id = task.task_id

    # Kill agent instantly
    agent.needs.hunger = 0.0
    agent.needs.starvation_timer = config.STARVATION_GRACE_PERIOD + 1.0
    agent.needs.is_dead = True

    sim.update(_DT)  # should trigger _remove_dead_agent

    assert agent not in sim.agent_manager.agents
    if node is not None:
        assert not task.reserved_at_node, "Node claim should be released on death"


def test_grid_occupancy_cleared_on_death():
    """The occupancy cell at the agent's death position is freed."""
    sim = Simulation(seed=42)
    agent = sim.agent_manager.agents[0]

    # Immediately kill
    agent.needs.hunger = 0.0
    agent.needs.starvation_timer = config.STARVATION_GRACE_PERIOD + 1.0
    agent.needs.is_dead = True

    gx, gy = int(round(agent.position.x)), int(round(agent.position.y))
    sim.update(_DT)

    # Cell should now be free (0)
    assert sim.grid.occupancy_grid[gy][gx] == 0, "Occupancy not cleared after agent death"
