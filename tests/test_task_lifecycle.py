from src.core.simulation import Simulation
from src.tasks.task import GatherAndDeliverTask
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
