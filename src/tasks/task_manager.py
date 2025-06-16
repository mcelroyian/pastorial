import uuid
import time
import logging # Added
from typing import List, Dict, Optional, TYPE_CHECKING

from .task import Task, GatherAndDeliverTask, DeliverWheatToMillTask # Added DeliverWheatToMillTask
from .task_types import TaskType, TaskStatus
from ..resources.resource_types import ResourceType # Assuming this path
from ..resources.mill import Mill # For checking Mill instances
from ..resources.processing import MultiInputProcessingStation
from ..core import config # For task generation settings
from ..agents.intents import IntentStatus # For type hinting

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
        self.logger = logging.getLogger(__name__) # Added
        
        self._next_task_check_time: float = time.time()
        self._task_generation_interval: float = 5.0 # How often to check for new task generation

    def add_task(self, task: Task):
        """Adds a pre-created task to the pending list, sorted by priority."""
        # Higher priority number means more important
        self.pending_tasks.append(task)
        self.pending_tasks.sort(key=lambda t: t.priority, reverse=True)
        self.logger.debug(f"TaskManager: Added new task {task.task_id} ({task.task_type.name}) P:{task.priority} to job board. Board size: {len(self.pending_tasks)}") # Changed

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

    def create_deliver_wheat_to_mill_task(self,
                                          quantity: int,
                                          priority: int) -> Optional[Task]:
        """
        Creates a new DeliverWheatToMillTask and adds it to the pending list.
        Agents undertaking this task must have an empty inventory.
        """
        # Future: Could add pre-checks for wheat in storage or mill availability,
        # but task.prepare() will handle the detailed validation and reservation.
        task = DeliverWheatToMillTask(
            priority=priority,
            quantity_to_retrieve=quantity
            # target_storage_id and target_processor_id can be set if known,
            # otherwise task.prepare() will find them.
        )
        self.add_task(task)
        self.logger.debug(f"TaskManager: Created DeliverWheatToMillTask {task.task_id} for {quantity} WHEAT, P:{priority}.") # Changed
        return task


    # def request_task_for_agent(self, agent: 'Agent') -> Optional[Task]:
    #     """
    #     DEPRECATED: Agents will now pull tasks from the job board.
    #     Assigns the highest priority available task to the given agent if one exists.
    #     Called by an agent when it becomes IDLE.
    #     """
    #     if not self.pending_tasks:
    #         return None
    #
    #     # Get the highest priority task
    #     # TODO: Add more sophisticated matching (e.g., agent skills, proximity, current inventory)
    #     task_to_assign = self.pending_tasks.pop(0) # Highest priority due to sort
    #
    #     task_to_assign.agent_id = agent.id
    #     task_to_assign.status = TaskStatus.ASSIGNED # Mark as assigned before prepare
    #     self.assigned_tasks[agent.id] = task_to_assign
    #
    #     print(f"TaskManager: Assigning task {task_to_assign.task_id} ({task_to_assign.task_type.name}) to agent {agent.id}. Assigned: {len(self.assigned_tasks)}")
    #     return task_to_assign

    def get_available_tasks(self) -> List[Task]:
        """Returns the current list of tasks on the job board (pending_tasks)."""
        return self.pending_tasks

    def attempt_claim_task(self, task_id: uuid.UUID, agent: 'Agent') -> Optional[Task]:
        """
        Allows an agent to attempt to claim a task from the job board.
        Returns the task if successfully claimed, None otherwise.
        """
        task_to_claim = None
        for i, task in enumerate(self.pending_tasks):
            if task.task_id == task_id:
                task_to_claim = self.pending_tasks.pop(i)
                break
        
        if task_to_claim:
            task_to_claim.agent_id = agent.id
            task_to_claim.status = TaskStatus.ASSIGNED # Or PREPARING if prepare is called immediately
            self.assigned_tasks[agent.id] = task_to_claim
            self.logger.info(f"TaskManager: Task {task_to_claim.task_id} ({task_to_claim.task_type.name}) CLAIMED by agent {agent.id}. Pending: {len(self.pending_tasks)}, Assigned: {len(self.assigned_tasks)}") # Changed
            return task_to_claim
        else:
            self.logger.warning(f"TaskManager: Agent {agent.id} FAILED to claim task {task_id}. Task not found or already claimed.") # Changed
            return None

    def report_task_outcome(self, task: Task, final_status: TaskStatus, agent: 'Agent'):
        """
        Called by an Agent when its current task is finished (completed, failed, or cancelled).
        """
        self.logger.debug(f"TaskManager: report_task_outcome CALLED by agent {agent.id} for task {task.task_id} (type: {task.task_type.name}) with status {final_status.name}. Current assigned_tasks keys: {list(self.assigned_tasks.keys())}, task.agent_id: {task.agent_id}")
        task.status = final_status # Ensure final status is set on the task object
        task.last_update_time = time.time()

        if agent.id in self.assigned_tasks and self.assigned_tasks[agent.id].task_id == task.task_id:
            self.logger.debug(f"TaskManager: Removing task {task.task_id} for agent {agent.id} from assigned_tasks.")
            del self.assigned_tasks[agent.id]
        else:
            self.logger.warning(f"TaskManager: Task {task.task_id} (agent {agent.id}) NOT removed from assigned_tasks. Agent ID in assigned: {agent.id in self.assigned_tasks}. Task ID matches: {self.assigned_tasks[agent.id].task_id == task.task_id if agent.id in self.assigned_tasks else 'N/A'}. Assigned task for agent: {self.assigned_tasks.get(agent.id)}") # Changed

        if final_status == TaskStatus.COMPLETED:
            self.completed_tasks.append(task)
            self.logger.info(f"TaskManager: Task {task.task_id} COMPLETED by agent {agent.id}. Completed: {len(self.completed_tasks)}") # Changed
        elif final_status == TaskStatus.FAILED:
            self.failed_tasks.append(task) # Keep a record of failed tasks
            self.logger.warning(f"TaskManager: Task {task.task_id} FAILED for agent {agent.id}. Reason: {task.error_message}. Failed list size: {len(self.failed_tasks)}") # Changed
            
            # Re-post task to job board (simple re-posting for now)
            # TODO: Add more sophisticated logic for re-posting (e.g., delay, modification, max retries)
            self.logger.info(f"TaskManager: Re-posting task {task.task_id} ({task.task_type.name}) to job board due to FAILED status.") # Changed
            task.status = TaskStatus.PENDING # Reset status
            task.agent_id = None # Unassign agent
            # task.error_message = None # Optionally clear error message or append to a list of errors
            self.add_task(task) # add_task handles sorting by priority

        elif final_status == TaskStatus.CANCELLED:
            # If cancelled, it might just be removed or put in a separate list
            # For now, treat like failed for tracking, or add a cancelled_tasks list.
            # Depending on policy, cancelled tasks might also be re-posted or archived.
            self.failed_tasks.append(task) # Or a self.cancelled_tasks list
            self.logger.info(f"TaskManager: Task {task.task_id} CANCELLED for agent {agent.id}. Added to failed/cancelled list.") # Changed


    def assign_task_to_agent(self, agent: 'Agent', resource_manager: 'ResourceManager') -> bool:
        """
        Finds a suitable task for the agent, assigns it, and initiates its preparation.
        Returns True if a task was successfully assigned and its preparation started, False otherwise.
        """
        self.logger.debug(f"TaskManager: Agent {agent.id} requesting a task.")
        if not self.pending_tasks:
            self.logger.debug(f"TaskManager: No pending tasks available for agent {agent.id}.")
            return False

        # Iterate over a copy for safe removal, sorted by priority (already sorted by add_task)
        for i, task in enumerate(list(self.pending_tasks)): # Iterate a copy
            # Pre-qualification checks (simplified version of old Agent._evaluate_and_select_task)
            # TODO: Enhance this pre-qualification logic
            can_perform_task = False
            if isinstance(task, GatherAndDeliverTask):
                # Basic check: agent inventory not full with a different resource type
                if agent.current_inventory['quantity'] == 0 or \
                   agent.current_inventory['resource_type'] == task.resource_type_to_gather or \
                   (agent.current_inventory['quantity'] < agent.inventory_capacity):
                    can_perform_task = True
            elif isinstance(task, DeliverWheatToMillTask):
                if agent.current_inventory['quantity'] == 0: # Must have empty inventory
                    can_perform_task = True
            else:
                can_perform_task = True # Default for other task types for now

            if not can_perform_task:
                self.logger.debug(f"TaskManager: Agent {agent.id} cannot perform task {task.task_id} ({task.task_type.name}) due to pre-qualification.")
                continue

            # Attempt to claim the task (by removing it from the original list)
            try:
                actual_task_idx = -1
                for original_idx, original_task_obj in enumerate(self.pending_tasks):
                    if original_task_obj.task_id == task.task_id:
                        actual_task_idx = original_idx
                        break
                
                if actual_task_idx != -1:
                    claimed_task = self.pending_tasks.pop(actual_task_idx)
                else:
                    self.logger.debug(f"TaskManager: Task {task.task_id} was no longer in pending_tasks (claimed by another agent?).")
                    continue # Task was claimed by another agent or removed

                self.logger.info(f"TaskManager: Attempting to assign task {claimed_task.task_id} ({claimed_task.task_type.name}) to agent {agent.id}.")
                claimed_task.agent_id = agent.id
                claimed_task.status = TaskStatus.ASSIGNED # Mark as assigned before prepare
                self.assigned_tasks[agent.id] = claimed_task

                if claimed_task.prepare(agent, resource_manager):
                    self.logger.info(f"TaskManager: Task {claimed_task.task_id} successfully prepared and assigned to agent {agent.id}.")
                    # task.prepare() should have submitted an intent to the agent.
                    return True # Task assigned and preparation started
                else:
                    self.logger.warning(f"TaskManager: Task {claimed_task.task_id} FAILED preparation for agent {agent.id}. Error: {claimed_task.error_message}")
                    # report_task_outcome will handle moving it from assigned_tasks and re-posting/failing it.
                    self.report_task_outcome(claimed_task, TaskStatus.FAILED, agent)
                    # Continue to check for other tasks for this agent in this cycle
            
            except ValueError: # If task was already removed from pending_tasks
                self.logger.debug(f"TaskManager: Task {task.task_id} was already removed from pending list, likely claimed by another agent.")
                continue # Try next task

        self.logger.debug(f"TaskManager: No suitable task found or assigned for agent {agent.id} after checking {len(self.pending_tasks)} tasks.")
        return False

    def notify_task_intent_outcome(self,
                                   task_id: uuid.UUID,
                                   intent_id: uuid.UUID,
                                   intent_status: IntentStatus,
                                   resource_manager: 'ResourceManager',
                                   agent: 'Agent'): # Added agent
        """
        Called by an Agent when an Intent associated with a Task has an outcome.
        This method finds the task and calls its on_intent_outcome method.
        """
        self.logger.debug(f"TaskManager: Received intent outcome for task {task_id}, intent {intent_id}, status {intent_status.name} from agent {agent.id}")
        
        # Find the task. It could be in pending_tasks (if prepare submitted an intent and it's still there)
        # or more likely in assigned_tasks.
        task_to_notify: Optional[Task] = None
        
        # Check assigned tasks first
        for assigned_agent_id, task in self.assigned_tasks.items():
            if task.task_id == task_id:
                if assigned_agent_id == agent.id: # Ensure the notification is from the correct agent
                    task_to_notify = task
                    break
                else:
                    self.logger.warning(f"TaskManager: Intent outcome for task {task_id} received from agent {agent.id}, but task is assigned to agent {assigned_agent_id}.")
                    return # Or handle as an error

        # If not found in assigned, check pending (less likely for ongoing intents but possible for initial ones)
        if not task_to_notify:
            for task in self.pending_tasks:
                if task.task_id == task_id:
                    # This scenario is unusual for an intent outcome unless it's an immediate failure during prepare.
                    self.logger.warning(f"TaskManager: Intent outcome for task {task_id} which is still in PENDING list. Agent: {agent.id}")
                    task_to_notify = task # Allow it, task.on_intent_outcome should handle its state.
                    break
        
        if task_to_notify:
            self.logger.debug(f"TaskManager: Relaying intent outcome to task {task_to_notify.task_id} ({task_to_notify.task_type.name}).")
            task_to_notify.on_intent_outcome(agent, intent_id, intent_status, resource_manager)
            # The task's on_intent_outcome might change its status.
            # If the task becomes COMPLETED or FAILED, the agent's main loop should then call report_task_outcome.
            # Or, if on_intent_outcome determines the task is finished, it could directly update its status
            # and the agent's main loop would pick that up.
            # For now, we assume the agent will call report_task_outcome based on the task's status after this.
        else:
            self.logger.warning(f"TaskManager: Could not find task {task_id} to notify about intent {intent_id} outcome from agent {agent.id}. It might have already completed/failed.")


    def update(self, dt: float):
        """
        Periodic update for the TaskManager.
        - Can generate new tasks based on simulation state (e.g., low resources).
        - Can re-prioritize tasks.
        - Can check for timed-out tasks.
        """
        current_time = time.time()
        if current_time >= self._next_task_check_time:
            self.logger.debug(f"TaskManager: Update - time to check for task generation. Current time: {current_time:.2f}, Next check: {self._next_task_check_time:.2f}") # Changed
            self._generate_tasks_if_needed()
            self._next_task_check_time = current_time + self._task_generation_interval
        # else:
            # self.logger.debug(f"TaskManager: Update - NOT time to check for task generation. Current time: {current_time:.2f}, Next check: {self._next_task_check_time:.2f}") # Changed


        # TODO: Check for tasks that are assigned but stuck (e.g., agent died, task timed out)
        # This would involve iterating self.assigned_tasks and checking task.last_update_time

    def _generate_tasks_if_needed(self):
        """
        Generates tasks based on simulation state, e.g., low resource stock.
        Currently implements logic for Berry stock.
        """
        self.logger.debug(f"TaskManager: _generate_tasks_if_needed CALLED. Pending: {len(self.pending_tasks)}, Assigned: {len(self.assigned_tasks)}")
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

            # self.logger.debug(f"TaskManager: Active berry gather tasks: {active_berry_gather_tasks}, Max Allowed: {config.MAX_ACTIVE_BERRY_GATHER_TASKS}") # Changed

            if active_berry_gather_tasks < config.MAX_ACTIVE_BERRY_GATHER_TASKS:
                self.logger.info(f"TaskManager: Low Berry Stock ({current_berry_stock} < {config.MIN_BERRY_STOCK_LEVEL}). Generating new GatherAndDeliverTask for BERRY.") # Changed
                self.create_gather_task(
                    resource_type=ResourceType.BERRY,
                    quantity=config.BERRY_GATHER_TASK_QUANTITY,
                    priority=config.BERRY_GATHER_TASK_PRIORITY
                )
            else:
                self.logger.debug(f"TaskManager: Berry stock low ({current_berry_stock}), but max active berry tasks ({active_berry_gather_tasks}/{config.MAX_ACTIVE_BERRY_GATHER_TASKS}) reached. No new BERRY task.") # Changed
        # else:
            # self.logger.debug(f"TaskManager: Berry stock ({current_berry_stock}) is sufficient. No new berry task needed.") # Changed

# --- Wheat Task Generation ---
        current_wheat_stock = self.resource_manager_ref.get_global_resource_quantity(ResourceType.WHEAT)
        
        # self.logger.debug(f"TaskManager: Current global wheat stock: {current_wheat_stock}, Min Level: {config.MIN_WHEAT_STOCK_LEVEL}") # Changed

        if current_wheat_stock < config.MIN_WHEAT_STOCK_LEVEL:
            active_wheat_gather_tasks = sum(
                1 for task in self.pending_tasks
                if isinstance(task, GatherAndDeliverTask) and task.resource_type_to_gather == ResourceType.WHEAT
            )
            active_wheat_gather_tasks += sum(
                1 for task in self.assigned_tasks.values()
                if isinstance(task, GatherAndDeliverTask) and task.resource_type_to_gather == ResourceType.WHEAT
            )

            # self.logger.debug(f"TaskManager: Active wheat gather tasks: {active_wheat_gather_tasks}, Max Allowed: {config.MAX_ACTIVE_WHEAT_GATHER_TASKS}") # Changed

            if active_wheat_gather_tasks < config.MAX_ACTIVE_WHEAT_GATHER_TASKS:
                self.logger.info(f"TaskManager: Low Wheat Stock ({current_wheat_stock} < {config.MIN_WHEAT_STOCK_LEVEL}). Generating new GatherAndDeliverTask for WHEAT.") # Changed
                self.create_gather_task(
                    resource_type=ResourceType.WHEAT,
                    quantity=config.WHEAT_GATHER_TASK_QUANTITY,
                    priority=config.WHEAT_GATHER_TASK_PRIORITY
                )
            else:
                self.logger.debug(f"TaskManager: Wheat stock low ({current_wheat_stock}), but max active wheat tasks ({active_wheat_gather_tasks}/{config.MAX_ACTIVE_WHEAT_GATHER_TASKS}) reached. No new WHEAT task.") # Changed
        # else:
            # self.logger.debug(f"TaskManager: Wheat stock ({current_wheat_stock}) is sufficient. No new wheat task needed.") # Changed

        # --- Flour (from Wheat) Task Generation ---
        # This task involves an agent picking up Wheat from storage and delivering it to a Mill.
        min_flour_stock_config = getattr(config, 'MIN_FLOUR_STOCK_LEVEL', 20)
        current_flour_stock = self.resource_manager_ref.get_global_resource_quantity(ResourceType.FLOUR_POWDER)
        self.logger.debug(f"FLOUR_TASK: Current Flour: {current_flour_stock}, Min Required: {min_flour_stock_config}") # Changed

        if current_flour_stock < min_flour_stock_config:
            self.logger.debug(f"FLOUR_TASK: Flour stock is LOW ({current_flour_stock} < {min_flour_stock_config}). Proceeding with checks.") # Changed
            
            process_wheat_qty_config = getattr(config, 'PROCESS_WHEAT_TASK_QUANTITY', 10)
            wheat_in_storage = self.resource_manager_ref.get_global_resource_quantity(ResourceType.WHEAT)
            self.logger.debug(f"FLOUR_TASK: Wheat in storage: {wheat_in_storage}, Required for task: {process_wheat_qty_config}") # Changed
            
            mill_can_accept = False
            self.logger.debug(f"FLOUR_TASK: Checking Mills... Total stations: {len(self.resource_manager_ref.processing_stations)}") # Changed
            for i, station in enumerate(self.resource_manager_ref.processing_stations):
                is_mill_instance = isinstance(station, Mill)
                can_accept_input = False
                if is_mill_instance:
                    can_accept_input = station.can_accept_input(ResourceType.WHEAT, 1) # type: ignore
                self.logger.debug(f"FLOUR_TASK: Station {i}: Type={type(station).__name__}, IsMill={is_mill_instance}, CanAcceptWheat={can_accept_input}, Pos={station.position if hasattr(station, 'position') else 'N/A'}") # Changed
                if is_mill_instance and can_accept_input:
                    mill_can_accept = True
                    self.logger.debug(f"FLOUR_TASK: Found suitable Mill: {station.position}") # Changed
                    break
            self.logger.debug(f"FLOUR_TASK: Mill can accept WHEAT: {mill_can_accept}") # Changed
            
            if wheat_in_storage >= process_wheat_qty_config and mill_can_accept:
                self.logger.debug(f"FLOUR_TASK: Wheat available ({wheat_in_storage} >= {process_wheat_qty_config}) AND Mill can accept. Checking active tasks...") # Changed
                active_process_wheat_tasks = sum(
                    1 for task in self.pending_tasks + list(self.assigned_tasks.values())
                    if isinstance(task, DeliverWheatToMillTask)
                )
                max_active_config = getattr(config, 'MAX_ACTIVE_PROCESS_WHEAT_TASKS', 2)
                self.logger.debug(f"FLOUR_TASK: Active DeliverWheatToMill tasks: {active_process_wheat_tasks}, Max Allowed: {max_active_config}") # Changed

                if active_process_wheat_tasks < max_active_config:
                    self.logger.info(f"FLOUR_TASK: All conditions met. Generating new DeliverWheatToMillTask.") # Changed
                    self.create_deliver_wheat_to_mill_task(
                        quantity=process_wheat_qty_config,
                        priority=getattr(config, 'PROCESS_WHEAT_TASK_PRIORITY', 75)
                    )
                else:
                    self.logger.debug(f"FLOUR_TASK: Max active DeliverWheatToMill tasks ({active_process_wheat_tasks}/{max_active_config}) reached. No new task.") # Changed
            else:
                self.logger.debug(f"FLOUR_TASK: Conditions not met for task creation:") # Changed
                if not (wheat_in_storage >= process_wheat_qty_config):
                    self.logger.debug(f"FLOUR_TASK: -> Not enough WHEAT in storage ({wheat_in_storage} < {process_wheat_qty_config}).") # Changed
                if not mill_can_accept:
                    self.logger.debug(f"FLOUR_TASK: -> No Mill can accept WHEAT currently.") # Changed
        else:
            self.logger.debug(f"FLOUR_TASK: Flour stock ({current_flour_stock}) is sufficient (>= {min_flour_stock_config}). No new DeliverWheatToMill task needed.") # Changed

        # --- Recipe-based Task Generation ---
        for station in self.resource_manager_ref.processing_stations:
            if isinstance(station, MultiInputProcessingStation):
                for resource_type, required_qty in station.recipe.inputs.items():
                    # Quick fix: Don't generate gather tasks for flour, it's handled by stock levels
                    if resource_type == ResourceType.FLOUR_POWDER:
                        continue

                    current_qty = station.current_input_quantity.get(resource_type, 0)
                    if current_qty < required_qty:
                        # How many are needed to satisfy the recipe?
                        needed_qty = required_qty - current_qty

                        # Are there already tasks to deliver this resource to this station?
                        active_delivery_qty = 0
                        for task in self.pending_tasks + list(self.assigned_tasks.values()):
                            if isinstance(task, GatherAndDeliverTask) and \
                               task.resource_type_to_gather == resource_type and \
                               task.target_dropoff_ref and task.target_dropoff_ref.id == station.id:
                                active_delivery_qty += task.quantity_to_gather

                        if needed_qty > active_delivery_qty:
                            self.logger.info(f"Station {station.id} needs {needed_qty - active_delivery_qty} of {resource_type.name}. Creating GatherAndDeliverTask.")
                            self.create_gather_task(
                                resource_type=resource_type,
                                quantity=int(needed_qty - active_delivery_qty),
                                priority=config.PROVISION_TASK_PRIORITY, # We can reuse this
                                target_dropoff_id=station.id
                            )


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