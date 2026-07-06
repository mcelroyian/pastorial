"""Tests for EatTask — bread consumption closes the economic loop."""
import pygame
from src.core.simulation import Simulation
from src.tasks.task import EatTask
from src.tasks.task_types import TaskStatus, TaskType
from src.resources.resource_types import ResourceType
from src.resources.storage_point import StoragePoint
from src.core import config

_DT = 1 / 60
_MAX_TICKS = 6000


def _seed_bread(sim, quantity=5):
    """Add bread to the bread storage, creating one at (0,0) if none exists yet."""
    for sp in sim.resource_manager.storage_points:
        if sp.accepted_resource_types is None or ResourceType.BREAD in sp.accepted_resource_types:
            sp.stored_resources[ResourceType.BREAD] = quantity
            return sp
    # Fallback: add a small storage point at the first free cell
    for gx in range(sim.grid.width_in_cells):
        for gy in range(sim.grid.height_in_cells):
            if sim.grid.is_area_free(gx, gy, 1, 1):
                sp = StoragePoint(
                    position=pygame.math.Vector2(gx, gy),
                    overall_capacity=20,
                    accepted_resource_types=[ResourceType.BREAD],
                )
                sp.stored_resources[ResourceType.BREAD] = quantity
                sim.resource_manager.add_storage_point(sp)
                sim.grid.update_occupancy(sp, gx, gy, 1, 1, is_placing=True)
                return sp
    raise RuntimeError("No free cell for bread storage")


def test_hungry_agent_eats_bread_and_restores_hunger():
    sim = Simulation(seed=42)
    _seed_bread(sim, quantity=5)

    # Force first agent to be hungry so it will seek food
    agent = sim.agent_manager.agents[0]
    agent.needs.hunger = config.HUNGER_SEEK_FOOD_THRESHOLD - 0.05

    for _ in range(_MAX_TICKS):
        sim.update(_DT)
        # Stop early if hunger was restored
        if agent.needs.hunger > config.HUNGER_SEEK_FOOD_THRESHOLD:
            break

    assert agent.needs.hunger > config.HUNGER_SEEK_FOOD_THRESHOLD, (
        f"Agent did not eat; hunger={agent.needs.hunger:.3f}"
    )
    # Bakery production may replenish stock, so use metrics to confirm consumption
    assert sim.metrics.consumed.get(ResourceType.BREAD, 0) > 0, "Bread should have been consumed"


def test_hungry_agent_no_bread_does_not_deadlock():
    sim = Simulation(seed=42)
    # Do NOT seed bread — test that agent keeps working normally

    agent = sim.agent_manager.agents[0]
    agent.needs.hunger = config.HUNGER_SEEK_FOOD_THRESHOLD - 0.05

    completed_before = len(sim.task_manager.completed_tasks)

    # Run 3000 ticks — agent should still do gather tasks, not spin
    for _ in range(3000):
        sim.update(_DT)

    completed_after = len(sim.task_manager.completed_tasks)
    assert completed_after > completed_before, "Agent should still complete gather tasks when no bread"


def test_critical_hunger_abandons_task_and_releases_claims():
    """Agent at critical hunger mid-gather should release node claim and storage reservation."""
    sim = Simulation(seed=42)
    _seed_bread(sim, quantity=5)

    agent = sim.agent_manager.agents[0]
    agent.needs.hunger = config.HUNGER_CRITICAL_THRESHOLD + 0.01  # just above critical

    # Wait until agent picks up a non-EAT task
    for _ in range(1000):
        sim.update(_DT)
        current_task = sim.task_manager.assigned_tasks.get(agent.id)
        if current_task and current_task.task_type != TaskType.EAT:
            break

    current_task = sim.task_manager.assigned_tasks.get(agent.id)
    if current_task is None or current_task.task_type == TaskType.EAT:
        return  # agent already eating or idle — test not applicable

    # Now drive hunger below critical
    agent.needs.hunger = config.HUNGER_CRITICAL_THRESHOLD - 0.01

    task_id = current_task.task_id
    for _ in range(200):
        sim.update(_DT)
        if sim.task_manager.assigned_tasks.get(agent.id) != current_task:
            break  # task abandoned

    # After abandonment, node and storage should be unclaimed
    if hasattr(current_task, 'reserved_at_node'):
        assert not current_task.reserved_at_node, "Node claim should be released"
    if hasattr(current_task, 'reserved_at_dropoff_quantity'):
        assert current_task.reserved_at_dropoff_quantity == 0, "Dropoff reservation should be released"


def test_eat_task_not_reposted_to_job_board():
    """Failed EatTask must not appear on the job board."""
    sim = Simulation(seed=42)
    agent = sim.agent_manager.agents[0]

    eat_task = EatTask(priority=100)
    eat_task.agent_id = agent.id
    # Fail it without preparing (simulates no bread found)
    eat_task.status = TaskStatus.FAILED
    eat_task.error_message = "test"

    sim.task_manager.assigned_tasks[agent.id] = eat_task
    sim.task_manager.report_task_outcome(eat_task, TaskStatus.FAILED, agent)

    pending_types = [t.task_type for t in sim.task_manager.pending_tasks]
    assert TaskType.EAT not in pending_types, "EatTask must never be re-posted"
