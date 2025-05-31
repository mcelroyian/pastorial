from enum import Enum, auto

class AgentState(Enum):
    """Defines the possible states an agent can be in. Tasks will set these."""
    IDLE = auto()
    MOVING_RANDOMLY = auto()
    MOVING_TO_RESOURCE = auto()
    GATHERING_RESOURCE = auto()
    MOVING_TO_STORAGE = auto()
    DELIVERING_RESOURCE = auto()
    MOVING_TO_PROCESSOR = auto()
    DELIVERING_TO_PROCESSOR = auto()
    COLLECTING_FROM_PROCESSOR = auto()
    EVALUATING_TASKS = auto() # New state for job board interaction