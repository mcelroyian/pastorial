import pygame
import uuid
import random
import logging
from typing import List, Dict, Optional, TYPE_CHECKING

from ..resources.resource_types import ResourceType
from ..core import config
from ..tasks.task import GatherAndDeliverTask, DeliverWheatToMillTask, EatTask
from ..tasks.task_types import TaskStatus, TaskType
from ..pathfinding.astar import find_path
from .intents import Intent, IntentStatus, MoveIntent, InteractAtTargetIntent, RandomMoveIntent
from .agent_behaviors import AgentBehavior, IdleBehavior, MovingBehavior, InteractingBehavior, PathFailedBehavior, EvaluatingIntentBehavior
from .needs import Needs

if TYPE_CHECKING:
    from ..tasks.task import Task
    from ..tasks.task_manager import TaskManager
    from ..resources.manager import ResourceManager


class Agent:
    """Represents an autonomous agent in the simulation, executing tasks and intents."""

    def __init__(self,
                 agent_id: uuid.UUID,
                 agent_name: str,
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
            agent_name (str): A human-readable name for the agent.
            position (pygame.math.Vector2): The starting grid coordinates of the agent.
            speed (float): The movement speed of the agent (grid units per second).
            grid (Grid): The simulation grid object.
            task_manager (TaskManager): Reference to the global task manager.
            inventory_capacity (int): Maximum number of resource units the agent can carry.
            resource_priorities (Optional[List[ResourceType]]): Ordered list of resource types the agent prefers.
        """
        self.id: uuid.UUID = agent_id
        self.name: str = agent_name
        self.position = position
        self.speed = speed
        self.grid = grid # type: ignore
        self.task_manager_ref: 'TaskManager' = task_manager
        self.config = config
        logger = logging.getLogger(__name__)
        self.logger = logging.LoggerAdapter(logger, {'agent_id': self.id, 'agent_name': self.name})
        self.random = random # For random decisions, e.g. RandomMoveIntent target
        self.pygame = pygame # For Vector2, etc.


        # --- Behavior/Intent System ---
        self.current_intent: Optional[Intent] = None
        self.current_behavior: AgentBehavior = IdleBehavior(self)

        self.target_position: Optional[pygame.math.Vector2] = None
        self.current_path: Optional[List[pygame.math.Vector2]] = None # For A* path
        self.final_destination: Optional[pygame.math.Vector2] = None # Ultimate goal of a movement sequence (used by set_target)
        self.target_tolerance = 0.1

        self.inventory_capacity: int = inventory_capacity
        self.current_inventory: Dict[str, Optional[ResourceType] | int] = { # type: ignore
            'resource_type': None,
            'quantity': 0
        }

        self.resource_priorities: Optional[List[ResourceType]] = resource_priorities

        self.needs: Needs = Needs()
        self.owner_faction_id: Optional[int] = None  # set by Simulation at spawn

        # Initialize the first behavior after all attributes are set
        self.current_behavior.enter()


    # --- New Intent and Behavior Methods ---
    def submit_intent(self, intent: Intent):
        """
        Submits a new intent for the agent to process.
        The agent will transition to EvaluatingIntentBehavior to handle it.
        """
        if self.current_intent and self.current_intent.status == IntentStatus.ACTIVE:
            self.logger.warning(f"Received new intent {intent.intent_id} while current intent {self.current_intent.intent_id} is active. Overwriting.")
            # Optionally, handle cancellation of the old intent here.
            self.current_intent.status = IntentStatus.CANCELLED # Mark as cancelled

        self.logger.info(f"Received new intent: {intent}")
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

        self.logger.debug(f"Processing intent: {self.current_intent} (Type: {type(self.current_intent)})")
        self.current_intent.status = IntentStatus.ACTIVE

        intent_type = type(self.current_intent)

        if intent_type in (MoveIntent, RandomMoveIntent):
            self._transition_behavior(MovingBehavior, self.current_intent)
        elif intent_type == InteractAtTargetIntent:
            self._transition_behavior(InteractingBehavior, self.current_intent)
        else:
            self.logger.warning(f"Unknown intent type {intent_type}. Failing intent.")
            self.current_intent.status = IntentStatus.FAILED
            self.current_intent.error_message = f"Unknown intent type: {intent_type}"
            self._transition_behavior(IdleBehavior)

    def _transition_behavior(self, new_behavior_class_or_instance, intent_for_behavior: Optional[Intent] = None):
        """Helper method to transition between behaviors."""
        if self.current_behavior:
            self.logger.debug(f"Exiting behavior: {self.current_behavior}")
            self.current_behavior.exit()

        if isinstance(new_behavior_class_or_instance, AgentBehavior):
            self.current_behavior = new_behavior_class_or_instance
        else: # It's a class, so instantiate it
            self.current_behavior = new_behavior_class_or_instance(self)
        
        self.logger.info(f"Transitioned to behavior: {self.current_behavior} for intent: {intent_for_behavior.intent_id if intent_for_behavior else 'None'}")
        self.current_behavior.enter(intent_for_behavior if intent_for_behavior else self.current_intent)

    def acquire_task_or_perform_idle_action(self, dt: float, resource_manager: 'ResourceManager'):
        """
        Called by EvaluatingIntentBehavior when no current_intent exists.
        Hungry agents self-generate an EatTask before pulling from the job board.
        """
        self.logger.debug(f"Attempting to acquire task or perform idle action.")

        # Personal need: hunger. Self-generate EatTask — never posted to the shared board.
        if (self.needs.hunger < config.HUNGER_SEEK_FOOD_THRESHOLD
                and self.needs.eat_retry_timer <= 0.0):
            eat_task = EatTask(priority=100)
            eat_task.agent_id = self.id
            if eat_task.prepare(self, resource_manager):
                eat_task.status = TaskStatus.ASSIGNED
                self.task_manager_ref.assigned_tasks[self.id] = eat_task
                self.logger.info(f"Self-generated EatTask (hunger={self.needs.hunger:.2f}).")
                if self.current_intent and self.current_intent.status == IntentStatus.PENDING:
                    self._process_current_intent()
                return
            else:
                # No bread right now — retry after cooldown, continue normal work
                self.needs.eat_retry_timer = config.EAT_RETRY_COOLDOWN
                self.logger.info(f"EatTask.prepare failed (no bread). Retry in {config.EAT_RETRY_COOLDOWN}s.")

        # Normal job-board path
        task_assigned_and_prepared = self.task_manager_ref.assign_task_to_agent(self, resource_manager)

        if task_assigned_and_prepared:
            self.logger.info(f"TaskManager assigned and prepared a task.")
            if self.current_intent and self.current_intent.status == IntentStatus.PENDING:
                self._process_current_intent()
            elif not self.current_intent:
                self.logger.warning(f"assign_task_to_agent reported success but no intent was set.")
                self.submit_intent(RandomMoveIntent())
        else:
            self.logger.info(f"No task assigned. Submitting RandomMoveIntent.")
            self.submit_intent(RandomMoveIntent())

    def set_target(self, final_destination: pygame.math.Vector2):
        """
        Sets the agent's final destination and calculates the path.
        The agent's 'target_position' will be the next waypoint in the path.
        """
        self.logger.debug(f"Set_target: Called with final_destination: {final_destination}, current_pos: {self.position}")
        self.final_destination = final_destination
        # Ensure positions are integers for pathfinding if they represent grid cells
        current_grid_pos = pygame.math.Vector2(int(round(self.position.x)), int(round(self.position.y)))
        final_grid_dest = pygame.math.Vector2(int(round(final_destination.x)), int(round(final_destination.y)))

        if current_grid_pos == final_grid_dest:
            self.current_path = [final_grid_dest] # Path is just the destination
            self.target_position = final_grid_dest # Already there or very close
            self.logger.debug(f"Set_target: Already at/near final destination {final_grid_dest}.") # Existing
            return

        self.current_path = find_path(current_grid_pos, final_grid_dest, self.grid) # type: ignore
        self.logger.debug(f"Set_target: Pathfinding requested from {current_grid_pos} to {final_grid_dest}. Result path: {'Found, length ' + str(len(self.current_path)) if self.current_path else 'None'})")

        if self.current_path and len(self.current_path) > 0:
            # Remove current position if it's the start of the path
            if self.current_path[0] == current_grid_pos and len(self.current_path) > 1:
                self.current_path.pop(0)
                self.logger.debug(f"Set_target: Popped current position from path. New path: {self.current_path}")
            
            if not self.current_path: # Path might have become empty after pop
                self.target_position = final_grid_dest # Essentially means we are at the destination
                self.logger.debug(f"Set_target: Path to {final_grid_dest} resulted in empty path after pop (likely at destination).") # Existing
                self.current_path = [final_grid_dest] # Ensure path isn't None
                return

            self.target_position = self.current_path[0]
            self.logger.debug(f"Set_target: Path set. Next waypoint: {self.target_position}. Full path: {self.current_path}")
            # print(f"DEBUG: Agent {self.id} set_target: New path to {final_grid_dest}. Next waypoint: {self.target_position}. Path: {self.current_path}")
        else: # Pathfinding failed or returned empty path initially
            self.target_position = None
            self.current_path = None # Ensure it's None if no path
            self.logger.warning(f"Set_target: Pathfinding FAILED or returned empty. Could not find a path from {current_grid_pos} to {final_grid_dest}.") # Modified existing warning
            # Consider setting agent to IDLE or a "PATH_FAILED" state if path is None
            # For now, task execution will likely fail if agent can't reach target.
            # self.set_objective_idle() # Or a specific failure state

    def _follow_path(self, dt: float) -> bool:
        """Move one tick along current_path. Returns True when a waypoint is reached."""
        if not self.current_path or not self.target_position:
            return False

        direction = self.target_position - self.position
        distance_to_waypoint = direction.length()

        if distance_to_waypoint < self.target_tolerance:
            self.logger.debug(f"Reached waypoint {self.target_position}.")
            self.position = pygame.math.Vector2(self.target_position)
            self.current_path.pop(0)
            if not self.current_path:
                self.target_position = None
                self.final_destination = None
                return True
            self.target_position = self.current_path[0]
            return True

        if distance_to_waypoint > 0:
            potential_movement = direction.normalize() * self.speed * self.needs.speed_multiplier * dt
            if potential_movement.length() >= distance_to_waypoint:
                self.logger.debug(f"Reached waypoint {self.target_position} by moving.")
                self.position = pygame.math.Vector2(self.target_position)
                if self.current_path:
                    self.current_path.pop(0)
                if not self.current_path:
                    self.target_position = None
                    self.final_destination = None
                    return True
                self.target_position = self.current_path[0]
                return True
            self.position += potential_movement

        return False

    def update(self, dt: float, resource_manager: 'ResourceManager'):
        """Updates the agent's behavior based on its current intent."""
        self.needs.update(dt)
        self._check_critical_hunger(resource_manager)

        if not self.current_behavior:
            self.logger.error(f"Has no current_behavior. Defaulting to IdleBehavior.")
            self._transition_behavior(IdleBehavior)

        intent_status_update = self.current_behavior.update(dt, resource_manager)

        if intent_status_update is not None and self.current_intent:
            completed_intent_id = self.current_intent.intent_id
            self.current_intent.status = intent_status_update
            log_message = f"Intent {completed_intent_id} ({self.current_intent.get_description()}) outcome: {intent_status_update.name}."
            if self.current_intent.error_message:
                log_message += f" Error: {self.current_intent.error_message}"

            if intent_status_update == IntentStatus.FAILED:
                self.logger.warning(log_message)
            else:
                self.logger.info(log_message)

                task_fully_concluded = False
                originating_task_id_of_intent = None

                if self.current_intent.originating_task_id:
                    originating_task_id_of_intent = self.current_intent.originating_task_id
                    self.task_manager_ref.notify_task_intent_outcome(
                        originating_task_id_of_intent,
                        self.current_intent.intent_id,
                        intent_status_update,
                        resource_manager,
                        self
                    )
                    task_object = self.task_manager_ref.get_task_by_id(originating_task_id_of_intent)
                    if task_object:
                        if task_object.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                            self.logger.info(f"Task {task_object.task_id} ({task_object.task_type.name}) terminal: {task_object.status.name}.")
                            self.task_manager_ref.report_task_outcome(task_object, task_object.status, self)
                            task_fully_concluded = True
                    else:
                        self.logger.warning(f"Could not retrieve task {originating_task_id_of_intent} after intent outcome.")
                else:
                    task_fully_concluded = True

            if intent_status_update in (IntentStatus.FAILED, IntentStatus.CANCELLED):
                self.current_intent = None
                self._transition_behavior(EvaluatingIntentBehavior)
            elif intent_status_update == IntentStatus.COMPLETED:
                if task_fully_concluded:
                    if self.current_intent and self.current_intent.intent_id == completed_intent_id:
                        self.current_intent = None
                else:
                    self.logger.debug(f"Intent {completed_intent_id} COMPLETED; task not yet terminal, awaiting next intent.")
                    if self.current_intent and self.current_intent.intent_id == completed_intent_id:
                        self.current_intent = None
                self._transition_behavior(EvaluatingIntentBehavior)

        if not self.current_intent and not isinstance(self.current_behavior, (EvaluatingIntentBehavior, IdleBehavior)):
            self._transition_behavior(EvaluatingIntentBehavior)
        elif not self.current_intent and isinstance(self.current_behavior, IdleBehavior):
            self._transition_behavior(EvaluatingIntentBehavior)

    def _check_critical_hunger(self, resource_manager: 'ResourceManager') -> None:
        """Abandon the current non-EAT task if hunger is critical so the agent seeks food."""
        if self.needs.hunger >= config.HUNGER_CRITICAL_THRESHOLD:
            return
        current_task = self.task_manager_ref.assigned_tasks.get(self.id)
        if current_task is None or current_task.task_type == TaskType.EAT:
            return
        self.logger.warning(f"Critical hunger ({self.needs.hunger:.2f}). Abandoning {current_task.task_type.name}.")
        current_task.cleanup(self, resource_manager, success=False)
        self.task_manager_ref.report_task_outcome(current_task, TaskStatus.FAILED, self)
        self.current_intent = None
        self.current_path = None
        self.target_position = None
        self.final_destination = None
        self._transition_behavior(EvaluatingIntentBehavior)

    def cancel_current_task(self):
        """Forcefully cancels the agent's current task and intent."""
        self.logger.info(f"Canceling current task and intent.")
        if self.current_intent:
            self.current_intent.status = IntentStatus.CANCELLED
        self.current_intent = None
        self.current_path = None
        self.target_position = None
        self.final_destination = None
        self._transition_behavior(IdleBehavior)