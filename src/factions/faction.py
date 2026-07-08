import uuid
from dataclasses import dataclass, field
from typing import List, Tuple, TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from src.tasks.task_manager import TaskManager


@dataclass
class Faction:
    faction_id: int
    name: str
    color: Tuple[int, int, int]
    home_region: pygame.Rect  # grid-coord bounding box
    task_manager: 'TaskManager'
    agent_ids: List[uuid.UUID] = field(default_factory=list)
    building_ids: List[uuid.UUID] = field(default_factory=list)
