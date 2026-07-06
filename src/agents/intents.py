from enum import Enum, auto
from abc import ABC, abstractmethod
import uuid
from typing import Optional
import pygame

class IntentStatus(Enum):
    PENDING = auto()
    ACTIVE = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()

class Intent(ABC):
    def __init__(self, task_id: Optional[uuid.UUID] = None):
        self.intent_id: uuid.UUID = uuid.uuid4()
        self.status: IntentStatus = IntentStatus.PENDING
        self.error_message: Optional[str] = None
        self.originating_task_id: Optional[uuid.UUID] = task_id

    @abstractmethod
    def get_description(self) -> str:
        pass

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.intent_id}, Status: {self.status.name})"


class MoveIntent(Intent):
    def __init__(self, target_position: pygame.math.Vector2, task_id: Optional[uuid.UUID] = None):
        super().__init__(task_id)
        self.target_position: pygame.math.Vector2 = target_position

    def get_description(self) -> str:
        return f"Move to {self.target_position}"


class InteractAtTargetIntent(Intent):
    def __init__(self, target_id: uuid.UUID, interaction_type: str, duration: float = 0.0, task_id: Optional[uuid.UUID] = None):
        super().__init__(task_id)
        self.target_id: uuid.UUID = target_id
        self.interaction_type: str = interaction_type
        self.duration: float = duration

    def get_description(self) -> str:
        return f"Interact ({self.interaction_type}, {self.duration}s) at target {self.target_id}"


class RandomMoveIntent(Intent):
    def __init__(self, task_id: Optional[uuid.UUID] = None):
        super().__init__(task_id)

    def get_description(self) -> str:
        return "Move to a random location"
