import pygame
import uuid # For agent ID
from enum import Enum, auto
import random
import logging # Added
from typing import List, Dict, Optional, TYPE_CHECKING, Any # Added Any
import math # For math.inf

from ..resources.resource_types import ResourceType
from ..core import config # Agent still uses config for timers, capacity if not overridden by task
from ..tasks.task import GatherAndDeliverTask, DeliverWheatToMillTask # Added DeliverWheatToMillTask
from ..tasks.task_types import TaskStatus, TaskType # Added TaskType
from ..pathfinding.astar import find_path # A* pathfinding
from .agent_defs import AgentState # Import AgentState from the new file

# Forward references for type hinting
if TYPE_CHECKING:
    from ..tasks.task import Task
    from ..tasks.task_manager import TaskManager
    from ..resources.manager import ResourceManager # For passing to tasks
    # from ..core.grid import Grid # Assuming Grid class type hint

# AgentState enum has been moved to agent_defs.py

class Agent:
    """Represents an autonomous agent in the simulation, executing tasks."""

    def __init__(self,
                 agent_id: uuid.UUID, 
                 position: pygame.math.Vector2,
                 speed: float,
                 grid, # 'Grid' type hint
                 task_manager: 'TaskManager',
                 # occupancy_grid: List[List[Optional[Any]]], # Removed occupancy_grid
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
            # occupancy_grid (List[List[Optional[Any]]]): The game's occupancy grid. # Removed
            inventory_capacity (int): Maximum number of resource units the agent can carry.
            resource_priorities (Optional[List[ResourceType]]): Ordered list of resource types the agent prefers.
                                                               Might be used by TaskManager.
        """
        self.id: uuid.UUID = agent_id
        self.position = position
        self.speed = speed
        self.grid = grid # type: ignore
        self.task_manager_ref: 'TaskManager' = task_manager
        # self.occupancy_grid = occupancy_grid # Removed
        self.config = config

        self.state = AgentState.IDLE
        self.target_position: Optional[pygame.math.Vector2] = None # Current waypoint
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
            # AgentState.COLLECTING_FROM_STORAGE will reuse GATHERING_RESOURCE color
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
        self.current_path: Optional[List[pygame.math.Vector2]] = None # For A* path
        self.final_destination: Optional[pygame.math.Vector2] = None # For the ultimate goal of a movement sequence

        self.gathering_timer: float = 0.0
        self.delivery_timer: float = 0.0
        self.logger = logging.getLogger(__name__) # Added

    def set_target(self, final_destination: pygame.math.Vector2):
        """
        Sets the agent's final destination and calculates the path.
        The agent's 'target_position' will be the next waypoint in the path.
        """
        self.final_destination = final_destination
        # Ensure positions are integers for pathfinding if they represent grid cells
        current_grid_pos = pygame.math.Vector2(int(round(self.position.x)), int(round(self.position.y)))
        final_grid_dest = pygame.math.Vector2(int(round(final_destination.x)), int(round(final_destination.y)))

        if current_grid_pos == final_grid_dest:
            self.current_path = [final_grid_dest] # Path is just the destination
            self.target_position = final_grid_dest # Already there or very close
            self.logger.debug(f"Agent {self.id} set_target: Already at/near final destination {final_grid_dest}.") # Changed
            return

        self.current_path = find_path(current_grid_pos, final_grid_dest, self.grid) # type: ignore

        if self.current_path and len(self.current_path) > 0:
            # Remove current position if it's the start of the path
            if self.current_path[0] == current_grid_pos and len(self.current_path) > 1:
                self.current_path.pop(0)
            
            if not self.current_path: # Path might have become empty after pop
                self.target_position = final_grid_dest # Essentially means we are at the destination
                self.logger.debug(f"Agent {self.id} set_target: Path to {final_grid_dest} resulted in empty path after pop (likely at destination).") # Changed
                self.current_path = [final_grid_dest] # Ensure path isn't None
                return

            self.target_position = self.current_path[0]
            # print(f"DEBUG: Agent {self.id} set_target: New path to {final_grid_dest}. Next waypoint: {self.target_position}. Path: {self.current_path}")
        else:
            self.target_position = None
            self.current_path = None # Ensure it's None if no path
            self.logger.warning(f"Agent {self.id} could not find a path from {current_grid_pos} to {final_grid_dest}.") # Changed
            # Consider setting agent to IDLE or a "PATH_FAILED" state if path is None
            # For now, task execution will likely fail if agent can't reach target.
            # self.set_objective_idle() # Or a specific failure state

    def set_objective_idle(self):
        """Sets the agent's state to IDLE and clears its target and path."""
        self.state = AgentState.IDLE
        self.target_position = None
        self.current_path = None
        self.final_destination = None

    def set_objective_evaluating_tasks(self):
        """Sets the agent's state to EVALUATING_TASKS."""
        self.state = AgentState.EVALUATING_TASKS
        self.target_position = None
        self.current_path = None
        self.final_destination = None

    def set_objective_move_randomly(self):
        """Sets the agent's state to MOVING_RANDOMLY and calculates a random path."""
        self.state = AgentState.MOVING_RANDOMLY
        # _move_randomly will pick a specific target and call self.set_target()
        self.target_position = None
        self.current_path = None
        self.final_destination = None


    def set_objective_move_to_resource(self, target_node_position: pygame.math.Vector2):
        """Sets the agent's state to MOVING_TO_RESOURCE and calculates path."""
        self.state = AgentState.MOVING_TO_RESOURCE
        self.set_target(target_node_position)

    def set_objective_gather_resource(self, gathering_time: float):
        """Sets the agent's state to GATHERING_RESOURCE and starts the timer."""
        self.state = AgentState.GATHERING_RESOURCE
        self.gathering_timer = gathering_time
        self.target_position = None
        self.current_path = None
        self.final_destination = None


    def set_objective_move_to_storage(self, storage_position: pygame.math.Vector2):
        """Sets the agent's state to MOVING_TO_STORAGE and calculates path."""
        self.state = AgentState.MOVING_TO_STORAGE
        self.set_target(storage_position)

    def set_objective_deliver_resource(self, delivery_time: float):
        """Sets the agent's state to DELIVERING_RESOURCE and starts the timer."""
        self.state = AgentState.DELIVERING_RESOURCE
        self.delivery_timer = delivery_time
        self.target_position = None
        self.current_path = None
        self.final_destination = None


    def set_objective_move_to_processor(self, processor_position: pygame.math.Vector2):
        """Sets the agent's state to MOVING_TO_PROCESSOR and calculates path."""
        self.state = AgentState.MOVING_TO_PROCESSOR
        self.set_target(processor_position)

    def set_objective_deliver_to_processor(self, delivery_time: float):
        """Sets the agent's state to DELIVERING_TO_PROCESSOR and starts the timer."""
        self.state = AgentState.DELIVERING_TO_PROCESSOR
        self.delivery_timer = delivery_time # Assuming delivery_timer can be reused
        self.target_position = None
        self.current_path = None
        self.final_destination = None


    def set_objective_collect_from_processor(self, collection_time: float):
        """Sets the agent's state to COLLECTING_FROM_PROCESSOR and starts a timer."""
        self.state = AgentState.COLLECTING_FROM_PROCESSOR
        self.gathering_timer = collection_time # Assuming gathering_timer can be reused
        self.target_position = None
        self.current_path = None
        self.final_destination = None


    def set_objective_collect_from_storage(self, collection_time: float):
        """Sets the agent's state to GATHERING_RESOURCE (reused for collecting from storage) and starts the timer."""
        self.state = AgentState.GATHERING_RESOURCE # Reusing GATHERING_RESOURCE state
        self.gathering_timer = collection_time
        self.target_position = None
        self.current_path = None
        self.final_destination = None


    def _follow_path(self, dt: float) -> bool:
        """
        Moves the agent along the self.current_path.
        Args: dt (float): Delta time.
        Returns: bool: True if the current waypoint in the path was reached, False otherwise.
                       If the final destination is reached, self.current_path will be empty or None.
        """
        if not self.current_path or not self.target_position: # target_position is the current waypoint
            # No path to follow, or no current waypoint set from the path
            # This might happen if path calculation failed or path is complete.
            # Task logic should handle what to do if agent can't move.
            return False

        # self.target_position is the current waypoint from self.current_path[0]
        direction = self.target_position - self.position
        distance_to_waypoint = direction.length()

        if distance_to_waypoint < self.target_tolerance:
            # Reached the current waypoint
            self.position = pygame.math.Vector2(self.target_position) # Snap to waypoint
            
            if self.current_path: # Should always be true if target_position was set from it
                self.current_path.pop(0) # Remove the reached waypoint

            if not self.current_path: # Path is now empty, meaning final destination of this path segment reached
                self.target_position = None
                self.final_destination = None # Clear final destination as it's reached for this segment
                # print(f"DEBUG: Agent {self.id} reached end of path.")
                return True # Signifies that the movement objective for this path is complete
            else:
                # Set next waypoint as the target
                self.target_position = self.current_path[0]
                # print(f"DEBUG: Agent {self.id} reached waypoint. Next waypoint: {self.target_position}. Path left: {self.current_path}")
                # Return False because the *overall* path (final_destination) might not be complete yet,
                # but True could be used by task to know a step in path is done.
                # Let's return True to indicate waypoint reached, task can check self.current_path.
                return True # Waypoint reached, but path may continue

        elif distance_to_waypoint > 0:
            normalized_direction = direction.normalize()
            potential_movement = normalized_direction * self.speed * dt
            
            if potential_movement.length() >= distance_to_waypoint:
                # Will reach or overshoot waypoint this frame
                self.position = pygame.math.Vector2(self.target_position) # Snap to waypoint
                
                if self.current_path: self.current_path.pop(0)

                if not self.current_path:
                    self.target_position = None
                    self.final_destination = None
                    # print(f"DEBUG: Agent {self.id} reached end of path by moving.")
                    return True # Final destination of path segment reached
                else:
                    self.target_position = self.current_path[0]
                    # print(f"DEBUG: Agent {self.id} reached waypoint by moving. Next waypoint: {self.target_position}")
                    return True # Waypoint reached
            else:
                self.position += potential_movement
        
        return False # Waypoint not yet reached

    def _move_randomly(self, dt: float):
        """Moves the agent randomly. If a path is set, it follows it. Otherwise, picks a new random target."""
        if not self.current_path and self.state == AgentState.MOVING_RANDOMLY: # Only pick new random if no path and in this state
            if self.grid.width_in_cells > 0 and self.grid.height_in_cells > 0: # type: ignore
                random_target_pos = pygame.math.Vector2(
                    random.uniform(0, self.grid.width_in_cells - 1), # type: ignore
                    random.uniform(0, self.grid.height_in_cells - 1) # type: ignore
                )
                # Ensure it's int for grid purposes
                random_target_pos.x = int(round(max(0, min(random_target_pos.x, self.grid.width_in_cells - 1)))) # type: ignore
                random_target_pos.y = int(round(max(0, min(random_target_pos.y, self.grid.height_in_cells - 1)))) # type: ignore
                
                self.logger.debug(f"Agent {self.id} moving randomly, new target: {random_target_pos}") # Changed
                self.set_target(random_target_pos) # This will calculate path
                if not self.current_path: # Path calculation failed
                    self.logger.warning(f"Agent {self.id} failed to find path for random move to {random_target_pos}. Becoming IDLE.") # Added
                    self.set_objective_idle() # Become idle if can't path to random spot
                    return
            else: # Grid not valid
                self.set_objective_idle()
                return

        # Now, follow the path if one exists (either newly calculated or pre-existing for random move)
        if self.current_path:
            if self._follow_path(dt): # True if waypoint reached
                if not self.current_path: # Path is now complete
                    # print(f"DEBUG: Agent {self.id} completed random move path.")
                    self.set_objective_idle() # Finished random move, become idle
        elif self.state == AgentState.MOVING_RANDOMLY : # No path, but was supposed to be moving randomly
             # This case might occur if path calculation failed initially and set_target didn't set a path
             # print(f"DEBUG: Agent {self.id} in MOVING_RANDOMLY but no path. Becoming IDLE.")
             self.set_objective_idle()


    def _evaluate_and_select_task(self, available_tasks: List['Task'], resource_manager: 'ResourceManager') -> Optional['Task']:
        """
        Evaluates available tasks and selects one based on agent's logic,
        checking for resource availability, dropoff space, and inventory compatibility.
        """
        from ..resources.mill import Mill # For checking Mill instances

        candidate_tasks: List[Task] = []

        for task in available_tasks:
            # --- GatherAndDeliverTask Evaluation ---
            if isinstance(task, GatherAndDeliverTask):
                task_resource_type = task.resource_type_to_gather
                self.logger.debug(f"Agent {self.id} evaluating GatherAndDeliverTask {task.task_id} for resource {task_resource_type.name}.") # Changed

                # 1. Check Agent's Resource Priorities
                if self.resource_priorities and task_resource_type not in self.resource_priorities:
                    self.logger.debug(f"Agent {self.id}: Task {task.task_id} resource {task_resource_type.name} not in priorities. Skipping.") # Changed
                    continue
                
                # 2. Check Source Availability (ResourceNode)
                if not resource_manager.has_available_sources(task_resource_type, min_quantity=1):
                    self.logger.debug(f"Agent {self.id}: Task {task.task_id} - No available sources for {task_resource_type.name}. Skipping.") # Changed
                    continue
                
                # 3. Check Dropoff Availability (StoragePoint)
                if not resource_manager.has_available_dropoffs(task_resource_type, min_capacity=1): # min_capacity for reservation
                    self.logger.debug(f"Agent {self.id}: Task {task.task_id} - No available dropoffs for {task_resource_type.name}. Skipping.") # Changed
                    continue

                # 4. Check Agent Inventory Compatibility & Capacity
                current_inv_qty = self.current_inventory.get('quantity', 0)
                current_inv_type = self.current_inventory.get('resource_type')

                if current_inv_qty > 0 and current_inv_type != task_resource_type:
                    if (self.inventory_capacity - current_inv_qty) < 1 : # Needs to be able to carry at least 1 of the new type
                        self.logger.debug(f"Agent {self.id}: Task {task.task_id} - Inventory has {current_inv_qty} of {current_inv_type}, not enough space for {task_resource_type.name}. Skipping.") # Changed
                        continue
                
                if current_inv_qty == self.inventory_capacity and (current_inv_type != task_resource_type or task.quantity_to_gather > 0) :
                    self.logger.debug(f"Agent {self.id}: Task {task.task_id} - Inventory full with {current_inv_type}, cannot take task for {task_resource_type.name}. Skipping.") # Changed
                    continue
                
                self.logger.debug(f"Agent {self.id}: Task {task.task_id} ({task_resource_type.name}) PASSED GatherAndDeliver checks.") # Changed
                candidate_tasks.append(task)

            # --- DeliverWheatToMillTask (TaskType.PROCESS_RESOURCE) Evaluation ---
            elif isinstance(task, DeliverWheatToMillTask): # Check for the specific class
                self.logger.debug(f"Agent {self.id} evaluating DeliverWheatToMillTask {task.task_id} for resource {task.resource_to_retrieve.name}.") # Changed

                # 1. Agent inventory must be empty for this specific task type as per plan
                if self.current_inventory.get('quantity', 0) > 0:
                    self.logger.debug(f"Agent {self.id}: Task {task.task_id} (DeliverWheatToMill) - Agent inventory not empty. Skipping.") # Changed
                    continue

                # 2. Check if Wheat is available in any StoragePoint
                # This is a simplified check; task.prepare() will do the actual reservation.
                wheat_available_in_storage = False
                for sp in resource_manager.storage_points:
                    if sp.has_resource(ResourceType.WHEAT, 1): # Check for at least 1 unit
                        wheat_available_in_storage = True
                        break
                if not wheat_available_in_storage:
                    self.logger.debug(f"Agent {self.id}: Task {task.task_id} - No WHEAT found in any storage point. Skipping.") # Changed
                    continue

                # 3. Check if a Mill is available and can accept Wheat
                # This is a simplified check; task.prepare() will find a specific mill.
                mill_available_and_accepts = False
                for station in resource_manager.processing_stations:
                    if isinstance(station, Mill) and station.can_accept_input(ResourceType.WHEAT, 1):
                        mill_available_and_accepts = True
                        break
                if not mill_available_and_accepts:
                    self.logger.debug(f"Agent {self.id}: Task {task.task_id} - No Mill available or accepting WHEAT. Skipping.") # Changed
                    continue
                
                self.logger.debug(f"Agent {self.id}: Task {task.task_id} ({task.resource_to_retrieve.name}) PASSED DeliverWheatToMill checks.") # Changed
                candidate_tasks.append(task)
            
            else:
                # Optionally handle other task types or log them
                if task.task_type not in [TaskType.GATHER_AND_DELIVER, TaskType.PROCESS_RESOURCE]: # Check general task_type
                     self.logger.debug(f"Agent {self.id} skipping unhandled task type {task.task_type.name} for task {task.task_id}.") # Changed
                # If it's PROCESS_RESOURCE but not DeliverWheatToMillTask, it's currently unhandled by agent eval
                elif task.task_type == TaskType.PROCESS_RESOURCE and not isinstance(task, DeliverWheatToMillTask):
                     self.logger.debug(f"Agent {self.id} skipping PROCESS_RESOURCE task {task.task_id} as it's not DeliverWheatToMillTask.") # Changed


        if not candidate_tasks:
            self.logger.debug(f"Agent {self.id} found NO suitable tasks after full evaluation of {len(available_tasks)} initial tasks.") # Changed
            return None

        candidate_tasks.sort(key=lambda t: t.priority, reverse=True)
        selected_task = candidate_tasks[0]
        self.logger.debug(f"Agent {self.id} selected task {selected_task.task_id} ({selected_task.task_type.name}) P:{selected_task.priority} from {len(candidate_tasks)} candidates.") # Changed
        return selected_task


    def update(self, dt: float, resource_manager: 'ResourceManager'):
        """Updates the agent's state and behavior based on its current task or idleness."""
        # Removed local import: from ..tasks.task_types import TaskStatus
        current_time = pygame.time.get_ticks() / 1000.0 # Get time in seconds

        if self.current_task:
            new_task_status = self.current_task.execute_step(self, dt, resource_manager)
            
            if new_task_status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                # Task's cleanup should handle releasing resources/reservations
                self.current_task.cleanup(self, resource_manager, success=(new_task_status == TaskStatus.COMPLETED))
                # TaskManager handles archiving/re-posting
                self.task_manager_ref.report_task_outcome(self.current_task, new_task_status, self)
                
                self.current_task = None
                self.set_objective_idle() # Become idle to look for new tasks

                if new_task_status == TaskStatus.COMPLETED and self.current_inventory['quantity'] == 0:
                    self.current_inventory['resource_type'] = None
        
        # Agent is not busy with a task
        else:
            if self.state == AgentState.IDLE:
                # Transition to evaluating tasks
                self.logger.debug(f"Agent {self.id}: State IDLE, transitioning to EVALUATING_TASKS.") # Changed
                self.set_objective_evaluating_tasks()
                self._last_task_evaluation_time = current_time # Reset cooldown timer
            
            elif self.state == AgentState.EVALUATING_TASKS:
                # Agent is evaluating tasks, TaskManager handles this.
                # Agent's own timers are not relevant here.
                if current_time - self._last_task_evaluation_time >= self.task_evaluation_cooldown:
                    self.logger.debug(f"Agent {self.id}: State EVALUATING_TASKS. Cooldown passed. Fetching tasks.") # Changed
                    self._last_task_evaluation_time = current_time
                    available_tasks = self.task_manager_ref.get_available_tasks()
                    self.logger.debug(f"Agent {self.id}: Found {len(available_tasks)} tasks on job board.") # Changed
                    
                    if available_tasks:
                        chosen_task_obj = self._evaluate_and_select_task(available_tasks, resource_manager)
                        
                        if chosen_task_obj:
                            self.logger.debug(f"Agent {self.id}: Evaluated and chose task {chosen_task_obj.task_id}. Attempting to claim.") # Changed
                            claimed_task = self.task_manager_ref.attempt_claim_task(chosen_task_obj.task_id, self)
                            if claimed_task:
                                self.logger.info(f"Agent {self.id}: Successfully CLAIMED task {claimed_task.task_id}. Preparing task.") # Changed to INFO
                                self.current_task = claimed_task
                                # Agent's state will be set by task.prepare()
                                if not self.current_task.prepare(self, resource_manager):
                                    # Preparation failed, task will be reported as FAILED by prepare's cleanup
                                    # Agent becomes IDLE again to re-evaluate
                                    self.logger.warning(f"Agent {self.id}: Task {self.current_task.task_id} PREPARATION FAILED. Reporting outcome and returning to IDLE.") # Changed to WARNING
                                    # TaskManager's report_task_outcome will handle re-posting if applicable
                                    self.task_manager_ref.report_task_outcome(self.current_task, TaskStatus.FAILED, self)
                                    # Ensure task cleanup is called if prepare fails and doesn't reach agent's main loop for cleanup
                                    if hasattr(self.current_task, 'cleanup') and callable(getattr(self.current_task, 'cleanup')):
                                         self.current_task.cleanup(self, resource_manager, success=False)
                                    self.current_task = None
                                    self.set_objective_idle()
                                else:
                                    self.logger.info(f"Agent {self.id}: Task {claimed_task.task_id} PREPARATION SUCCESSFUL. Agent state: {self.state}") # Changed to INFO

                            else:
                                # Failed to claim (e.g., another agent took it)
                                self.logger.info(f"Agent {self.id}: Failed to claim task {chosen_task_obj.task_id} (likely claimed by another agent). Re-evaluating.") # Changed to INFO
                                self.set_objective_idle() # Re-evaluate on next suitable tick
                        else:
                            # No suitable task found by evaluation logic
                            self.logger.debug(f"Agent {self.id}: No suitable tasks found after evaluation. Moving randomly.") # Changed
                            self.set_objective_move_randomly()
                    else:
                        # No tasks on the job board
                        self.logger.debug(f"Agent {self.id}: No tasks available on job board. Moving randomly.") # Changed
                        self.set_objective_move_randomly()
                # else:
                    # self.logger.debug(f"Agent {self.id}: State EVALUATING_TASKS. Cooldown NOT passed. Waiting. Current: {current_time:.2f}, LastEval: {self._last_task_evaluation_time:.2f}, Cooldown: {self.task_evaluation_cooldown:.2f}") # Changed

            
            elif self.state == AgentState.MOVING_RANDOMLY:
                self._move_randomly(dt)
                # If _move_randomly sets state to IDLE, it will then transition to EVALUATING_TASKS
            
            # Ensure agent doesn't get stuck in a non-IDLE, non-MOVING_RANDOMLY state without a task
            elif self.state not in [AgentState.IDLE, AgentState.EVALUATING_TASKS, AgentState.MOVING_RANDOMLY]:
                  self.set_objective_idle()
        
        # Agent-specific state updates based on its current state (timers, etc.)
        if self.state == AgentState.GATHERING_RESOURCE:
            if self.gathering_timer > 0:
                self.gathering_timer -= dt
                if self.gathering_timer < 0:
                    self.gathering_timer = 0 # Ensure it doesn't go negative

        elif self.state == AgentState.DELIVERING_RESOURCE:
            if self.delivery_timer > 0:
                self.delivery_timer -= dt
                if self.delivery_timer < 0:
                    self.delivery_timer = 0 # Ensure it doesn't go negative
        
        # Similar timer logic can be added for COLLECTING_FROM_PROCESSOR or DELIVERING_TO_PROCESSOR if those use timers
        elif self.state == AgentState.COLLECTING_FROM_PROCESSOR: # Assuming it uses gathering_timer
            if self.gathering_timer > 0:
                self.gathering_timer -= dt
                if self.gathering_timer < 0:
                    self.gathering_timer = 0
        
        elif self.state == AgentState.DELIVERING_TO_PROCESSOR: # Assuming it uses delivery_timer
            if self.delivery_timer > 0:
                self.delivery_timer -= dt
                if self.delivery_timer < 0:
                    self.delivery_timer = 0


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