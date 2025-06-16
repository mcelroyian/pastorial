from dataclasses import dataclass, field
from typing import Dict

@dataclass
class Recipe:
    """
    Represents a recipe for a processing station.

    Attributes:
        inputs: A dictionary mapping resource types to the quantities required.
        outputs: A dictionary mapping resource types to the quantities produced.
    """
    inputs: Dict[str, int] = field(default_factory=dict)
    outputs: Dict[str, int] = field(default_factory=dict)