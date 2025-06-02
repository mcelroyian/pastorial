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
# from .agent_defs import AgentState # Kept for now for fallback logic - REMOVING
from .intents import Intent, IntentStatus, MoveIntent, GatherIntent, DeliverIntent, InteractAtTargetIntent, RandomMoveIntent
from .agent_behaviors import AgentBehavior, IdleBehavior, MovingBehavior, InteractingBehavior, PathFailedBehavior, EvaluatingIntentBehavior


# Forward references for type hinting
if TYPE_CHECKING:
    from ..tasks.task import Task
    from ..tasks.task_manager import TaskManager
    from ..resources.manager import ResourceManager
    from ..tasks.task import Task # For type hinting current_task if kept temporarily
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
        self.random = random # For random decisions, e.g. RandomMoveIntent target
        self.pygame = pygame # For Vector2, etc.

        # --- Old State System (REMOVED) ---
        # self.state = AgentState.IDLE # REMOVED
        # self._old_state_colors = { ... } # REMOVED
        # self.gathering_timer: float = 0.0 # REMOVED
        # self.delivery_timer: float = 0.0 # REMOVED
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
        # self.task_evaluation_cooldown = 1.0 # REMOVED - Was for old system
        # self._last_task_evaluation_time = 0.0 # REMOVED

        self.inventory_capacity: int = inventory_capacity
        self.current_inventory: Dict[str, Optional[ResourceType] | int] = { # type: ignore
            'resource_type': None,
            'quantity': 0
        }
        
        # self.current_task: Optional['Task'] = None # REMOVED - Old system context
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

        self.logger.debug(f"Agent {self.id} processing intent: {self.current_intent} (Type: {type(self.current_intent)})")
        self.current_intent.status = IntentStatus.ACTIVE # Mark as active as we are starting it

        intent_type = type(self.current_intent)
        self.logger.debug(f"Agent {self.id} _process_current_intent: Intent type determined as {intent_type}")

        if intent_type == MoveIntent or intent_type == RandomMoveIntent:
            self.logger.debug(f"Agent {self.id} _process_current_intent: Matched MoveIntent or RandomMoveIntent. Transitioning to MovingBehavior.")
            self._transition_behavior(MovingBehavior, self.current_intent)
        elif intent_type == GatherIntent or intent_type == DeliverIntent or intent_type == InteractAtTargetIntent:
            # Note: GatherIntent and DeliverIntent might be phased out in favor of tasks submitting
            # sequences of MoveIntent and InteractAtTargetIntent.
            self.logger.debug(f"Agent {self.id} _process_current_intent: Matched Gather/Deliver/InteractAtTargetIntent group. Current intent actual type: {type(self.current_intent)}")
            if isinstance(self.current_intent, (GatherIntent, DeliverIntent, InteractAtTargetIntent)):
                 self.logger.debug(f"Agent {self.id} _process_current_intent: isinstance check PASSED for InteractingBehavior. Transitioning to InteractingBehavior with intent: {self.current_intent}")
                 self._transition_behavior(InteractingBehavior, self.current_intent)
            else: # Should not happen if intent_type matched
                 self.logger.error(f"Agent {self.id}: Unhandled intent type {intent_type} in _process_current_intent after type check (isinstance FAILED). Intent: {self.current_intent}")
                 if self.current_intent: # Check if current_intent is not None before accessing status
                    self.current_intent.status = IntentStatus.FAILED
                    self.current_intent.error_message = f"Agent cannot handle intent type {intent_type} (isinstance failed)"
                 self._transition_behavior(IdleBehavior) # Fallback to Idle
        else:
            self.logger.warning(f"Agent {self.id}: Unknown intent type {intent_type}. Intent: {self.current_intent}. Transitioning to IdleBehavior.")
            if self.current_intent: # Check if current_intent is not None
                self.current_intent.status = IntentStatus.FAILED
                self.current_intent.error_message = f"Unknown intent type: {intent_type}"
            self._transition_behavior(IdleBehavior) # Fallback to Idle

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

    def acquire_task_or_perform_idle_action(self, dt: float, resource_manager: 'ResourceManager'):
        """
        Called by EvaluatingIntentBehavior when no current_intent exists.
        Attempts to acquire a new task. If no task is found, may perform an idle action (e.g., random move).
        """
        self.logger.debug(f"Agent {self.id} attempting to acquire task or perform idle action.")

        # Attempt to get a task assigned by the TaskManager.
        # The TaskManager's assign_task_to_agent method will handle:
        # - Finding a suitable task
        # - Claiming it for the agent
        # - Calling task.prepare(), which should submit the first intent.
        task_assigned_and_prepared = self.task_manager_ref.assign_task_to_agent(self, resource_manager)

        if task_assigned_and_prepared:
            self.logger.info(f"Agent {self.id}: TaskManager assigned and prepared a task. Current intent should be set by task.prepare().")
            # If assign_task_to_agent was successful, self.current_intent should have been set
            # by the task's prepare() method calling self.submit_intent().
            # EvaluatingIntentBehavior will pick this up in the next cycle or if _process_current_intent is called.
            if self.current_intent and self.current_intent.status == IntentStatus.PENDING:
                self._process_current_intent() # Process it immediately if PENDING
            elif not self.current_intent:
                self.logger.warning(f"Agent {self.id}: TaskManager.assign_task_to_agent reported success, but no current_intent was set by task.prepare(). This is unexpected.")
                # Fallback to random move if intent wasn't set for some reason
                self.logger.info(f"Agent {self.id} submitting RandomMoveIntent as a fallback after failed task intent submission.")
                random_move = RandomMoveIntent()
                self.submit_intent(random_move)
        else:
            # No task was assigned or task preparation failed.
            # Perform idle action: submit a RandomMoveIntent.
            self.logger.info(f"Agent {self.id}: No task assigned or task preparation failed. Submitting RandomMoveIntent.")
            random_move = RandomMoveIntent()
            self.submit_intent(random_move)

    # --- End New Intent and Behavior Methods ---

    # _seek_new_work_or_fallback is being removed as its functionality
    # is moving into acquire_task_or_perform_idle_action and behaviors.

    # _evaluate_and_select_task is being removed as task selection logic
    # will be handled by TaskManager.assign_task_to_agent or refined in acquire_task_or_perform_idle_action.

    # _move_randomly is being removed as RandomMoveIntent + MovingBehavior will handle this.

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

    # All set_objective_* methods are being removed as they pertain to the old state system.


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

    # _move_randomly has been removed. Random movement is handled by RandomMoveIntent + MovingBehavior.
    # _evaluate_and_select_task has been removed. Task selection is now initiated by
    # acquire_task_or_perform_idle_action calling TaskManager.assign_task_to_agent.

    def update(self, dt: float, resource_manager: 'ResourceManager'):
        """Updates the agent's behavior based on its current intent."""
        self.logger.debug(f"Agent {self.id} update START. Behavior: {self.current_behavior}, Intent: {self.current_intent.intent_id if self.current_intent else 'None'}")

        # The primary driving force is the current behavior processing the current intent,
        # or EvaluatingIntentBehavior finding a new intent.
        if not self.current_behavior:
            self.logger.error(f"Agent {self.id} has no current_behavior. This should not happen. Defaulting to IdleBehavior.")
            self._transition_behavior(IdleBehavior) # Should not happen, but as a safeguard

        # current_behavior.update() is the main logic driver.
        # It might return an IntentStatus if the intent it was handling is done.
        intent_status_update = self.current_behavior.update(dt, resource_manager)

        if intent_status_update is not None: # Behavior signals an intent it was handling has finished
            if self.current_intent:
                completed_intent_id = self.current_intent.intent_id
                self.current_intent.status = intent_status_update
                log_message = f"Agent {self.id}: Intent {self.current_intent.intent_id} ({self.current_intent.get_description()}) outcome: {intent_status_update.name}."
                if self.current_intent.error_message:
                    log_message += f" Error: {self.current_intent.error_message}"
                
                if intent_status_update == IntentStatus.FAILED:
                    self.logger.warning(log_message)
                else:
                    self.logger.info(log_message)
    
                    task_fully_concluded = False
                    originating_task_id_of_intent = None
    
                    # Notify the task that owns this intent.
                    if self.current_intent.originating_task_id:
                        originating_task_id_of_intent = self.current_intent.originating_task_id
                        self.logger.debug(f"Agent {self.id} notifying TaskManager about intent {self.current_intent.intent_id} outcome for task {originating_task_id_of_intent}.")
                        self.task_manager_ref.notify_task_intent_outcome(
                            originating_task_id_of_intent,
                            self.current_intent.intent_id,
                            intent_status_update,
                            resource_manager,
                            self
                        )
    
                        # After notifying the task, check if the task itself is now completed or failed.
                        task_object = self.task_manager_ref.get_task_by_id(originating_task_id_of_intent)
                        self.logger.debug(f"Agent {self.id} post-notify: Task ID {originating_task_id_of_intent}. Retrieved task_object: {'Exists' if task_object else 'None'}. Intent outcome: {intent_status_update.name if intent_status_update else 'N/A'}")
                        if task_object:
                            self.logger.debug(f"Agent {self.id} post-notify: Task {task_object.task_id} current status from agent's perspective: {task_object.status.name if task_object.status else 'N/A'}")
                            if task_object.status == TaskStatus.COMPLETED or task_object.status == TaskStatus.FAILED:
                                self.logger.info(f"Agent {self.id}: Task {task_object.task_id} (Type: {task_object.task_type.name}) has reached terminal state: {task_object.status.name} after intent {self.current_intent.intent_id} outcome.")
                                self.task_manager_ref.report_task_outcome(task_object, task_object.status, self)
                                task_fully_concluded = True
                                # Task cleanup (like releasing resources) should be handled by Task.cleanup()
                                # which should be called by TaskManager.report_task_outcome or by the task itself.
                                # For now, ensure TaskManager handles it.
                        else:
                            self.logger.warning(f"Agent {self.id}: Could not retrieve task {originating_task_id_of_intent} after intent outcome to check its final status.")
    
                    else: # Intent exists but no originating task (e.g. RandomMoveIntent)
                        self.logger.debug(f"Agent {self.id}: Intent {self.current_intent.intent_id} (type: {type(self.current_intent)}) finished with {intent_status_update.name}, but no originating_task_id. No task to notify or report outcome for.")
                        task_fully_concluded = True # Treat as concluded for the agent's current_intent processing
    
                    # Decide next step based on intent outcome
                    if intent_status_update == IntentStatus.FAILED:
                        # If the task itself hasn't failed yet (e.g. intent failed but task might retry/recover)
                        # then the agent might enter PathFailedBehavior.
                        # If the task_fully_concluded as FAILED, then agent should just find new work.
                        if not task_fully_concluded: # Task might still be trying to recover or has other steps
                            if not isinstance(self.current_behavior, PathFailedBehavior):
                                self._transition_behavior(PathFailedBehavior, self.current_intent) # Show path failure for this intent
                            else: # Already in PathFailed, means the PathFailedBehavior itself "completed" its duty
                                self.current_intent = None # Clear the failed intent
                                self._transition_behavior(EvaluatingIntentBehavior) # Go find new work
                        else: # Task itself is FAILED and reported
                            self.current_intent = None
                            self._transition_behavior(EvaluatingIntentBehavior)
    
    
                    elif intent_status_update == IntentStatus.COMPLETED:
                        # Inventory updates for old Gather/Deliver intents (should be phased out)
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
                        
                        # If the task is fully concluded (COMPLETED or FAILED and reported), or if there was no task,
                        # the agent should clear its current_intent and seek new work/evaluate next chained intent.
                        # If the task is NOT fully_concluded, it means the task's on_intent_outcome might have submitted a new intent.
                        # In that case, current_intent would be updated, and EvaluatingIntentBehavior will pick it up.
                        if task_fully_concluded:
                            if self.current_intent and self.current_intent.intent_id == completed_intent_id:
                                 self.current_intent = None # Clear the intent that just finished
                            self._transition_behavior(EvaluatingIntentBehavior)
                        # If not task_fully_concluded, it implies the task itself has submitted a new intent.
                        # The agent's current_intent might have been updated by task.on_intent_outcome.
                        # Transitioning to EvaluatingIntentBehavior will handle processing this new/pending intent.
                        else:
                             self.logger.debug(f"Agent {self.id}: Intent {completed_intent_id} COMPLETED, but task {originating_task_id_of_intent} not yet terminal. Task will submit next intent. Current agent intent: {self.current_intent.intent_id if self.current_intent else 'None'}")
                             self._transition_behavior(EvaluatingIntentBehavior)
    
    
                    elif intent_status_update == IntentStatus.CANCELLED:
                        self.logger.info(f"Agent {self.id}: Intent {completed_intent_id} was cancelled.")
                        # If task was associated, it should have been marked FAILED by notify_task_intent_outcome
                        # and then reported by the logic above.
                        if self.current_intent and self.current_intent.intent_id == completed_intent_id:
                            self.current_intent = None
                        self._transition_behavior(EvaluatingIntentBehavior) # Go find new work
                
                    else:
                        self.logger.error(f"Agent {self.id}: Behavior {self.current_behavior} reported intent status but no current_intent was set on agent.")
                        self._transition_behavior(IdleBehavior) # Default to idle
        
        # If no intent status update was returned by the behavior, it means the behavior is ongoing.
        # If the behavior is EvaluatingIntentBehavior, its update method should have already
        # called _process_current_intent (if a PENDING intent exists) or
        # acquire_task_or_perform_idle_action (if no intent exists).
        # So, no further direct action needed here for EvaluatingIntentBehavior.
        
        # Fallback logic (to be removed)
        # The 'else' part of the original 'if self.current_intent and self.current_behavior:'
        # which contained the old state system logic, is now removed.
        # If an agent somehow ends up with no current_intent and is not in EvaluatingIntentBehavior,
        # it should naturally transition to EvaluatingIntentBehavior when its current behavior completes
        # or if an external event submits a new intent.
        # If it's in IdleBehavior, it will stay there until a new intent is submitted.
        # EvaluatingIntentBehavior is responsible for proactive work seeking.

        # Final check: if agent is not in a behavior that actively seeks work (like EvaluatingIntentBehavior)
        # and has no intent, it should probably be in Idle or transition to Evaluating to find work.
        # This is mostly handled by behaviors transitioning to EvaluatingIntentBehavior upon completion.
        if not self.current_intent and not isinstance(self.current_behavior, EvaluatingIntentBehavior) and not isinstance(self.current_behavior, IdleBehavior) :
            self.logger.debug(f"Agent {self.id} has no intent and is in behavior {self.current_behavior}. Transitioning to EvaluatingIntentBehavior to find work.")
            self._transition_behavior(EvaluatingIntentBehavior)
        elif not self.current_intent and isinstance(self.current_behavior, IdleBehavior):
            # If truly idle with no intent, it should try to find work.
            # This can be done by transitioning to EvaluatingIntentBehavior.
            # This ensures an agent doesn't get stuck in Idle if acquire_task_or_perform_idle_action
            # somehow didn't result in an immediate new intent (e.g. cooldowns in task manager).
            self.logger.debug(f"Agent {self.id} is Idle with no intent. Transitioning to EvaluatingIntentBehavior to seek work.")
            self._transition_behavior(EvaluatingIntentBehavior)


    def draw(self, screen: pygame.Surface, grid):
        """Draws the agent on the screen."""
        screen_pos = self.grid.grid_to_screen(self.position) # type: ignore
        agent_radius = self.grid.cell_width // 2 # type: ignore

        current_display_color = self.color # Default
        # Always use new system for color, as old system is being removed.
        # If no current_intent, it might be in IdleBehavior or EvaluatingIntentBehavior.
        current_display_color = self.behavior_colors.get(type(self.current_behavior), self.color)
            
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