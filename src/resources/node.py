import pygame
from abc import ABC, abstractmethod
from ..resources.resource_types import ResourceType # Import ResourceType

class ResourceNode(ABC):
    """
    Base class for resource nodes in the simulation.
    """
    def __init__(self, position: pygame.Vector2, capacity: int, generation_rate: float, resource_type: ResourceType):
        """
        Initializes a ResourceNode.

        Args:
            position: The position of the node on the grid (pygame.Vector2).
            capacity: The maximum amount of resources the node can hold (integer units).
            generation_rate: The rate at which resources are generated per second (can be fractional).
            resource_type: The type of resource this node provides.
        """
        if not isinstance(position, pygame.Vector2):
            raise TypeError("Position must be a pygame.Vector2")
        self.position = position
        self.capacity = int(capacity) # Ensure capacity is integer
        self.generation_rate = generation_rate
        self.resource_type = resource_type # Added
        self.current_quantity = 0.0  # Start with zero resources, will be float due to generation_rate
                                      # Collection will deal with integer parts.

    def update(self, dt: float):
        """
        Updates the resource node's state, generating resources over time.

        Args:
            dt: The time elapsed since the last update in seconds.
        """
        if self.current_quantity < self.capacity:
            self.current_quantity += self.generation_rate * dt
            # Clamp the resources to the capacity
            self.current_quantity = min(self.current_quantity, float(self.capacity))

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
        # Agents collect discrete units, so we work with the integer part of current_quantity
        available_integer_quantity = int(self.current_quantity)
        
        collectable_amount = min(amount_to_collect, available_integer_quantity)
        
        if collectable_amount > 0:
            self.current_quantity -= float(collectable_amount)
            # Ensure resources don't go below zero (shouldn't happen with min logic)
            self.current_quantity = max(0.0, self.current_quantity)
            print(f"Node at {self.position} ({self.resource_type.name}) collected {collectable_amount}, remaining: {self.current_quantity:.2f}") # Debug
        return collectable_amount