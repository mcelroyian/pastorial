import pygame
from abc import ABC, abstractmethod

class ResourceNode(ABC):
    """
    Base class for resource nodes in the simulation.
    """
    def __init__(self, position: pygame.Vector2, capacity: int, generation_rate: float):
        """
        Initializes a ResourceNode.

        Args:
            position: The position of the node on the grid (pygame.Vector2).
            capacity: The maximum amount of resources the node can hold.
            generation_rate: The rate at which resources are generated per second.
        """
        if not isinstance(position, pygame.Vector2):
            raise TypeError("Position must be a pygame.Vector2")
        self.position = position
        self.capacity = capacity
        self.generation_rate = generation_rate
        self.current_resources = 0.0  # Start with zero resources

    def update(self, dt: float):
        """
        Updates the resource node's state, generating resources over time.

        Args:
            dt: The time elapsed since the last update in seconds.
        """
        if self.current_resources < self.capacity:
            self.current_resources += self.generation_rate * dt
            # Clamp the resources to the capacity
            self.current_resources = min(self.current_resources, self.capacity)

    @abstractmethod
    def draw(self, surface: pygame.Surface, font: pygame.font.Font):
        """
        Draws the resource node on the given surface.
        This method must be implemented by subclasses.

        Args:
            surface: The pygame surface to draw on.
            font: The pygame font to use for rendering text.
        """
        pass

    def collect(self, amount: float) -> float:
        """
        Attempts to collect a specified amount of resources from the node.

        Args:
            amount: The amount of resources to attempt to collect.

        Returns:
            The actual amount of resources collected (can be less than requested).
        """
        collectable_amount = min(amount, self.current_resources)
        self.current_resources -= collectable_amount
        # Ensure resources don't go below zero (shouldn't happen with min)
        self.current_resources = max(0.0, self.current_resources)
        return collectable_amount