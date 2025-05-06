from enum import Enum, auto

class ResourceType(Enum):
    """Defines the types of resources available in the simulation."""
    BERRY = auto()
    WHEAT = auto()
    # Future resource types can be added here
    # e.g., WATER = auto(), FLOUR = auto(), BREAD = auto()