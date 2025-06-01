from enum import Enum, auto
from abc import ABC, abstractmethod
import uuid
from typing import Optional, Any
import pygame # For Vector2

class IntentStatus(Enum):
    """Defines the possible statuses of an Intent."""
    PENDING = auto()    # The intent has been created but not yet started by the agent.
    ACTIVE = auto()     # The agent is currently working on this intent.
    COMPLETED = auto()  # The agent has successfully completed the intent.
    FAILED = auto()     # The agent failed to complete the intent.
    CANCELLED = auto()  # The intent was cancelled before completion.

class Intent(ABC):
    """
    Abstract base class for all intents that an agent can process.
    An intent represents a high-level goal or action for the agent.
    """
    def __init__(self):
        self.intent_id: uuid.UUID = uuid.uuid4()
        self.status: IntentStatus = IntentStatus.PENDING
        self.error_message: Optional[str] = None

    @abstractmethod
    def get_description(self) -> str:
        """Returns a human-readable description of the intent."""
        pass

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.intent_id}, Status: {self.status.name})"

# --- Concrete Intent Types will be added below ---

class MoveIntent(Intent):
    """Intent for an agent to move to a specific target position."""
    def __init__(self, target_position: pygame.math.Vector2):
        super().__init__()
        self.target_position: pygame.math.Vector2 = target_position

    def get_description(self) -> str:
        return f"Move to {self.target_position}"

class GatherIntent(Intent):
    """Intent for an agent to gather a resource from a target node."""
    def __init__(self, resource_node_id: uuid.UUID, resource_type: Any, quantity_to_gather: int): # Using Any for ResourceType for now
        super().__init__()
        self.resource_node_id: uuid.UUID = resource_node_id
        self.resource_type: Any = resource_type # TODO: Replace Any with actual ResourceType
        self.quantity_to_gather: int = quantity_to_gather
        self.quantity_gathered: int = 0

    def get_description(self) -> str:
        return f"Gather {self.quantity_to_gather} of {self.resource_type} from node {self.resource_node_id}"

class DeliverIntent(Intent):
    """Intent for an agent to deliver a resource to a target dropoff."""
    def __init__(self, dropoff_id: uuid.UUID, resource_type: Any, quantity_to_deliver: int): # Using Any for ResourceType
        super().__init__()
        self.dropoff_id: uuid.UUID = dropoff_id
        self.resource_type: Any = resource_type # TODO: Replace Any with actual ResourceType
        self.quantity_to_deliver: int = quantity_to_deliver
        self.quantity_delivered: int = 0

    def get_description(self) -> str:
        return f"Deliver {self.quantity_to_deliver} of {self.resource_type} to dropoff {self.dropoff_id}"

class InteractAtTargetIntent(Intent):
    """A more generic intent to interact at a target, could be for timers or specific actions."""
    def __init__(self, target_id: uuid.UUID, interaction_type: str, duration: float = 0.0):
        super().__init__()
        self.target_id: uuid.UUID = target_id # ID of the entity to interact with
        self.interaction_type: str = interaction_type # e.g., "GATHER_TIMER", "DELIVER_TIMER"
        self.duration: float = duration # If the interaction is time-based

    def get_description(self) -> str:
        return f"Interact ({self.interaction_type}, {self.duration}s) at target {self.target_id}"

# Example of a more complex intent that might be broken down by the agent or task
class GatherAndDeliverFullLoadIntent(Intent):
    """
    Intent for an agent to gather a full load of a resource and deliver it.
    This is a higher-level intent that the agent might break down into
    Move, Gather, Move, Deliver sub-intents internally, or the task
    might submit these sequentially. For now, let's assume the task
    would submit the finer-grained intents.
    """
    def __init__(self, resource_node_id: uuid.UUID, resource_type: Any, dropoff_id: uuid.UUID):
        super().__init__()
        self.resource_node_id: uuid.UUID = resource_node_id
        self.resource_type: Any = resource_type
        self.dropoff_id: uuid.UUID = dropoff_id

    def get_description(self) -> str:
        return f"Gather full load of {self.resource_type} from {self.resource_node_id} and deliver to {self.dropoff_id}"