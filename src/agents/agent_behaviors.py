from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

from .intents import Intent, IntentStatus, MoveIntent, RandomMoveIntent # Assuming intents.py is in the same directory
from ..pathfinding.utils import find_closest_walkable_tile

if TYPE_CHECKING:
    from .agent import Agent # To avoid circular import, for type hinting only
    from ..resources.manager import ResourceManager # If behaviors interact directly
    # from ..core.grid import Grid # If behaviors interact directly

class AgentBehavior(ABC):
    """Abstract base class for all agent behaviors (states in the State Pattern)."""

    def __init__(self, agent: 'Agent'):
        self.agent = agent

    @abstractmethod
    def enter(self, intent: Optional[Intent] = None):
        """Called when the agent enters this behavior/state."""
        pass

    @abstractmethod
    def update(self, dt: float, resource_manager: 'ResourceManager') -> Optional[IntentStatus]:
        """
        Called every frame to update the behavior.
        Args:
            dt (float): Delta time.
            resource_manager (ResourceManager): Reference to the resource manager.
        Returns an IntentStatus if the current intent associated with this behavior
        has reached a terminal state (COMPLETED, FAILED).
        Returns None if the behavior is still ongoing.
        """
        pass

    @abstractmethod
    def exit(self):
        """Called when the agent exits this behavior/state."""
        pass

    def __str__(self) -> str:
        return self.__class__.__name__

class IdleBehavior(AgentBehavior):
    """Behavior for when the agent is idle and waiting for an intent or deciding what to do."""
    def enter(self, intent: Optional[Intent] = None):
        self.agent.logger.debug(f"Agent {self.agent.id} entering IdleBehavior.")
        # Agent's internal state (like self.agent.state from AgentState enum) might be set here
        # For now, we focus on the behavior class.
        # The agent might clear its path/target when becoming idle if not handled by exiting another state.
        self.agent.current_path = None
        self.agent.target_position = None
        self.agent.final_destination = None


    def update(self, dt: float, resource_manager: 'ResourceManager') -> Optional[IntentStatus]:
        # In IdleBehavior, the agent might decide to look for tasks (which would be an intent itself)
        # or process a new intent if one is assigned.
        # For now, IdleBehavior itself doesn't complete an "intent".
        # The Agent's main loop will handle transitioning from Idle if a new intent arrives.
        # It could transition to EvaluatingIntentBehavior if it needs to find work.
        self.agent.logger.debug(f"Agent {self.agent.id} in IdleBehavior.update. Considering transition to EvaluatingIntentBehavior.")
        # If an agent is truly idle, it should probably try to find something to do.
        # This transition will be handled by the agent's main loop if a new intent is submitted,
        # or if the agent decides to seek work (which would be a transition to EvaluatingIntentBehavior).
        # For now, let's assume if it's in Idle, it means it has nothing and EvaluatingIntentBehavior will handle seeking.
        return None # Remains idle until agent logic transitions it

    def exit(self):
        self.agent.logger.debug(f"Agent {self.agent.id} exiting IdleBehavior.")

class MovingBehavior(AgentBehavior):
    """Behavior for when the agent is moving towards a target."""
    def __init__(self, agent: 'Agent'):
        super().__init__(agent)
        self.move_intent: Optional[Intent] = None # Store the specific move intent

    def enter(self, intent: Optional[Intent] = None):
        self.agent.logger.debug(f"Agent {self.agent.id} entering MovingBehavior.")
        if isinstance(intent, RandomMoveIntent):
            self.move_intent = intent
            # Pick a random target position
            if self.agent.grid.width_in_cells > 0 and self.agent.grid.height_in_cells > 0:
                random_target_x = self.agent.random.uniform(0, self.agent.grid.width_in_cells - 1)
                random_target_y = self.agent.random.uniform(0, self.agent.grid.height_in_cells - 1)
                target_pos = self.agent.pygame.math.Vector2(
                    int(round(random_target_x)),
                    int(round(random_target_y))
                )
                self.agent.logger.info(f"Agent {self.agent.id} MovingBehavior: RandomMoveIntent, generated target {target_pos}")
                # BUGFIX: Store the generated target on the intent itself so PathFailedBehavior can access it.
                self.move_intent.target_position = target_pos # type: ignore
                self.agent.set_target(target_pos)
            else:
                self.agent.logger.error(f"Agent {self.agent.id} MovingBehavior: RandomMoveIntent but grid is invalid. Cannot set target.")
                self.agent.current_path = None # Ensure no path
        elif intent and hasattr(intent, 'target_position'):
            self.move_intent = intent
            self.agent.set_target(intent.target_position) # type: ignore
        else:
            self.agent.logger.error(f"Agent {self.agent.id} MovingBehavior: Entered without a valid MoveIntent or RandomMoveIntent.")
            self.move_intent = None # Ensure it's None
            self.agent.current_path = None # Ensure no path

        if self.agent.current_path is None and self.move_intent: # Check if pathfinding failed for any type of move intent
            self.agent.logger.warning(f"Agent {self.agent.id} MovingBehavior: Pathfinding failed for intent {self.move_intent.intent_id} (type: {type(self.move_intent)}). Transitioning to PathFailedBehavior.")
            self.agent._transition_behavior(PathFailedBehavior, self.move_intent)
        elif self.move_intent:
            self.agent.logger.debug(f"Agent {self.agent.id} MovingBehavior: Path set for intent {self.move_intent.intent_id} (type: {type(self.move_intent)}).")


    def update(self, dt: float, resource_manager: 'ResourceManager') -> Optional[IntentStatus]:
        if not self.move_intent: # Should have been set in enter()
            self.agent.logger.error(f"Agent {self.agent.id} MovingBehavior: update called but no move_intent set.")
            return IntentStatus.FAILED

        # If pathfinding failed, the agent would have transitioned to PathFailedBehavior in enter().
        # This update loop now only needs to handle the case where there is a valid path.
        if self.agent.target_position:
            path_follow_result = self.agent._follow_path(dt) # _follow_path returns True if waypoint reached or path ended

            if path_follow_result: # Waypoint reached
                if not self.agent.current_path: # Path is now empty, meaning final destination reached
                    self.agent.logger.debug(f"Agent {self.agent.id} MovingBehavior: Path completed for intent {self.move_intent.intent_id}.")
                    return IntentStatus.COMPLETED
        
        # If there's no target position, it implies the path is complete or was never set.
        # If it was never set, the agent would have transitioned to PathFailedBehavior.
        # Therefore, we can assume completion.
        elif not self.agent.current_path:
            self.agent.logger.debug(f"Agent {self.agent.id} MovingBehavior: No target_position and no current_path. Assuming path completed.")
            return IntentStatus.COMPLETED


        return None # Still actively moving or waiting for next update cycle

    def exit(self):
        self.agent.logger.debug(f"Agent {self.agent.id} exiting MovingBehavior.")
        # self.agent.current_path = None # Path should be None if completed, or handled by next state
        # self.agent.target_position = None

class InteractingBehavior(AgentBehavior):
    """Behavior for when the agent is performing a timed interaction (e.g., gathering, delivering)."""
    def __init__(self, agent: 'Agent'):
        super().__init__(agent)
        self.interaction_intent: Optional[Intent] = None
        self.timer: float = 0.0

    def enter(self, intent: Optional[Intent] = None):
        self.agent.logger.debug(f"Agent {self.agent.id} entering InteractingBehavior.")
        if intent:
            self.agent.logger.info(f"Agent {self.agent.id} InteractingBehavior.enter: Received intent type: {type(intent)}")
            self.agent.logger.info(f"Agent {self.agent.id} InteractingBehavior.enter: Intent __dict__: {intent.__dict__}")
            has_duration = hasattr(intent, 'duration')
            self.agent.logger.info(f"Agent {self.agent.id} InteractingBehavior.enter: hasattr(intent, 'duration') -> {has_duration}")
            if has_duration:
                self.agent.logger.info(f"Agent {self.agent.id} InteractingBehavior.enter: intent.duration value: {intent.duration}")

        if intent and hasattr(intent, 'duration'):
            self.interaction_intent = intent
            self.timer = getattr(intent, 'duration', self.agent.config.DEFAULT_GATHERING_TIME) # Fallback, should be on intent
            self.agent.logger.debug(f"Agent {self.agent.id} InteractingBehavior: Starting interaction '{getattr(intent, 'interaction_type', 'Unknown')}' for {self.timer}s. Intent: {intent.intent_id}")
        else:
            self.agent.logger.error(f"Agent {self.agent.id} InteractingBehavior: Entered without a valid InteractAtTargetIntent or duration. Intent was: {intent}")
            self.timer = -1 # Force immediate failure in update

    def update(self, dt: float, resource_manager: 'ResourceManager') -> Optional[IntentStatus]:
        if self.timer < 0: # Invalid setup
            return IntentStatus.FAILED

        self.timer -= dt
        if self.timer <= 0:
            self.agent.logger.debug(f"Agent {self.agent.id} InteractingBehavior: Interaction timer complete for intent {self.interaction_intent.intent_id if self.interaction_intent else 'None'}.")
            # Here, the actual effect of the interaction would be applied by the agent or task logic
            # For example, if it was a GatherIntent, agent.inventory would be updated.
            # The behavior signals completion; the agent's IntentProcessor or task will handle consequences.
            return IntentStatus.COMPLETED
        return None # Interaction ongoing

    def exit(self):
        self.agent.logger.debug(f"Agent {self.agent.id} exiting InteractingBehavior.")
        self.timer = 0.0

class PathFailedBehavior(AgentBehavior):
    """
    Behavior for handling pathfinding failures with recovery strategies like
    finding a new target, retrying, or giving up.
    """
    def __init__(self, agent: 'Agent'):
        super().__init__(agent)
        self.failed_intent: Optional[Intent] = None
        self.retry_count: int = 0
        self.retry_timer: float = 0.0

    def enter(self, intent: Optional[Intent] = None):
        self.agent.logger.warning(f"Agent {self.agent.id} entering PathFailedBehavior for intent {intent.intent_id if intent else 'Unknown'}.")
        if not intent or not hasattr(intent, 'target_position'):
            self.agent.logger.error(f"Agent {self.agent.id} entered PathFailedBehavior without a valid intent with a target position.")
            # Immediately fail if there's no valid intent to work with.
            self.failed_intent = None # Ensure it's None
            return

        self.failed_intent = intent
        self.retry_count = 0
        self.retry_timer = 0.0

        # Strategy 1: If target is unwalkable, find a new one.
        target_pos = getattr(self.failed_intent, 'target_position', None)
        if target_pos and not self.agent.grid.is_walkable(int(target_pos.x), int(target_pos.y)):
            self.agent.logger.info(f"Agent {self.agent.id} PathFailed: Target {target_pos} is unwalkable. Searching for a new target.")
            new_target = find_closest_walkable_tile(
                target_pos,
                self.agent.config.PATHFINDING_NEW_TARGET_SEARCH_RADIUS,
                self.agent.grid
            )
            if new_target:
                self.agent.logger.info(f"Agent {self.agent.id} PathFailed: Found new walkable target at {new_target}. Updating intent and transitioning to MovingBehavior.")
                self.failed_intent.target_position = new_target # type: ignore
                # Immediately try to move to the new target
                self.agent._transition_behavior(MovingBehavior, self.failed_intent)
                return # Exit enter() as we've already transitioned

        # Strategy 2: If target is walkable or no new target was found, set up for retry.
        self.agent.logger.info(f"Agent {self.agent.id} PathFailed: Setting up for retry logic.")
        self.retry_timer = self.agent.config.PATHFINDING_RETRY_DELAY


    def update(self, dt: float, resource_manager: 'ResourceManager') -> Optional[IntentStatus]:
        if not self.failed_intent:
            return IntentStatus.FAILED # Should have been caught in enter, but as a safeguard.

        if self.retry_timer > 0:
            self.retry_timer -= dt
            return None # Waiting for the timer to expire

        # Timer has expired, let's try to repath
        if self.retry_count < self.agent.config.PATHFINDING_MAX_RETRIES:
            self.retry_count += 1
            self.agent.logger.info(f"Agent {self.agent.id} PathFailed: Attempting retry {self.retry_count}/{self.agent.config.PATHFINDING_MAX_RETRIES} for intent {self.failed_intent.intent_id}.")

            # Attempt to find a path again
            path = self.agent.grid.find_path(self.agent.position, self.failed_intent.target_position) # type: ignore

            if path:
                self.agent.logger.info(f"Agent {self.agent.id} PathFailed: Retry successful. Path found. Transitioning to MovingBehavior.")
                self.agent.current_path = path
                self.agent.target_position = path[-1] if path else None
                self.agent._transition_behavior(MovingBehavior, self.failed_intent)
                return None # Behavior is done, new one is queued
            else:
                self.agent.logger.warning(f"Agent {self.agent.id} PathFailed: Retry {self.retry_count} failed. Resetting timer.")
                self.retry_timer = self.agent.config.PATHFINDING_RETRY_DELAY # Reset timer for next attempt
                return None
        else:
            # Strategy 3: Give up
            self.agent.logger.error(f"Agent {self.agent.id} PathFailed: All retries failed for intent {self.failed_intent.intent_id}. Marking as FAILED.")
            self.failed_intent.error_message = "Pathfinding failed after multiple retries."
            return IntentStatus.FAILED

    def exit(self):
        self.agent.logger.debug(f"Agent {self.agent.id} exiting PathFailedBehavior.")
        self.failed_intent = None
        self.retry_count = 0
        self.retry_timer = 0.0

class EvaluatingIntentBehavior(AgentBehavior):
    """Behavior for when the agent is evaluating its current intent or needs to fetch a new one."""
    def enter(self, intent: Optional[Intent] = None):
        self.agent.logger.debug(f"Agent {self.agent.id} entering EvaluatingIntentBehavior.")
        # This behavior is more of a transient state for the agent's internal logic
        # to decide the next concrete action behavior based on the current_intent.

    def update(self, dt: float, resource_manager: 'ResourceManager') -> Optional[IntentStatus]:
        self.agent.logger.debug(f"Agent {self.agent.id} EvaluatingIntentBehavior: Update called.")
        if self.agent.current_intent and self.agent.current_intent.status == IntentStatus.PENDING:
            self.agent.logger.debug(f"Agent {self.agent.id} EvaluatingIntentBehavior: Found PENDING intent {self.agent.current_intent.intent_id}. Calling _process_current_intent.")
            self.agent._process_current_intent() # Agent transitions to another behavior
        elif not self.agent.current_intent:
            self.agent.logger.debug(f"Agent {self.agent.id} EvaluatingIntentBehavior: No current intent. Calling acquire_task_or_perform_idle_action.")
            # This call might result in a new intent being submitted, which will be processed in the next cycle
            # or by an immediate transition if acquire_task_or_perform_idle_action itself calls submit_intent and _process_current_intent.
            # For now, assume it might submit an intent that becomes PENDING.
            self.agent.acquire_task_or_perform_idle_action(dt, resource_manager)
        else:
            # Intent exists but is not PENDING (e.g., ACTIVE, COMPLETED, FAILED).
            # This behavior's job is done for such intents; agent's main loop handles outcomes.
            # Or, if an intent was just completed/failed, agent should have transitioned here,
            # and current_intent might have been cleared or replaced.
            self.agent.logger.debug(f"Agent {self.agent.id} EvaluatingIntentBehavior: current_intent exists but not PENDING (Status: {self.agent.current_intent.status.name}). No action by behavior.")

        return None # This behavior itself doesn't complete an intent; it facilitates processing or acquisition.

    def exit(self):
        self.agent.logger.debug(f"Agent {self.agent.id} exiting EvaluatingIntentBehavior.")