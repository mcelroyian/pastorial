from enum import Enum, auto

class TaskType(Enum):
    """Defines the types of tasks an agent can perform."""
    GATHER_AND_DELIVER = auto()
    PROCESS_RESOURCE = auto() # Example for future expansion
    COLLECT_PROCESSED_AND_DELIVER = auto() # Example for future expansion
    # Add other task types as needed

class TaskStatus(Enum):
    """Defines the possible states of a task."""
    PENDING = auto()    # Task is created but not yet assigned or prepared
    ASSIGNED = auto()   # Task is assigned to an agent, but not yet prepared
    PREPARING = auto()  # Task is actively trying to claim resources/reserve space
    # IN_PROGRESS states indicate the agent is actively working on a phase of the task
    IN_PROGRESS_MOVE_TO_RESOURCE = auto()
    IN_PROGRESS_GATHERING = auto()
    IN_PROGRESS_MOVE_TO_DROPOFF = auto()
    IN_PROGRESS_DELIVERING = auto()
    IN_PROGRESS_MOVE_TO_STORAGE = auto() # For moving to a storage point to collect
    IN_PROGRESS_COLLECTING_FROM_STORAGE = auto() # For collecting from a storage point
    IN_PROGRESS_MOVE_TO_PROCESSOR = auto() # For moving to a processing station
    IN_PROGRESS_DELIVERING_TO_PROCESSOR = auto() # For delivering to a processing station
    # Add other IN_PROGRESS states for more complex tasks (e.g., IN_PROGRESS_PROCESSING)
    COMPLETED = auto()  # Task was successfully finished
    FAILED = auto()     # Task could not be completed
    CANCELLED = auto()  # Task was cancelled before completion