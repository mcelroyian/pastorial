import pygame
from typing import List, TYPE_CHECKING
from .node import ResourceNode # Use relative import within the package
from .resource_types import ResourceType # For get_nodes_by_type
# Forward reference for StoragePoint to avoid circular import if StoragePoint imports ResourceManager
if TYPE_CHECKING:
    from .storage_point import StoragePoint

class ResourceManager:
    """
    Manages all resource nodes in the simulation.
    """
    def __init__(self):
        """
        Initializes the ResourceManager with an empty list of nodes.
        """
        self.nodes: List[ResourceNode] = []
        self.storage_points: List['StoragePoint'] = [] # Initialize storage_points list

    def add_node(self, node: ResourceNode):
        """
        Adds a resource node to the manager.

        Args:
            node: The ResourceNode instance to add.
        """
        if isinstance(node, ResourceNode):
            self.nodes.append(node)
        else:
            # Simple error handling, could be more robust (e.g., logging)
            print(f"Error: Attempted to add non-ResourceNode object to ResourceManager: {node}")

    def add_storage_point(self, storage_point: 'StoragePoint'):
        """
        Adds a storage point to the manager.

        Args:
            storage_point: The StoragePoint instance to add.
        """
        # Can add type checking if StoragePoint is directly imported
        # from .storage_point import StoragePoint
        # if isinstance(storage_point, StoragePoint):
        self.storage_points.append(storage_point)
        # else:
        #     print(f"Error: Attempted to add non-StoragePoint object to ResourceManager: {storage_point}")

    def get_nodes_by_type(self, resource_type: ResourceType) -> List[ResourceNode]:
        """
        Returns a list of resource nodes of a specific type.
        """
        return [node for node in self.nodes if hasattr(node, 'resource_type') and node.resource_type == resource_type]

    def update_nodes(self, dt: float):
        """
        Updates all managed resource nodes.

        Args:
            dt: The time elapsed since the last update in seconds.
        """
        for node in self.nodes:
            node.update(dt)

    def draw_nodes(self, surface: pygame.Surface, font: pygame.font.Font):
        """
        Draws all managed resource nodes.

        Args:
            surface: The pygame surface to draw on.
            font: The pygame font to use for rendering text on nodes.
        """
        for node in self.nodes:
            node.draw(surface, font)
        # Optionally, draw storage points too
        # for sp in self.storage_points:
        #     if hasattr(sp, 'draw'): # Check if storage_point has a draw method
        #         sp.draw(surface, self.grid) # Assuming storage_point.draw takes screen and grid