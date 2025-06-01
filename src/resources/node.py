import pygame
import uuid # For task and agent IDs
import logging # Added
from typing import Optional # For Optional type hints
from abc import ABC, abstractmethod
from ..resources.resource_types import ResourceType # Import ResourceType

class ResourceNode(ABC):
    """
    Base class for resource nodes in the simulation.
    """
    def __init__(self, position: pygame.Vector2, capacity: int, generation_interval: float, resource_type: ResourceType):
        """
        Initializes a ResourceNode.

        Args:
            position: The position of the node on the grid (pygame.Vector2).
            capacity: The maximum amount of resources the node can hold (integer units).
            generation_interval: The interval at which resources are generated (in seconds).
            resource_type: The type of resource this node provides.
        """
        self.logger = logging.getLogger(__name__) # Added
        if not isinstance(position, pygame.Vector2):
            self.logger.critical("Position must be a pygame.Vector2") # Added
            raise TypeError("Position must be a pygame.Vector2")
        self.position = position
        self.id: uuid.UUID = uuid.uuid4()
        self.capacity = int(capacity) # Ensure capacity is integer
        self.generation_interval = generation_interval
        self.resource_type = resource_type # Added
        self.current_quantity = 0
        self._generation_timer = 0.0
        
        # --- Attributes for task-based claiming ---
        self.claimed_by_task_id: Optional[uuid.UUID] = None
        self.claimed_by_agent_id: Optional[uuid.UUID] = None

    def update(self, dt: float):
        """
        Updates the resource node's state, generating resources over time.

        Args:
            dt: The time elapsed since the last update in seconds.
        """
        if self.current_quantity < self.capacity:
            self._generation_timer += dt
            resources_to_add = int(self._generation_timer / self.generation_interval)
            if resources_to_add > 0:
                self._generation_timer -= resources_to_add * self.generation_interval
                # Don't overfill
                resources_needed = self.capacity - self.current_quantity
                actual_to_add = min(resources_to_add, resources_needed)
                self.current_quantity += actual_to_add
                if actual_to_add > 0:
                    self.logger.debug(f"Node {self.id} at {self.position} ({self.resource_type.name}) regenerated {actual_to_add}. New quantity: {self.current_quantity}/{self.capacity}")

    # --- Methods for task-based claiming ---
    def claim(self, agent_id: uuid.UUID, task_id: uuid.UUID) -> bool:
        """
        Attempts to claim this resource node for a specific task and agent.
        Returns True if successful (node was not already claimed), False otherwise.
        """
        if self.claimed_by_task_id is None:
            self.claimed_by_task_id = task_id
            self.claimed_by_agent_id = agent_id
            self.logger.debug(f"Node {self.position} claimed by task {task_id} for agent {agent_id}.") # Changed
            return True
        self.logger.debug(f"Node {self.position} FAILED to claim by task {task_id} (already claimed by task {self.claimed_by_task_id}).") # Changed
        return False

    def release(self, agent_id: uuid.UUID, task_id: uuid.UUID):
        """
        Releases the claim on this resource node if the provided task_id matches the current claim.
        """
        if self.claimed_by_task_id == task_id:
            # Optional: could also check agent_id for stricter release conditions
            # if self.claimed_by_agent_id == agent_id:
            self.claimed_by_task_id = None
            self.claimed_by_agent_id = None
            self.logger.debug(f"Node {self.position} released by task {task_id} from agent {agent_id}.") # Changed
        else:
            self.logger.debug(f"Node {self.position} release called by task {task_id} but was claimed by {self.claimed_by_task_id} (or not claimed).") # Changed

    @abstractmethod
    def draw(self, surface: pygame.Surface, font: pygame.font.Font, grid): # Added grid
        """
        Draws the resource node on the given surface.
        This method must be implemented by subclasses.

        Args:
            surface: The pygame surface to draw on.
            font: The pygame font to use for rendering text.
            grid: The game grid object, potentially for coordinate transformations or cell information.
        """
        pass

    def collect_resource(self, amount_to_collect: int) -> int:
        """
        Attempts to collect a specified integer amount of resources from the node.

        Args:
            amount_to_collect: The integer amount of resources to attempt to collect.

        Returns:
            The actual integer amount of resources collected (can be less than requested).
        """
        
        collectable_amount = min(amount_to_collect, self.current_quantity)
        
        if collectable_amount > 0:
            self.current_quantity -= collectable_amount
            # Ensure resources don't go below zero (shouldn't happen with min logic)
            self.current_quantity = max(0.0, self.current_quantity)
            self.logger.debug(f"Node at {self.position} ({self.resource_type.name}) collected {collectable_amount}, remaining: {self.current_quantity:.2f}") # Changed
        return collectable_amount