import pygame
from typing import List
from .node import ResourceNode # Use relative import within the package

class ResourceManager:
    """
    Manages all resource nodes in the simulation.
    """
    def __init__(self):
        """
        Initializes the ResourceManager with an empty list of nodes.
        """
        self.nodes: List[ResourceNode] = []

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