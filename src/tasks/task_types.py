from enum import Enum, auto

class TaskType(Enum):
    """Defines the types of tasks an agent can perform."""
    GATHER_AND_DELIVER = auto()
    PROCESS_RESOURCE = auto()
    COLLECT_PROCESSED_AND_DELIVER = auto()
    PATROL = auto()
    EAT = auto()

class TaskStatus(Enum):
    """Defines the possible states of a task."""
    PENDING = auto()
    ASSIGNED = auto()
    PREPARING = auto()
    IN_PROGRESS = auto()
    # Legacy granular statuses — kept for compatibility; unused by step-based tasks (Task 4 removes them)
    IN_PROGRESS_MOVE_TO_RESOURCE = auto()
    IN_PROGRESS_GATHERING = auto()
    IN_PROGRESS_MOVE_TO_DROPOFF = auto()
    IN_PROGRESS_DELIVERING = auto()
    IN_PROGRESS_MOVE_TO_STORAGE = auto()
    IN_PROGRESS_COLLECTING_FROM_STORAGE = auto()
    IN_PROGRESS_MOVE_TO_PROCESSOR = auto()
    IN_PROGRESS_DELIVERING_TO_PROCESSOR = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()