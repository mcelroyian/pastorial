import pygame
from src.core.simulation import Simulation
from src.tasks.task import GatherAndDeliverTask, PatrolTask
from src.tasks.task_types import TaskStatus
from src.resources.resource_types import ResourceType

_MAX_TICKS = 3000
_DT = 1 / 60


def test_gather_deliver_starts_pending():
    sim = Simulation(seed=42)
    task = GatherAndDeliverTask(
        priority=100,
        resource_type_to_gather=ResourceType.BERRY,
        quantity_to_gather=3,
    )
    sim.task_manager.add_task(task)
    assert task.status == TaskStatus.PENDING


def test_gather_deliver_completes():
    sim = Simulation(seed=42)
    task = GatherAndDeliverTask(
        priority=100,
        resource_type_to_gather=ResourceType.BERRY,
        quantity_to_gather=3,
    )
    sim.task_manager.add_task(task)

    for _ in range(_MAX_TICKS):
        sim.update(_DT)
        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            break

    assert task.status == TaskStatus.COMPLETED, (
        f"Task ended in {task.status.name} after {_MAX_TICKS} ticks. "
        f"Error: {task.error_message}"
    )


def test_completed_task_appears_in_manager_history():
    sim = Simulation(seed=42)
    task = GatherAndDeliverTask(
        priority=100,
        resource_type_to_gather=ResourceType.BERRY,
        quantity_to_gather=3,
    )
    sim.task_manager.add_task(task)

    for _ in range(_MAX_TICKS):
        sim.update(_DT)
        if task.status == TaskStatus.COMPLETED:
            break

    assert any(t.task_id == task.task_id for t in sim.task_manager.completed_tasks)


def test_patrol_task_completes():
    sim = Simulation(seed=42)
    grid = sim.grid
    # Use positions near agent spawn so pathfinding is short
    agent = sim.agent_manager.agents[0]
    cx, cy = int(agent.position.x), int(agent.position.y)
    # Find two walkable positions within ±8 cells of the agent, separated by >= 3 cells
    nearby = [
        pygame.math.Vector2(x, y)
        for y in range(max(0, cy - 8), min(grid.height_in_cells, cy + 8))
        for x in range(max(0, cx - 8), min(grid.width_in_cells, cx + 8))
        if grid.is_walkable(x, y)
    ]
    point_a = nearby[0]
    point_b = next(p for p in nearby if (p - point_a).length() >= 3)
    task = PatrolTask(priority=150, point_a=point_a, point_b=point_b)
    sim.task_manager.add_task(task)

    for _ in range(6000):
        sim.update(_DT)
        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            break

    assert task.status == TaskStatus.COMPLETED, (
        f"PatrolTask ended in {task.status.name}. Error: {task.error_message}"
    )
