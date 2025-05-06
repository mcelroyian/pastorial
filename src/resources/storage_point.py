import pygame
from typing import List, Dict, Optional

# Assuming ResourceType is defined in resource_types.py
from .resource_types import ResourceType

class StoragePoint:
    """Represents a location where agents can drop off collected resources."""

    def __init__(self,
                 position: pygame.math.Vector2,
                 overall_capacity: int,
                 accepted_resource_types: Optional[List[ResourceType]] = None):
        """
        Initializes a StoragePoint.

        Args:
            position (pygame.math.Vector2): The grid coordinates of the storage point.
            overall_capacity (int): The maximum total quantity of all resources this point can hold.
            accepted_resource_types (Optional[List[ResourceType]]): A list of resource types
                                     this storage point accepts. If None, accepts all types.
        """
        self.position = position
        self.overall_capacity = overall_capacity
        self.accepted_resource_types = accepted_resource_types
        self.stored_resources: Dict[ResourceType, int] = {}

    def get_current_load(self) -> int:
        """Returns the total quantity of all resources currently stored."""
        return sum(self.stored_resources.values())

    def can_accept(self, resource_type: ResourceType, quantity: int) -> bool:
        """Checks if the storage point can accept a given quantity of a resource type."""
        if self.accepted_resource_types is not None and resource_type not in self.accepted_resource_types:
            return False
        if self.get_current_load() + quantity > self.overall_capacity:
            return False
        return True

    def add_resource(self, resource_type: ResourceType, quantity: int) -> int:
        """
        Adds a quantity of a specific resource type to the storage.

        Args:
            resource_type (ResourceType): The type of resource to add.
            quantity (int): The amount of resource to add.

        Returns:
            int: The actual quantity of the resource added (might be less than requested
                 if capacity is exceeded or type not accepted).
        """
        if not self.can_accept(resource_type, quantity):
            # If it cannot accept the full quantity, try to accept as much as possible
            if self.accepted_resource_types is not None and resource_type not in self.accepted_resource_types:
                return 0 # Cannot accept this type at all

            available_capacity = self.overall_capacity - self.get_current_load()
            quantity_to_add = min(quantity, available_capacity)

            if quantity_to_add <= 0:
                return 0
        else:
            quantity_to_add = quantity

        current_amount = self.stored_resources.get(resource_type, 0)
        self.stored_resources[resource_type] = current_amount + quantity_to_add
        print(f"Storage at {self.position} received {quantity_to_add} of {resource_type.name}. Total: {self.stored_resources}") # Debug
        return quantity_to_add

    def draw(self, screen: pygame.Surface, grid):
        """Draws the storage point on the screen (placeholder)."""
        screen_pos = grid.grid_to_screen(self.position)
        color = (128, 128, 128) # Grey for storage
        radius = grid.cell_width // 2
        pygame.draw.rect(screen, color, (screen_pos.x - radius, screen_pos.y - radius, grid.cell_width, grid.cell_height))
        # Optionally, draw stored resource counts or indicators