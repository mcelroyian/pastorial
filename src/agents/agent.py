import pygame
import uuid # For agent ID
from enum import Enum, auto
import random
from typing import List, Dict, Optional, TYPE_CHECKING
import math # For math.inf

from ..resources.resource_types import ResourceType
from ..core import config # Agent still uses config for timers, capacity if not overridden by task

# Forward references for type hinting
if TYPE_CHECKING:
    from ..tasks.task import Task
    from ..tasks.task_manager import TaskManager
    from ..resources.manager import ResourceManager # For passing to tasks
    # from ..core.grid import Grid # Assuming Grid class type hint


class AgentState(Enum):
    """Defines the possible states an agent can be in. Tasks will set these."""
    IDLE = auto()
    MOVING_RANDOMLY = auto()
    MOVING_TO_RESOURCE = auto()
    GATHERING_RESOURCE = auto()
    MOVING_TO_STORAGE = auto()
    DELIVERING_RESOURCE = auto()
    MOVING_TO_PROCESSOR = auto()
    DELIVERING_TO_PROCESSOR = auto()
    COLLECTING_FROM_PROCESSOR = auto()
    EVALUATING_TASKS = auto() # New state for job board interaction

class Agent:
    """Represents an autonomous agent in the simulation, executing tasks."""

    def __init__(self,
                 agent_id: uuid.UUID, 
                 position: pygame.math.Vector2,
                 speed: float,
                 grid, # 'Grid' type hint
                 task_manager: 'TaskManager', 
                 inventory_capacity: int,
                 resource_priorities: Optional[List[ResourceType]] = None):
        """
        Initializes an Agent.
        Args:
            agent_id (uuid.UUID): Unique identifier for this agent.
            position (pygame.math.Vector2): The starting grid coordinates of the agent.
            speed (float): The movement speed of the agent (grid units per second).
            grid (Grid): The simulation grid object.
            task_manager (TaskManager): Reference to the global task manager.
            inventory_capacity (int): Maximum number of resource units the agent can carry.
            resource_priorities (Optional[List[ResourceType]]): Ordered list of resource types the agent prefers.
                                                               Might be used by TaskManager.
        """
        self.id: uuid.UUID = agent_id
        self.position = position
        self.speed = speed
        self.grid = grid # type: ignore
        self.task_manager_ref: 'TaskManager' = task_manager
        self.config = config 

        self.state = AgentState.IDLE
        self.target_position: Optional[pygame.math.Vector2] = None # Set by tasks
        self.color = (255, 255, 0)

        self.state_colors = {
            AgentState.IDLE: (255, 255, 0),
            AgentState.MOVING_RANDOMLY: (255, 165, 0),
            AgentState.MOVING_TO_RESOURCE: (0, 200, 50),
            AgentState.GATHERING_RESOURCE: (50, 150, 255),
            AgentState.MOVING_TO_STORAGE: (0, 200, 200),
            AgentState.DELIVERING_RESOURCE: (100, 100, 255),
            AgentState.MOVING_TO_PROCESSOR: (255, 140, 0),
            AgentState.DELIVERING_TO_PROCESSOR: (138, 43, 226),
            AgentState.COLLECTING_FROM_PROCESSOR: (0, 128, 128),
            AgentState.EVALUATING_TASKS: (200, 200, 200), # Light grey for evaluating
        }
        self.target_tolerance = 0.1
        self.task_evaluation_cooldown = 1.0 # Seconds before trying to evaluate tasks again if none found
        self._last_task_evaluation_time = 0.0


        self.inventory_capacity: int = inventory_capacity
        self.current_inventory: Dict[str, Optional[ResourceType] | int] = {
            'resource_type': None,
            'quantity': 0
        }
        
        self.current_task: Optional['Task'] = None
        self.resource_priorities: Optional[List[ResourceType]] = resource_priorities

        self.gathering_timer: float = 0.0
        self.delivery_timer: float = 0.0

    def set_target(self, target_position: pygame.math.Vector2):
        """Sets the agent's target position. Primarily called by tasks."""
        self.target_position = target_position
        # The agent's state (e.g., MOVING_TO_RESOURCE) should be set by the task itself.
        # print(f"DEBUG: Agent {self.id} set_target: NewTargetGridPos={self.target_position}")

    def _move_towards_target(self, dt: float) -> bool:
        """
        Moves the agent towards its target position.
        Args: dt (float): Delta time.
        Returns: bool: True if the target was reached this frame, False otherwise.
        """
        if self.target_position is None:
            return False

        direction = self.target_position - self.position
        distance = direction.length()

        if distance < self.target_tolerance:
            self.position = pygame.math.Vector2(self.target_position) 
            self.target_position = None 
            return True
        elif distance > 0:
            normalized_direction = direction.normalize()
            movement = normalized_direction * self.speed * dt
            if movement.length() >= distance:
                self.position = pygame.math.Vector2(self.target_position)
                self.target_position = None
                return True
            else:
                self.position += movement
        return False

    def _move_randomly(self, dt: float):
        """Moves the agent randomly within the grid bounds."""
        if self.target_position is None: 
            if self.grid.width_in_cells > 0 and self.grid.height_in_cells > 0: # type: ignore
                self.target_position = pygame.math.Vector2(
                    random.uniform(0, self.grid.width_in_cells - 1), # type: ignore
                    random.uniform(0, self.grid.height_in_cells - 1) # type: ignore
                )
                self.target_position.x = max(0, min(self.target_position.x, self.grid.width_in_cells - 1)) # type: ignore
                self.target_position.y = max(0, min(self.target_position.y, self.grid.height_in_cells - 1)) # type: ignore
            else: 
                self.state = AgentState.IDLE 
                return

        if self._move_towards_target(dt):
            self.state = AgentState.IDLE

    def _evaluate_and_select_task(self, available_tasks: List['Task'], resource_manager: 'ResourceManager') -> Optional['Task']:
        """
        Evaluates available tasks and selects one based on agent's logic,
        checking for resource availability, dropoff space, and inventory compatibility.
        """
        from ..tasks.task import GatherAndDeliverTask # Local import for type checking

        candidate_tasks: List[Task] = []

        for task in available_tasks:
            if not isinstance(task, GatherAndDeliverTask): # For now, only evaluate GatherAndDeliverTasks
                print(f"DEBUG: Agent {self.id} skipping non-GatherAndDeliverTask {task.task_id} ({task.task_type.name}).")
                continue

            task_resource_type = task.resource_type_to_gather
            print(f"DEBUG: Agent {self.id} evaluating task {task.task_id} ({task.task_type.name}) for resource {task_resource_type.name}.")

            # 1. Check Agent's Resource Priorities
            if self.resource_priorities and task_resource_type not in self.resource_priorities:
                print(f"DEBUG: Agent {self.id}: Task {task.task_id} resource {task_resource_type.name} not in priorities {self.resource_priorities}. Skipping.")
                continue
            
            # 2. Check Source Availability (using ResourceManager)
            if not resource_manager.has_available_sources(task_resource_type, min_quantity=1):
                print(f"DEBUG: Agent {self.id}: Task {task.task_id} - No available sources for {task_resource_type.name}. Skipping.")
                continue
            
            # 3. Check Dropoff Availability (using ResourceManager)
            # Consider quantity agent might carry - for now, just check if *any* space.
            # A more advanced check would be: min_capacity = min(self.inventory_capacity, task.quantity_to_gather)
            if not resource_manager.has_available_dropoffs(task_resource_type, min_capacity=1):
                print(f"DEBUG: Agent {self.id}: Task {task.task_id} - No available dropoffs for {task_resource_type.name}. Skipping.")
                continue

            # 4. Check Agent Inventory Compatibility & Capacity
            current_inv_qty = self.current_inventory.get('quantity', 0)
            current_inv_type = self.current_inventory.get('resource_type')

            if current_inv_qty > 0 and current_inv_type != task_resource_type:
                remaining_capacity = self.inventory_capacity - current_inv_qty
                # Define a 'meaningful amount' - e.g., at least 1 unit or a percentage of capacity
                # For simplicity, let's say if it's carrying something else, it needs full capacity for the new task type
                # or at least capacity for 1 unit of the new type.
                # This logic can be refined. For now, if carrying something else, and not enough space for at least 1 new unit, skip.
                if remaining_capacity < 1 : # Needs to be able to carry at least 1 of the new type
                    print(f"DEBUG: Agent {self.id}: Task {task.task_id} - Inventory has {current_inv_qty} of {current_inv_type}, not enough space for {task_resource_type.name}. Skipping.")
                    continue
            
            if current_inv_qty == self.inventory_capacity and current_inv_type != task_resource_type:
                print(f"DEBUG: Agent {self.id}: Task {task.task_id} - Inventory full with {current_inv_type}, cannot take task for {task_resource_type.name}. Skipping.")
                continue
            
            print(f"DEBUG: Agent {self.id}: Task {task.task_id} ({task_resource_type.name}) PASSED all preliminary checks.")
            candidate_tasks.append(task)

        if not candidate_tasks:
            print(f"DEBUG: Agent {self.id} found NO suitable tasks after full evaluation of {len(available_tasks)} initial tasks.")
            return None

        # If multiple candidates, sort by task.priority (higher is better)
        # Then could add proximity or other heuristics. For now, highest priority.
        candidate_tasks.sort(key=lambda t: t.priority, reverse=True)
        selected_task = candidate_tasks[0]
        print(f"DEBUG: Agent {self.id} selected task {selected_task.task_id} ({selected_task.task_type.name}) P:{selected_task.priority} from {len(candidate_tasks)} candidates.")
        return selected_task


    def update(self, dt: float, resource_manager: 'ResourceManager'):
        """Updates the agent's state and behavior based on its current task or idleness."""
        from ..tasks.task_types import TaskStatus
        current_time = pygame.time.get_ticks() / 1000.0 # Get time in seconds

        if self.current_task:
            new_task_status = self.current_task.execute_step(self, dt, resource_manager)
            
            if new_task_status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                # Task's cleanup should handle releasing resources/reservations
                self.current_task.cleanup(self, resource_manager, success=(new_task_status == TaskStatus.COMPLETED))
                # TaskManager handles archiving/re-posting
                self.task_manager_ref.report_task_outcome(self.current_task, new_task_status, self)
                
                self.current_task = None
                self.state = AgentState.IDLE # Become idle to look for new tasks
                self.target_position = None

                if new_task_status == TaskStatus.COMPLETED and self.current_inventory['quantity'] == 0:
                    self.current_inventory['resource_type'] = None
        
        # Agent is not busy with a task
        else:
            if self.state == AgentState.IDLE:
                # Transition to evaluating tasks
                print(f"DEBUG: Agent {self.id}: State IDLE, transitioning to EVALUATING_TASKS.")
                self.state = AgentState.EVALUATING_TASKS
                self._last_task_evaluation_time = current_time # Reset cooldown timer
            
            elif self.state == AgentState.EVALUATING_TASKS:
                if current_time - self._last_task_evaluation_time >= self.task_evaluation_cooldown:
                    print(f"DEBUG: Agent {self.id}: State EVALUATING_TASKS. Cooldown passed. Fetching tasks.")
                    self._last_task_evaluation_time = current_time
                    available_tasks = self.task_manager_ref.get_available_tasks()
                    print(f"DEBUG: Agent {self.id}: Found {len(available_tasks)} tasks on job board.")
                    
                    if available_tasks:
                        chosen_task_obj = self._evaluate_and_select_task(available_tasks, resource_manager)
                        
                        if chosen_task_obj:
                            print(f"DEBUG: Agent {self.id}: Evaluated and chose task {chosen_task_obj.task_id}. Attempting to claim.")
                            claimed_task = self.task_manager_ref.attempt_claim_task(chosen_task_obj.task_id, self)
                            if claimed_task:
                                print(f"DEBUG: Agent {self.id}: Successfully CLAIMED task {claimed_task.task_id}. Preparing task.")
                                self.current_task = claimed_task
                                # Agent's state will be set by task.prepare()
                                if not self.current_task.prepare(self, resource_manager):
                                    # Preparation failed, task will be reported as FAILED by prepare's cleanup
                                    # Agent becomes IDLE again to re-evaluate
                                    print(f"DEBUG: Agent {self.id}: Task {self.current_task.task_id} PREPARATION FAILED. Reporting outcome and returning to IDLE.")
                                    # TaskManager's report_task_outcome will handle re-posting if applicable
                                    self.task_manager_ref.report_task_outcome(self.current_task, TaskStatus.FAILED, self)
                                    # Ensure task cleanup is called if prepare fails and doesn't reach agent's main loop for cleanup
                                    if hasattr(self.current_task, 'cleanup') and callable(getattr(self.current_task, 'cleanup')):
                                         self.current_task.cleanup(self, resource_manager, success=False)
                                    self.current_task = None
                                    self.state = AgentState.IDLE
                                else:
                                    print(f"DEBUG: Agent {self.id}: Task {claimed_task.task_id} PREPARATION SUCCESSFUL. Agent state: {self.state}")

                            else:
                                # Failed to claim (e.g., another agent took it)
                                print(f"DEBUG: Agent {self.id}: Failed to claim task {chosen_task_obj.task_id}. Re-evaluating (will become IDLE).")
                                self.state = AgentState.IDLE # Re-evaluate on next suitable tick
                        else:
                            # No suitable task found by evaluation logic
                            print(f"DEBUG: Agent {self.id}: No suitable tasks found after evaluation. Moving randomly.")
                            self.state = AgentState.MOVING_RANDOMLY
                    else:
                        # No tasks on the job board
                        print(f"DEBUG: Agent {self.id}: No tasks available on job board. Moving randomly.")
                        self.state = AgentState.MOVING_RANDOMLY
                # else:
                    # print(f"DEBUG: Agent {self.id}: State EVALUATING_TASKS. Cooldown NOT passed. Waiting. Current: {current_time:.2f}, LastEval: {self._last_task_evaluation_time:.2f}, Cooldown: {self.task_evaluation_cooldown:.2f}")

            
            elif self.state == AgentState.MOVING_RANDOMLY:
                self._move_randomly(dt)
                # If _move_randomly sets state to IDLE, it will then transition to EVALUATING_TASKS
            
            # Ensure agent doesn't get stuck in a non-IDLE, non-MOVING_RANDOMLY state without a task
            elif self.state not in [AgentState.IDLE, AgentState.EVALUATING_TASKS, AgentState.MOVING_RANDOMLY]:
                 self.state = AgentState.IDLE
                 self.target_position = None


    def draw(self, screen: pygame.Surface, grid):
        """Draws the agent on the screen."""
        screen_pos = self.grid.grid_to_screen(self.position) # type: ignore
        agent_radius = self.grid.cell_width // 2 # type: ignore

        current_agent_color = self.state_colors.get(self.state, self.color)
        pygame.draw.circle(screen, current_agent_color, screen_pos, agent_radius)

        if self.current_inventory['quantity'] > 0 and self.current_inventory['resource_type'] is not None:
            carried_resource_type = self.current_inventory['resource_type']
            resource_color = self.config.RESOURCE_VISUAL_COLORS.get(carried_resource_type, (128, 128, 128)) 

            icon_radius = agent_radius // 2
            icon_offset_y = -agent_radius - icon_radius // 2 
            icon_center_x = screen_pos[0]
            icon_center_y = screen_pos[1] + icon_offset_y
            
            pygame.draw.circle(screen, resource_color, (icon_center_x, icon_center_y), icon_radius)