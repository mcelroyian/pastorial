import pygame
import uuid # For agent ID
from enum import Enum, auto
import random
import logging # Added
from typing import List, Dict, Optional, TYPE_CHECKING, Any
import math # For math.inf

from ..resources.resource_types import ResourceType
from ..core import config
from ..tasks.task import GatherAndDeliverTask, DeliverWheatToMillTask
from ..tasks.task_types import TaskStatus, TaskType
from ..pathfinding.astar import find_path
from .agent_defs import AgentState # Kept for now for fallback logic
from .intents import Intent, IntentStatus, MoveIntent, GatherIntent, DeliverIntent, InteractAtTargetIntent
from .agent_behaviors import AgentBehavior, IdleBehavior, MovingBehavior, InteractingBehavior, PathFailedBehavior, EvaluatingIntentBehavior


# Forward references for type hinting
if TYPE_CHECKING:
    from ..tasks.task import Task
    from ..tasks.task_manager import TaskManager
    from ..resources.manager import ResourceManager
    # from ..core.grid import Grid
    # from .intents import Intent # Already imported above
    # from .agent_behaviors import AgentBehavior # Already imported above


class Agent:
    """Represents an autonomous agent in the simulation, executing tasks and intents."""

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
        """
        self.id: uuid.UUID = agent_id
        self.position = position
        self.speed = speed
        self.grid = grid # type: ignore
        self.task_manager_ref: 'TaskManager' = task_manager
        self.config = config
        self.logger = logging.getLogger(__name__)

        # --- Old State System (kept for fallback during transition) ---
        self.state = AgentState.IDLE
        self._old_state_colors = { # Renamed to avoid conflict if new system uses state_colors
            AgentState.IDLE: (255, 255, 0),
            AgentState.MOVING_RANDOMLY: (255, 165, 0),
            AgentState.MOVING_TO_RESOURCE: (0, 200, 50),
            AgentState.GATHERING_RESOURCE: (50, 150, 255),
            AgentState.MOVING_TO_STORAGE: (0, 200, 200),
            AgentState.DELIVERING_RESOURCE: (100, 100, 255),
            AgentState.MOVING_TO_PROCESSOR: (255, 140, 0),
            AgentState.DELIVERING_TO_PROCESSOR: (138, 43, 226),
            AgentState.COLLECTING_FROM_PROCESSOR: (0, 128, 128),
            AgentState.EVALUATING_TASKS: (200, 200, 200),
        }
        # Timers for old system, will be removed later
        self.gathering_timer: float = 0.0
        self.delivery_timer: float = 0.0
        # --- End Old State System ---

        # --- New Behavior/Intent System ---
        self.current_intent: Optional[Intent] = None
        self.current_behavior: AgentBehavior = IdleBehavior(self)
        # self.current_behavior.enter() # Initialize the first behavior - Called after full init

        self.behavior_colors = {
            IdleBehavior: (255, 255, 0), # Yellow
            MovingBehavior: (0, 200, 50), # Green
            InteractingBehavior: (50, 150, 255), # Blue
            PathFailedBehavior: (255, 0, 0), # Red
            EvaluatingIntentBehavior: (200, 200, 200), # Grey
        }
        self.color = (255, 0, 255) # Default color if behavior not in map (Magenta)
        # --- End New Behavior/Intent System ---
        
        self.target_position: Optional[pygame.math.Vector2] = None # Current waypoint for pathfinding
        self.current_path: Optional[List[pygame.math.Vector2]] = None # For A* path
        self.final_destination: Optional[pygame.math.Vector2] = None # Ultimate goal of a movement sequence (used by set_target)
        
        self.target_tolerance = 0.1
        self.task_evaluation_cooldown = 1.0 # Seconds before trying to evaluate tasks again if none found (for old system)
        self._last_task_evaluation_time = 0.0

        self.inventory_capacity: int = inventory_capacity
        self.current_inventory: Dict[str, Optional[ResourceType] | int] = { # type: ignore
            'resource_type': None,
            'quantity': 0
        }
        
        self.current_task: Optional['Task'] = None # Task currently assigned (old system context)
        self.resource_priorities: Optional[List[ResourceType]] = resource_priorities
        
        # Initialize the first behavior after all attributes are set
        self.current_behavior.enter()


    # --- New Intent and Behavior Methods ---
    def submit_intent(self, intent: Intent):
        """
        Submits a new intent for the agent to process.
        The agent will transition to EvaluatingIntentBehavior to handle it.
        """
        if self.current_intent and self.current_intent.status == IntentStatus.ACTIVE:
            self.logger.warning(f"Agent {self.id} received new intent {intent.intent_id} while current intent {self.current_intent.intent_id} is active. Overwriting.")
            # Optionally, handle cancellation of the old intent here.
            self.current_intent.status = IntentStatus.CANCELLED # Mark as cancelled

        self.logger.info(f"Agent {self.id} received new intent: {intent}")
        self.current_intent = intent
        self.current_intent.status = IntentStatus.PENDING # Should be PENDING until processed
        self._transition_behavior(EvaluatingIntentBehavior, self.current_intent)

    def _process_current_intent(self):
        """
        Processes the self.current_intent and transitions the agent to an appropriate behavior.
        This is typically called by EvaluatingIntentBehavior or when an intent is completed.
        """
        if not self.current_intent or self.current_intent.status != IntentStatus.PENDING:
            # If no intent, or intent not pending, agent might go idle or seek new task/intent.
            if not isinstance(self.current_behavior, IdleBehavior):
                 self._transition_behavior(IdleBehavior)
            return

        self.logger.debug(f"Agent {self.id} processing intent: {self.current_intent}")
        self.current_intent.status = IntentStatus.ACTIVE # Mark as active as we are starting it

        intent_type = type(self.current_intent)

        if intent_type == MoveIntent:
            self._transition_behavior(MovingBehavior, self.current_intent)
        elif intent_type == GatherIntent or intent_type == DeliverIntent or intent_type == InteractAtTargetIntent:
            # These could map to InteractingBehavior, which would then use intent details
            # For now, assuming InteractAtTargetIntent is used for the timed part of gathering/delivering.
            # GatherIntent/DeliverIntent might need specific logic if they are not just timers.
            if isinstance(self.current_intent, (GatherIntent, DeliverIntent, InteractAtTargetIntent)):
                 self._transition_behavior(InteractingBehavior, self.current_intent)
            else: # Should not happen if intent_type matched
                 self.logger.error(f"Agent {self.id}: Unhandled intent type {intent_type} in _process_current_intent after type check.")
                 if self.current_intent: # Check if current_intent is not None before accessing status
                    self.current_intent.status = IntentStatus.FAILED
                    self.current_intent.error_message = f"Agent cannot handle intent type {intent_type}"
                 self._transition_behavior(IdleBehavior) # Fallback
        # Add more intent types here (e.g., specific gather, deliver behaviors if needed)
        else:
            self.logger.warning(f"Agent {self.id}: Unknown intent type {intent_type}. Intent: {self.current_intent}")
            if self.current_intent: # Check if current_intent is not None
                self.current_intent.status = IntentStatus.FAILED
                self.current_intent.error_message = f"Unknown intent type: {intent_type}"
            self._transition_behavior(IdleBehavior) # Fallback

    def _transition_behavior(self, new_behavior_class_or_instance, intent_for_behavior: Optional[Intent] = None):
        """Helper method to transition between behaviors."""
        if self.current_behavior:
            self.logger.debug(f"Agent {self.id} exiting behavior: {self.current_behavior}")
            self.current_behavior.exit()

        if isinstance(new_behavior_class_or_instance, AgentBehavior):
            self.current_behavior = new_behavior_class_or_instance
        else: # It's a class, so instantiate it
            self.current_behavior = new_behavior_class_or_instance(self)
        
        self.logger.info(f"Agent {self.id} transitioned to behavior: {self.current_behavior} for intent: {intent_for_behavior.intent_id if intent_for_behavior else 'None'}")
        self.current_behavior.enter(intent_for_behavior if intent_for_behavior else self.current_intent)

    def _seek_new_work_or_fallback(self, dt: float, resource_manager: 'ResourceManager'):
        """Placeholder for logic when agent is idle: find task or move randomly (old system)."""
        self.logger.debug(f"Agent {self.id} is in _seek_new_work_or_fallback. Current behavior: {self.current_behavior}")
        # This will eventually integrate with the task system to get new intents.
        # For now, it might fall back to old EVALUATING_TASKS or MOVING_RANDOMLY logic.
        
        # Fallback to old logic for now if no current_intent and in Idle/EvaluatingIntent behavior
        current_time = pygame.time.get_ticks() / 1000.0
        if self.state == AgentState.IDLE:
            self.logger.debug(f"Agent {self.id} (fallback): State IDLE, transitioning to EVALUATING_TASKS.")
            self.set_objective_evaluating_tasks() # Old system
            self._last_task_evaluation_time = current_time
        
        elif self.state == AgentState.EVALUATING_TASKS:
            if current_time - self._last_task_evaluation_time >= self.task_evaluation_cooldown:
                self.logger.debug(f"Agent {self.id} (fallback): State EVALUATING_TASKS. Cooldown passed. Fetching tasks.")
                self._last_task_evaluation_time = current_time
                available_tasks = self.task_manager_ref.get_available_tasks()
                if available_tasks:
                    chosen_task_obj = self._evaluate_and_select_task(available_tasks, resource_manager)
                    if chosen_task_obj:
                        claimed_task = self.task_manager_ref.attempt_claim_task(chosen_task_obj.task_id, self)
                        if claimed_task:
                            self.current_task = claimed_task
                            self.logger.info(f"Agent {self.id} (fallback): Claimed task {claimed_task.task_id}. Preparing (old system).")
                            # OLD WAY: task.prepare sets agent state.
                            # NEW WAY (TODO): task.prepare should submit an intent.
                            if not self.current_task.prepare(self, resource_manager):
                                self.logger.warning(f"Agent {self.id} (fallback): Task {self.current_task.task_id} PREPARATION FAILED (old system).")
                                self.task_manager_ref.report_task_outcome(self.current_task, TaskStatus.FAILED, self)
                                if hasattr(self.current_task, 'cleanup'): self.current_task.cleanup(self, resource_manager, success=False)
                                self.current_task = None
                                self.set_objective_idle() # Old system
                            else:
                                self.logger.info(f"Agent {self.id} (fallback): Task {claimed_task.task_id} PREPARATION SUCCESSFUL (old system). Agent state is now {self.state.name}")
                                # At this point, the old system's task.prepare() would have set self.state
                                # and the agent would proceed with that.
                        else: # Failed to claim
                            self.set_objective_idle() # Old system
                    else: # No suitable task
                        self.set_objective_move_randomly() # Old system
                else: # No tasks available
                    self.set_objective_move_randomly() # Old system
        elif self.state == AgentState.MOVING_RANDOMLY:
             self._move_randomly(dt) # Old system

    # --- End New Intent and Behavior Methods ---

    def set_target(self, final_destination: pygame.math.Vector2):
        """
        Sets the agent's final destination and calculates the path.
        The agent's 'target_position' will be the next waypoint in the path.
        """
        self.logger.debug(f"Agent {self.id} set_target: Called with final_destination: {final_destination}, current_pos: {self.position}")
        self.final_destination = final_destination
        # Ensure positions are integers for pathfinding if they represent grid cells
        current_grid_pos = pygame.math.Vector2(int(round(self.position.x)), int(round(self.position.y)))
        final_grid_dest = pygame.math.Vector2(int(round(final_destination.x)), int(round(final_destination.y)))

        if current_grid_pos == final_grid_dest:
            self.current_path = [final_grid_dest] # Path is just the destination
            self.target_position = final_grid_dest # Already there or very close
            self.logger.debug(f"Agent {self.id} set_target: Already at/near final destination {final_grid_dest}.") # Existing
            return

        self.current_path = find_path(current_grid_pos, final_grid_dest, self.grid) # type: ignore
        self.logger.debug(f"Agent {self.id} set_target: Pathfinding requested from {current_grid_pos} to {final_grid_dest}. Result path: {'Found, length ' + str(len(self.current_path)) if self.current_path else 'None'})")

        if self.current_path and len(self.current_path) > 0:
            # Remove current position if it's the start of the path
            if self.current_path[0] == current_grid_pos and len(self.current_path) > 1:
                self.current_path.pop(0)
                self.logger.debug(f"Agent {self.id} set_target: Popped current position from path. New path: {self.current_path}")
            
            if not self.current_path: # Path might have become empty after pop
                self.target_position = final_grid_dest # Essentially means we are at the destination
                self.logger.debug(f"Agent {self.id} set_target: Path to {final_grid_dest} resulted in empty path after pop (likely at destination).") # Existing
                self.current_path = [final_grid_dest] # Ensure path isn't None
                return

            self.target_position = self.current_path[0]
            self.logger.debug(f"Agent {self.id} set_target: Path set. Next waypoint: {self.target_position}. Full path: {self.current_path}")
            # print(f"DEBUG: Agent {self.id} set_target: New path to {final_grid_dest}. Next waypoint: {self.target_position}. Path: {self.current_path}")
        else: # Pathfinding failed or returned empty path initially
            self.target_position = None
            self.current_path = None # Ensure it's None if no path
            self.logger.warning(f"Agent {self.id} set_target: Pathfinding FAILED or returned empty. Could not find a path from {current_grid_pos} to {final_grid_dest}.") # Modified existing warning
            # Consider setting agent to IDLE or a "PATH_FAILED" state if path is None
            # For now, task execution will likely fail if agent can't reach target.
            # self.set_objective_idle() # Or a specific failure state

    def set_objective_idle(self):
        """Sets the agent's state to IDLE and clears its target and path."""
        old_state = self.state
        self.state = AgentState.IDLE
        self.target_position = None
        self.current_path = None
        self.final_destination = None
        self.logger.debug(f"Agent {self.id} state transition: {old_state.name} -> {self.state.name}")

    def set_objective_evaluating_tasks(self):
        """Sets the agent's state to EVALUATING_TASKS."""
        old_state = self.state
        self.state = AgentState.EVALUATING_TASKS
        self.target_position = None
        self.current_path = None
        self.final_destination = None
        self.logger.debug(f"Agent {self.id} state transition: {old_state.name} -> {self.state.name}")

    def set_objective_move_randomly(self):
        """Sets the agent's state to MOVING_RANDOMLY and calculates a random path."""
        old_state = self.state
        self.state = AgentState.MOVING_RANDOMLY
        # _move_randomly will pick a specific target and call self.set_target()
        self.target_position = None
        self.current_path = None
        self.final_destination = None
        self.logger.debug(f"Agent {self.id} state transition: {old_state.name} -> {self.state.name}")


    def set_objective_move_to_resource(self, target_node_position: pygame.math.Vector2):
        """Sets the agent's state to MOVING_TO_RESOURCE and calculates path."""
        old_state = self.state
        self.state = AgentState.MOVING_TO_RESOURCE
        self.logger.debug(f"Agent {self.id} state transition: {old_state.name} -> {self.state.name}. Target: {target_node_position}")
        self.set_target(target_node_position)

    def set_objective_gather_resource(self, gathering_time: float):
        """Sets the agent's state to GATHERING_RESOURCE and starts the timer."""
        old_state = self.state
        self.state = AgentState.GATHERING_RESOURCE
        self.gathering_timer = gathering_time
        self.target_position = None
        self.current_path = None
        self.final_destination = None
        self.logger.debug(f"Agent {self.id} state transition: {old_state.name} -> {self.state.name}. Gathering time: {gathering_time}")


    def set_objective_move_to_storage(self, storage_position: pygame.math.Vector2):
        """Sets the agent's state to MOVING_TO_STORAGE and calculates path."""
        old_state = self.state
        self.state = AgentState.MOVING_TO_STORAGE
        self.logger.debug(f"Agent {self.id} state transition: {old_state.name} -> {self.state.name}. Target: {storage_position}")
        self.set_target(storage_position)

    def set_objective_deliver_resource(self, delivery_time: float):
        """Sets the agent's state to DELIVERING_RESOURCE and starts the timer."""
        old_state = self.state
        self.state = AgentState.DELIVERING_RESOURCE
        self.delivery_timer = delivery_time
        self.target_position = None
        self.current_path = None
        self.final_destination = None
        self.logger.debug(f"Agent {self.id} state transition: {old_state.name} -> {self.state.name}. Delivery time: {delivery_time}")


    def set_objective_move_to_processor(self, processor_position: pygame.math.Vector2):
        """Sets the agent's state to MOVING_TO_PROCESSOR and calculates path."""
        old_state = self.state
        self.state = AgentState.MOVING_TO_PROCESSOR
        self.logger.debug(f"Agent {self.id} state transition: {old_state.name} -> {self.state.name}. Target: {processor_position}")
        self.set_target(processor_position)

    def set_objective_deliver_to_processor(self, delivery_time: float):
        """Sets the agent's state to DELIVERING_TO_PROCESSOR and starts the timer."""
        old_state = self.state
        self.state = AgentState.DELIVERING_TO_PROCESSOR
        self.delivery_timer = delivery_time # Assuming delivery_timer can be reused
        self.target_position = None
        self.current_path = None
        self.final_destination = None
        self.logger.debug(f"Agent {self.id} state transition: {old_state.name} -> {self.state.name}. Delivery time: {delivery_time}")


    def set_objective_collect_from_processor(self, collection_time: float):
        """Sets the agent's state to COLLECTING_FROM_PROCESSOR and starts a timer."""
        old_state = self.state
        self.state = AgentState.COLLECTING_FROM_PROCESSOR
        self.gathering_timer = collection_time # Assuming gathering_timer can be reused
        self.target_position = None
        self.current_path = None
        self.final_destination = None
        self.logger.debug(f"Agent {self.id} state transition: {old_state.name} -> {self.state.name}. Collection time: {collection_time}")


    def set_objective_collect_from_storage(self, collection_time: float):
        """Sets the agent's state to GATHERING_RESOURCE (reused for collecting from storage) and starts the timer."""
        old_state = self.state
        self.state = AgentState.GATHERING_RESOURCE # Reusing GATHERING_RESOURCE state
        self.gathering_timer = collection_time
        self.target_position = None
        self.current_path = None
        self.final_destination = None
        self.logger.debug(f"Agent {self.id} state transition: {old_state.name} -> {self.state.name} (as GATHERING_RESOURCE for collecting from storage). Collection time: {collection_time}")


    def _follow_path(self, dt: float) -> bool:
        """
        Moves the agent along the self.current_path.
        Args: dt (float): Delta time.
        Returns: bool: True if the current waypoint in the path was reached, False otherwise.
                       If the final destination is reached, self.current_path will be empty or None.
        """
        if not self.current_path or not self.target_position: # target_position is the current waypoint
            self.logger.debug(f"Agent {self.id} _follow_path: No current_path or target_position. Path: {self.current_path}, Target: {self.target_position}. Returning False.")
            # No path to follow, or no current waypoint set from the path
            # This might happen if path calculation failed or path is complete.
            # Task logic should handle what to do if agent can't move.
            return False

        # self.target_position is the current waypoint from self.current_path[0]
        direction = self.target_position - self.position
        distance_to_waypoint = direction.length()
        self.logger.debug(f"Agent {self.id} _follow_path: Current pos: {self.position}, Waypoint: {self.target_position}, Dist: {distance_to_waypoint:.2f}, Path: {self.current_path}")

        if distance_to_waypoint < self.target_tolerance:
            # Reached the current waypoint
            self.logger.debug(f"Agent {self.id} _follow_path: Reached waypoint {self.target_position} (within tolerance). Snapping position.")
            self.position = pygame.math.Vector2(self.target_position) # Snap to waypoint
            
            if self.current_path: # Should always be true if target_position was set from it
                self.current_path.pop(0) # Remove the reached waypoint
                self.logger.debug(f"Agent {self.id} _follow_path: Popped waypoint. Remaining path: {self.current_path}")

            if not self.current_path: # Path is now empty, meaning final destination of this path segment reached
                self.target_position = None
                self.final_destination = None # Clear final destination as it's reached for this segment
                self.logger.debug(f"Agent {self.id} _follow_path: Reached end of path (path empty after pop).")
                # print(f"DEBUG: Agent {self.id} reached end of path.")
                return True # Signifies that the movement objective for this path is complete
            else:
                # Set next waypoint as the target
                self.target_position = self.current_path[0]
                self.logger.debug(f"Agent {self.id} _follow_path: New waypoint set: {self.target_position}. Path left: {self.current_path}")
                # print(f"DEBUG: Agent {self.id} reached waypoint. Next waypoint: {self.target_position}. Path left: {self.current_path}")
                # Return False because the *overall* path (final_destination) might not be complete yet,
                # but True could be used by task to know a step in path is done.
                # Let's return True to indicate waypoint reached, task can check self.current_path.
                return True # Waypoint reached, but path may continue

        elif distance_to_waypoint > 0:
            normalized_direction = direction.normalize()
            potential_movement = normalized_direction * self.speed * dt
            self.logger.debug(f"Agent {self.id} _follow_path: Moving towards {self.target_position}. Movement: {potential_movement} (Speed: {self.speed}, dt: {dt})")
            
            if potential_movement.length() >= distance_to_waypoint:
                # Will reach or overshoot waypoint this frame
                self.logger.debug(f"Agent {self.id} _follow_path: Will reach/overshoot waypoint {self.target_position} this frame. Snapping.")
                self.position = pygame.math.Vector2(self.target_position) # Snap to waypoint
                
                if self.current_path: self.current_path.pop(0)
                self.logger.debug(f"Agent {self.id} _follow_path: Popped waypoint after moving. Remaining path: {self.current_path}")

                if not self.current_path:
                    self.target_position = None
                    self.final_destination = None
                    self.logger.debug(f"Agent {self.id} _follow_path: Reached end of path by moving (path empty after pop).")
                    # print(f"DEBUG: Agent {self.id} reached end of path by moving.")
                    return True # Final destination of path segment reached
                else:
                    self.target_position = self.current_path[0]
                    self.logger.debug(f"Agent {self.id} _follow_path: New waypoint set after moving: {self.target_position}")
                    # print(f"DEBUG: Agent {self.id} reached waypoint by moving. Next waypoint: {self.target_position}")
                    return True # Waypoint reached
            else:
                self.position += potential_movement
                self.logger.debug(f"Agent {self.id} _follow_path: Moved. New position: {self.position}")
        
        self.logger.debug(f"Agent {self.id} _follow_path: Waypoint {self.target_position} not yet reached. Returning False.")
        return False # Waypoint not yet reached

    def _move_randomly(self, dt: float):
        """Moves the agent randomly. If a path is set, it follows it. Otherwise, picks a new random target."""
        self.logger.debug(f"Agent {self.id} _move_randomly: Current state: {self.state.name}, Has path: {self.current_path is not None}")
        if not self.current_path and self.state == AgentState.MOVING_RANDOMLY: # Only pick new random if no path and in this state
            self.logger.debug(f"Agent {self.id} _move_randomly: No current path and in MOVING_RANDOMLY state. Attempting to pick new random target.")
            if self.grid.width_in_cells > 0 and self.grid.height_in_cells > 0: # type: ignore
                random_target_pos = pygame.math.Vector2(
                    random.uniform(0, self.grid.width_in_cells - 1), # type: ignore
                    random.uniform(0, self.grid.height_in_cells - 1) # type: ignore
                )
                # Ensure it's int for grid purposes
                random_target_pos.x = int(round(max(0, min(random_target_pos.x, self.grid.width_in_cells - 1)))) # type: ignore
                random_target_pos.y = int(round(max(0, min(random_target_pos.y, self.grid.height_in_cells - 1)))) # type: ignore
                
                self.logger.debug(f"Agent {self.id} _move_randomly: New random target: {random_target_pos}") # Existing
                self.set_target(random_target_pos) # This will calculate path
                if not self.current_path: # Path calculation failed
                    self.logger.warning(f"Agent {self.id} _move_randomly: Pathfinding FAILED for random move to {random_target_pos}. Becoming IDLE.") # Existing, modified
                    self.set_objective_idle() # Become idle if can't path to random spot
                    return
                else:
                    self.logger.debug(f"Agent {self.id} _move_randomly: Pathfinding SUCCEEDED for random move. Path: {self.current_path}")
            else: # Grid not valid
                self.logger.warning(f"Agent {self.id} _move_randomly: Grid not valid (width/height <=0). Becoming IDLE.")
                self.set_objective_idle()
                return

        # Now, follow the path if one exists (either newly calculated or pre-existing for random move)
        if self.current_path:
            self.logger.debug(f"Agent {self.id} _move_randomly: Following existing path. Waypoint: {self.target_position}, Path: {self.current_path}")
            if self._follow_path(dt): # True if waypoint reached
                self.logger.debug(f"Agent {self.id} _move_randomly: _follow_path returned True (waypoint reached or path ended).")
                if not self.current_path: # Path is now complete
                    self.logger.debug(f"Agent {self.id} _move_randomly: Random move path completed. Becoming IDLE.")
                    # print(f"DEBUG: Agent {self.id} completed random move path.")
                    self.set_objective_idle() # Finished random move, become idle
                # else: still on path, _follow_path handled next waypoint
            # else: waypoint not reached, continue following
        elif self.state == AgentState.MOVING_RANDOMLY : # No path, but was supposed to be moving randomly
             self.logger.warning(f"Agent {self.id} _move_randomly: In MOVING_RANDOMLY state but no current_path (e.g. pathfinding failed and wasn't caught, or logic error). Becoming IDLE.")
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
                # Agent will try to gather up to its capacity or what the task requires for this trip.
                # This should align with the amount task.prepare() will attempt to reserve at the dropoff.
                # For GatherAndDeliverTask, the amount it tries to reserve at dropoff is:
                # qty_to_reserve_for_delivery = min(task.quantity_to_gather, agent.inventory_capacity)
                # and this is further limited by target_resource_node_ref.current_quantity.
                # For the agent's pre-check, we can estimate based on task.quantity_to_gather and agent's capacity.
                
                # Effective quantity the agent would aim to gather and thus need to reserve space for in one go.
                # This considers what the task wants overall and what the agent can carry.
                # It doesn't consider current node quantity here, as that's a more dynamic check in task.prepare().
                prospective_gather_amount_for_trip = min(task.quantity_to_gather, self.inventory_capacity)
                
                # If agent already has some of the same resource, it can carry less of the new amount.
                # However, the task reservation logic in `prepare` for `GatherAndDeliverTask` calculates
                # `qty_to_reserve_for_delivery` based on `agent.inventory_capacity` (full capacity for the trip)
                # and `task.quantity_to_gather`, not current free space.
                # The actual gathering step then considers `can_carry_more`.
                # To be consistent with the reservation logic, we use full capacity for this check.
                # If the task is designed for multiple trips, this check might need to be smarter or rely on task.prepare failing.
                # For now, let's assume a task aims to fill up for one trip if possible.

                if prospective_gather_amount_for_trip <= 0: # If task quantity is 0 or agent capacity is 0
                    self.logger.debug(f"Agent {self.id}: Task {task.task_id} - Prospective gather amount is {prospective_gather_amount_for_trip}. Skipping dropoff check or defaulting to 1.")
                    # If task.quantity_to_gather is 0, it's a strange task, but let's assume it might still be valid if it means "gather what you can".
                    # If agent capacity is 0, it can't do the task. This should be caught by inventory checks.
                    # For safety, if it's 0, let's still check for min_capacity=1 as a fallback.
                    prospective_gather_amount_for_trip = 1
                
                if not resource_manager.has_available_dropoffs(task_resource_type, min_capacity=prospective_gather_amount_for_trip):
                    self.logger.debug(f"Agent {self.id}: Task {task.task_id} - No available dropoffs for {task_resource_type.name} (checked for capacity: {prospective_gather_amount_for_trip}). Skipping.") # Changed
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
        """Updates the agent's behavior based on its current intent or fallback to old state logic."""
        self.logger.debug(f"Agent {self.id} update START. Behavior: {self.current_behavior}, Intent: {self.current_intent.intent_id if self.current_intent else 'None'}, Old State: {self.state.name}")

        if self.current_intent and self.current_behavior:
            # --- New Behavior/Intent System ---
            self.logger.debug(f"Agent {self.id} updating behavior {self.current_behavior} for intent {self.current_intent.intent_id if self.current_intent else 'None'}")
            intent_status_update = self.current_behavior.update(dt)

            if intent_status_update is not None: # Behavior signals intent outcome
                if self.current_intent:
                    self.current_intent.status = intent_status_update
                    log_message = f"Agent {self.id}: Intent {self.current_intent.intent_id} ({self.current_intent.get_description()}) outcome: {intent_status_update.name}."
                    if self.current_intent.error_message:
                        log_message += f" Error: {self.current_intent.error_message}"
                    
                    if intent_status_update == IntentStatus.FAILED:
                        self.logger.warning(log_message)
                    else:
                        self.logger.info(log_message)

                    # Notify the task that owns this intent, if a task is currently assigned via the old system.
                    # This allows the task to react to the intent's outcome.
                    if self.current_task and hasattr(self.current_task, 'on_intent_outcome') and self.current_intent:
                        self.logger.debug(f"Agent {self.id} notifying task {self.current_task.task_id} of intent {self.current_intent.intent_id} outcome: {intent_status_update.name}")
                        self.current_task.on_intent_outcome(self, self.current_intent.intent_id, intent_status_update, resource_manager)
                    elif not self.current_task and self.current_intent:
                        self.logger.debug(f"Agent {self.id}: Intent {self.current_intent.intent_id} finished with {intent_status_update.name}, but no current_task to notify (intent might be agent-internal).")
                    
                    if intent_status_update == IntentStatus.FAILED:
                        if not isinstance(self.current_behavior, PathFailedBehavior):
                             self._transition_behavior(PathFailedBehavior, self.current_intent)
                        elif isinstance(self.current_behavior, PathFailedBehavior): # Already in PathFailed, so clear intent and evaluate
                             self.current_intent = None
                             self._transition_behavior(EvaluatingIntentBehavior)

                    elif intent_status_update == IntentStatus.COMPLETED:
                        if isinstance(self.current_intent, GatherIntent):
                            gathered_qty = self.current_intent.quantity_to_gather
                            resource_type = self.current_intent.resource_type
                            if self.current_inventory['resource_type'] is None or self.current_inventory['resource_type'] == resource_type:
                                self.current_inventory['resource_type'] = resource_type
                                self.current_inventory['quantity'] = self.current_inventory.get('quantity',0) + gathered_qty # type: ignore
                                self.logger.info(f"Agent {self.id} inventory updated: +{gathered_qty} of {resource_type}. New total: {self.current_inventory['quantity']}")
                            else:
                                self.logger.error(f"Agent {self.id} inventory mismatch after GatherIntent. Has {self.current_inventory['resource_type']}, gathered {resource_type}")
                        elif isinstance(self.current_intent, DeliverIntent):
                            delivered_qty = self.current_intent.quantity_to_deliver
                            self.current_inventory['quantity'] = self.current_inventory.get('quantity',0) - delivered_qty # type: ignore
                            if self.current_inventory.get('quantity', 0) <= 0:
                                self.current_inventory['quantity'] = 0
                                self.current_inventory['resource_type'] = None
                            self.logger.info(f"Agent {self.id} inventory updated: -{delivered_qty}. New total: {self.current_inventory['quantity']}")
                        
                        self.current_intent = None
                        self._transition_behavior(EvaluatingIntentBehavior)

                    elif intent_status_update == IntentStatus.CANCELLED:
                        self.logger.info(f"Agent {self.id}: Intent {self.current_intent.intent_id} was cancelled.")
                        self.current_intent = None
                        self._transition_behavior(EvaluatingIntentBehavior)
                
                else:
                    self.logger.error(f"Agent {self.id}: Behavior {self.current_behavior} reported intent status but no current_intent was set.")
                    self._transition_behavior(IdleBehavior)
            
            elif isinstance(self.current_behavior, EvaluatingIntentBehavior):
                if self.current_intent and self.current_intent.status == IntentStatus.PENDING:
                    self._process_current_intent()
                elif not self.current_intent:
                    self._seek_new_work_or_fallback(dt, resource_manager)

        else:
            self.logger.debug(f"Agent {self.id} falling back to old state system. Current old state: {self.state.name}")
            current_time = pygame.time.get_ticks() / 1000.0

            if self.current_task:
                new_task_status = self.current_task.execute_step(self, dt, resource_manager)
                if new_task_status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    self.logger.info(f"Agent {self.id} (fallback): Task {self.current_task.task_id} finished with status {new_task_status.name}.")
                    self.current_task.cleanup(self, resource_manager, success=(new_task_status == TaskStatus.COMPLETED))
                    self.task_manager_ref.report_task_outcome(self.current_task, new_task_status, self)
                    self.current_task = None
                    self.set_objective_idle()
                    if new_task_status == TaskStatus.COMPLETED and self.current_inventory['quantity'] == 0:
                        self.current_inventory['resource_type'] = None
            else:
                self._seek_new_work_or_fallback(dt, resource_manager)

            if self.state == AgentState.GATHERING_RESOURCE:
                if self.gathering_timer > 0:
                    self.gathering_timer -= dt
                    if self.gathering_timer < 0: self.gathering_timer = 0
            elif self.state == AgentState.DELIVERING_RESOURCE:
                if self.delivery_timer > 0:
                    self.delivery_timer -= dt
                    if self.delivery_timer < 0: self.delivery_timer = 0
            elif self.state == AgentState.COLLECTING_FROM_PROCESSOR:
                if self.gathering_timer > 0:
                    self.gathering_timer -= dt
                    if self.gathering_timer < 0: self.gathering_timer = 0
            elif self.state == AgentState.DELIVERING_TO_PROCESSOR:
                if self.delivery_timer > 0:
                    self.delivery_timer -= dt
                    if self.delivery_timer < 0: self.delivery_timer = 0
        
        if not self.current_intent and not self.current_task:
            if self.state not in [AgentState.IDLE, AgentState.EVALUATING_TASKS, AgentState.MOVING_RANDOMLY]:
                self.logger.warning(f"Agent {self.id} (fallback): No task/intent, but in old state {self.state.name}. Forcing IDLE (old system).")
                self.set_objective_idle()


    def draw(self, screen: pygame.Surface, grid):
        """Draws the agent on the screen."""
        screen_pos = self.grid.grid_to_screen(self.position) # type: ignore
        agent_radius = self.grid.cell_width // 2 # type: ignore

        current_display_color = self.color # Default
        if self.current_intent and self.current_behavior: # New system active
            current_display_color = self.behavior_colors.get(type(self.current_behavior), self.color)
        else: # Fallback to old system color
            current_display_color = self._old_state_colors.get(self.state, self.color)
            
        pygame.draw.circle(screen, current_display_color, screen_pos, agent_radius)

        if self.current_inventory['quantity'] > 0 and self.current_inventory['resource_type'] is not None:
            carried_resource_type = self.current_inventory['resource_type']
            # Ensure carried_resource_type is a ResourceType enum or has a .name attribute
            key_for_color = carried_resource_type.name if hasattr(carried_resource_type, 'name') else str(carried_resource_type)
            resource_color = self.config.RESOURCE_VISUAL_COLORS.get(key_for_color, (128, 128, 128))

            icon_radius = agent_radius // 2
            icon_offset_y = -agent_radius - icon_radius // 2
            icon_center_x = screen_pos[0]
            icon_center_y = screen_pos[1] + icon_offset_y
            
            pygame.draw.circle(screen, resource_color, (icon_center_x, icon_center_y), icon_radius)