import uuid
import time
from typing import List, Dict, Optional, TYPE_CHECKING

from .task import Task, GatherAndDeliverTask # Assuming task.py is in the same directory
from .task_types import TaskType, TaskStatus
from ..resources.resource_types import ResourceType # Assuming this path
from ..core import config # For task generation settings

# Forward references to avoid circular imports
if TYPE_CHECKING:
    from ..agents.agent import Agent
    from ..agents.manager import AgentManager
    from ..resources.manager import ResourceManager

class TaskManager:
    """Manages the creation, assignment, and tracking of tasks for agents."""

    def __init__(self, resource_manager: 'ResourceManager', agent_manager: 'AgentManager'):
        self.pending_tasks: List[Task] = []
        self.assigned_tasks: Dict[uuid.UUID, Task] = {} # agent_id -> Task
        self.completed_tasks: List[Task] = [] # For history/metrics
        self.failed_tasks: List[Task] = []     # For analysis/retry
        
        self.resource_manager_ref: 'ResourceManager' = resource_manager
        self.agent_manager_ref: 'AgentManager' = agent_manager
        
        self._next_task_check_time: float = time.time()
        self._task_generation_interval: float = 5.0 # How often to check for new task generation

    def add_task(self, task: Task):
        """Adds a pre-created task to the pending list, sorted by priority."""
        # Higher priority number means more important
        self.pending_tasks.append(task)
        self.pending_tasks.sort(key=lambda t: t.priority, reverse=True)
        print(f"TaskManager: Added new task {task.task_id} ({task.task_type.name}) with priority {task.priority}. Pending: {len(self.pending_tasks)}")

    def create_gather_task(self,
                           resource_type: ResourceType,
                           quantity: int,
                           priority: int,
                           target_dropoff_id: Optional[uuid.UUID] = None, # Optional: specific dropoff
                           target_resource_node_id: Optional[uuid.UUID] = None # Optional: specific node
                           ) -> Optional[Task]:
        """
        Creates a new GatherAndDeliverTask and adds it to the pending list.
        The actual finding of suitable nodes/dropoffs if not specified will occur in Task.prepare().
        """
        # Basic validation: Ensure resource manager can find nodes/dropoffs for this type
        # This is a pre-check; Task.prepare() does the actual claiming/reservation.
        # For now, we assume the task can be created and prepare() will validate further.
        
        task = GatherAndDeliverTask(
            priority=priority,
            resource_type_to_gather=resource_type,
            quantity_to_gather=quantity,
            target_resource_node_id=target_resource_node_id,
            target_dropoff_id=target_dropoff_id
        )
        self.add_task(task)
        return task

    def request_task_for_agent(self, agent: 'Agent') -> Optional[Task]:
        """
        Assigns the highest priority available task to the given agent if one exists.
        Called by an agent when it becomes IDLE.
        """
        if not self.pending_tasks:
            return None

        # Get the highest priority task
        # TODO: Add more sophisticated matching (e.g., agent skills, proximity, current inventory)
        task_to_assign = self.pending_tasks.pop(0) # Highest priority due to sort
        
        task_to_assign.agent_id = agent.id
        task_to_assign.status = TaskStatus.ASSIGNED # Mark as assigned before prepare
        self.assigned_tasks[agent.id] = task_to_assign
        
        print(f"TaskManager: Assigning task {task_to_assign.task_id} ({task_to_assign.task_type.name}) to agent {agent.id}. Assigned: {len(self.assigned_tasks)}")
        return task_to_assign

    def report_task_outcome(self, task: Task, final_status: TaskStatus, agent: 'Agent'):
        """
        Called by an Agent when its current task is finished (completed, failed, or cancelled).
        """
        task.status = final_status # Ensure final status is set on the task object
        task.last_update_time = time.time()

        if agent.id in self.assigned_tasks and self.assigned_tasks[agent.id].task_id == task.task_id:
            del self.assigned_tasks[agent.id]
        else:
            print(f"Warning: TaskManager received outcome for task {task.task_id} from agent {agent.id}, but it was not in assigned_tasks or mismatch.")

        if final_status == TaskStatus.COMPLETED:
            self.completed_tasks.append(task)
            print(f"TaskManager: Task {task.task_id} COMPLETED by agent {agent.id}. Completed: {len(self.completed_tasks)}")
        elif final_status == TaskStatus.FAILED:
            self.failed_tasks.append(task)
            print(f"TaskManager: Task {task.task_id} FAILED for agent {agent.id}. Reason: {task.error_message}. Failed: {len(self.failed_tasks)}")
            # TODO: Potential re-queueing or modification logic for failed tasks
        elif final_status == TaskStatus.CANCELLED:
            # If cancelled, it might just be removed or put in a separate list
            print(f"TaskManager: Task {task.task_id} CANCELLED for agent {agent.id}. Failed: {len(self.failed_tasks)}")
            # For now, treat like failed for tracking, or add a cancelled_tasks list.
            self.failed_tasks.append(task) 


    def update(self, dt: float):
        """
        Periodic update for the TaskManager.
        - Can generate new tasks based on simulation state (e.g., low resources).
        - Can re-prioritize tasks.
        - Can check for timed-out tasks.
        """
        current_time = time.time()
        if current_time >= self._next_task_check_time:
            self._generate_tasks_if_needed()
            self._next_task_check_time = current_time + self._task_generation_interval

        # TODO: Check for tasks that are assigned but stuck (e.g., agent died, task timed out)
        # This would involve iterating self.assigned_tasks and checking task.last_update_time

    def _generate_tasks_if_needed(self):
        """
        Generates tasks based on simulation state, e.g., low resource stock.
        Currently implements logic for Berry stock.
        """
        # --- Berry Task Generation ---
        current_berry_stock = self.resource_manager_ref.get_global_resource_quantity(ResourceType.BERRY)
        
        # print(f"DEBUG TaskManager: Current global berry stock: {current_berry_stock}, Min Level: {config.MIN_BERRY_STOCK_LEVEL}") # Debug

        if current_berry_stock < config.MIN_BERRY_STOCK_LEVEL:
            # Count existing GATHER_AND_DELIVER tasks for BERRY (pending or assigned)
            active_berry_gather_tasks = sum(
                1 for task in self.pending_tasks
                if isinstance(task, GatherAndDeliverTask) and task.resource_type_to_gather == ResourceType.BERRY
            )
            active_berry_gather_tasks += sum(
                1 for task in self.assigned_tasks.values()
                if isinstance(task, GatherAndDeliverTask) and task.resource_type_to_gather == ResourceType.BERRY
            )

            # print(f"DEBUG TaskManager: Active berry gather tasks: {active_berry_gather_tasks}, Max Allowed: {config.MAX_ACTIVE_BERRY_GATHER_TASKS}") # Debug

            if active_berry_gather_tasks < config.MAX_ACTIVE_BERRY_GATHER_TASKS:
                print(f"TaskManager: Low Berry Stock ({current_berry_stock} < {config.MIN_BERRY_STOCK_LEVEL}). Generating new GatherAndDeliverTask for BERRY.")
                self.create_gather_task(
                    resource_type=ResourceType.BERRY,
                    quantity=config.BERRY_GATHER_TASK_QUANTITY,
                    priority=config.BERRY_GATHER_TASK_PRIORITY
                )
            # else:
                # print(f"DEBUG TaskManager: Berry stock low, but max active berry tasks ({config.MAX_ACTIVE_BERRY_GATHER_TASKS}) reached.") # Debug
        # else:
            # print(f"DEBUG TaskManager: Berry stock ({current_berry_stock}) is sufficient. No new berry task needed.") # Debug

# --- Wheat Task Generation ---
        current_wheat_stock = self.resource_manager_ref.get_global_resource_quantity(ResourceType.WHEAT)
        
        # print(f"DEBUG TaskManager: Current global wheat stock: {current_wheat_stock}, Min Level: {config.MIN_WHEAT_STOCK_LEVEL}") # Debug

        if current_wheat_stock < config.MIN_WHEAT_STOCK_LEVEL:
            active_wheat_gather_tasks = sum(
                1 for task in self.pending_tasks
                if isinstance(task, GatherAndDeliverTask) and task.resource_type_to_gather == ResourceType.WHEAT
            )
            active_wheat_gather_tasks += sum(
                1 for task in self.assigned_tasks.values()
                if isinstance(task, GatherAndDeliverTask) and task.resource_type_to_gather == ResourceType.WHEAT
            )

            # print(f"DEBUG TaskManager: Active wheat gather tasks: {active_wheat_gather_tasks}, Max Allowed: {config.MAX_ACTIVE_WHEAT_GATHER_TASKS}") # Debug

            if active_wheat_gather_tasks < config.MAX_ACTIVE_WHEAT_GATHER_TASKS:
                print(f"TaskManager: Low Wheat Stock ({current_wheat_stock} < {config.MIN_WHEAT_STOCK_LEVEL}). Generating new GatherAndDeliverTask for WHEAT.")
                self.create_gather_task(
                    resource_type=ResourceType.WHEAT,
                    quantity=config.WHEAT_GATHER_TASK_QUANTITY,
                    priority=config.WHEAT_GATHER_TASK_PRIORITY
                )
            # else:
                # print(f"DEBUG TaskManager: Wheat stock low, but max active wheat tasks ({config.MAX_ACTIVE_WHEAT_GATHER_TASKS}) reached.") # Debug
        # else:
            # print(f"DEBUG TaskManager: Wheat stock ({current_wheat_stock}) is sufficient. No new wheat task needed.") # Debug
        # TODO: Future: Add logic for other resource types here, following a similar pattern.
        # Example: Check Wheat storage and create tasks if low (conceptual)
        # current_wheat_stock = self.resource_manager_ref.get_global_resource_quantity(ResourceType.WHEAT)
        # if current_wheat_stock < getattr(config, 'MIN_WHEAT_STOCK_LEVEL', 0): # Assuming MIN_WHEAT_STOCK_LEVEL in config
        #     # ... similar logic to create wheat gathering tasks ...
        #     pass


    def get_task_by_id(self, task_id: uuid.UUID) -> Optional[Task]:
        """Retrieves a task by its ID from any of the lists."""
        for task_list in [self.pending_tasks, list(self.assigned_tasks.values()), self.completed_tasks, self.failed_tasks]:
            for task in task_list:
                if task.task_id == task_id:
                    return task
        return None

    def get_all_tasks_count(self) -> Dict[str, int]:
        return {
            "pending": len(self.pending_tasks),
            "assigned": len(self.assigned_tasks),
            "completed": len(self.completed_tasks),
            "failed": len(self.failed_tasks)
        }