from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

from .intents import Intent, IntentStatus # Assuming intents.py is in the same directory

if TYPE_CHECKING:
    from .agent import Agent # To avoid circular import, for type hinting only
    # from ..core.grid import Grid # If behaviors interact directly with grid
    # from ..resources.manager import ResourceManager # If behaviors interact directly

class AgentBehavior(ABC):
    """Abstract base class for all agent behaviors (states in the State Pattern)."""

    def __init__(self, agent: 'Agent'):
        self.agent = agent

    @abstractmethod
    def enter(self, intent: Optional[Intent] = None):
        """Called when the agent enters this behavior/state."""
        pass

    @abstractmethod
    def update(self, dt: float) -> Optional[IntentStatus]:
        """
        Called every frame to update the behavior.
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


    def update(self, dt: float) -> Optional[IntentStatus]:
        # In IdleBehavior, the agent might decide to look for tasks (which would be an intent itself)
        # or process a new intent if one is assigned.
        # For now, IdleBehavior itself doesn't complete an "intent".
        # The Agent's main loop will handle transitioning from Idle if a new intent arrives.
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
        if intent and hasattr(intent, 'target_position'):
            self.move_intent = intent
            self.agent.set_target(intent.target_position) # type: ignore
            if self.agent.current_path is None:
                self.agent.logger.warning(f"Agent {self.agent.id} MovingBehavior: Pathfinding failed for intent {intent.intent_id} to {intent.target_position}.") # type: ignore
                # This state should immediately signal failure for this intent.
            else:
                self.agent.logger.debug(f"Agent {self.agent.id} MovingBehavior: Path set for intent {intent.intent_id} to {intent.target_position}.") # type: ignore
        else:
            self.agent.logger.error(f"Agent {self.agent.id} MovingBehavior: Entered without a valid MoveIntent or target_position.")
            # This is an error condition, should probably lead to intent failure.
            self.move_intent = None


    def update(self, dt: float) -> Optional[IntentStatus]:
        if not self.agent.current_path and not self.agent.target_position:
            # Pathfinding might have failed in enter(), or path was unexpectedly cleared.
            # If agent is already at the final destination of the intent, it's a success.
            if self.move_intent and hasattr(self.move_intent, 'target_position'):
                target_pos = getattr(self.move_intent, 'target_position')
                if self.agent.position.distance_to(target_pos) < self.agent.target_tolerance:
                    self.agent.logger.debug(f"Agent {self.agent.id} MovingBehavior: Already at target {target_pos} for intent {self.move_intent.intent_id}. Path completed.")
                    return IntentStatus.COMPLETED
            
            self.agent.logger.warning(f"Agent {self.agent.id} MovingBehavior: No path and not at target. Intent {self.move_intent.intent_id if self.move_intent else 'None'} failed.")
            return IntentStatus.FAILED

        path_follow_result = self.agent._follow_path(dt) # _follow_path returns True if waypoint reached or path ended

        if path_follow_result: # Waypoint reached
            if not self.agent.current_path: # Path is now empty, meaning final destination reached
                self.agent.logger.debug(f"Agent {self.agent.id} MovingBehavior: Path completed for intent {self.move_intent.intent_id if self.move_intent else 'None'}.")
                return IntentStatus.COMPLETED
        
        # If path_follow_result is False, it means still moving towards current waypoint.
        # If current_path exists but target_position is None (should not happen if _follow_path is robust)
        if self.agent.current_path and self.agent.target_position is None:
            self.agent.logger.error(f"Agent {self.agent.id} MovingBehavior: current_path exists but target_position is None. Critical error.")
            return IntentStatus.FAILED
            
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

    def update(self, dt: float) -> Optional[IntentStatus]:
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
    """Behavior for when the agent fails to find a path."""
    def enter(self, intent: Optional[Intent] = None):
        self.agent.logger.warning(f"Agent {self.agent.id} entering PathFailedBehavior for intent {intent.intent_id if intent else 'Unknown'}.")
        # Potentially log the failed intent details
        if intent:
            intent.error_message = "Pathfinding failed."
            # The agent itself might have a cooldown or retry logic here,
            # but for now, this behavior just signals the intent has failed.

    def update(self, dt: float) -> Optional[IntentStatus]:
        # This state immediately signals the failure of the intent that led to it.
        # The agent's IntentProcessor would then decide what to do next (e.g., go idle, try alternative).
        return IntentStatus.FAILED

    def exit(self):
        self.agent.logger.debug(f"Agent {self.agent.id} exiting PathFailedBehavior.")

class EvaluatingIntentBehavior(AgentBehavior):
    """Behavior for when the agent is evaluating its current intent or needs to fetch a new one."""
    def enter(self, intent: Optional[Intent] = None):
        self.agent.logger.debug(f"Agent {self.agent.id} entering EvaluatingIntentBehavior.")
        # This behavior is more of a transient state for the agent's internal logic
        # to decide the next concrete action behavior based on the current_intent.

    def update(self, dt: float) -> Optional[IntentStatus]:
        # The actual logic for evaluating/dispatching intents will reside in the Agent class.
        # This behavior might not directly complete an intent itself but trigger
        # the agent to transition to another behavior (e.g., MovingBehavior if intent is MoveIntent).
        # If there's no current intent, it might trigger looking for new tasks.
        # For now, let's assume the agent's main update loop handles this transition.
        # This behavior itself doesn't have a "completion" status for an intent.
        self.agent.logger.debug(f"Agent {self.agent.id} EvaluatingIntentBehavior: Update called. Agent should process its current_intent.")
        return None # Agent's main logic will transition out of this.

    def exit(self):
        self.agent.logger.debug(f"Agent {self.agent.id} exiting EvaluatingIntentBehavior.")