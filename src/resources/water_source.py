import pygame
from .node import ResourceNode
from src.core import config
from ..resources.resource_types import ResourceType

class WaterSource(ResourceNode):
    """
    Represents a Water Source (Well) resource node in the simulation.
    """
    def __init__(self, grid_position: pygame.Vector2):
        """
        Initializes a WaterSource node.

        Args:
            grid_position: The grid coordinates of the well (pygame.Vector2).
        """
        super().__init__(
            position=grid_position,
            capacity=config.WELL_CAPACITY,
            generation_interval=config.WELL_GENERATION_INTERVAL,
            resource_type=ResourceType.WATER
        )
        self.display_size = config.GRID_CELL_SIZE

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, grid):
        """
        Draws the well and its current resource count.

        Args:
            surface: The pygame surface to draw on.
            font: The pygame font to use for rendering the resource count.
            grid: The game grid object for coordinate conversions.
        """
        screen_pos = grid.grid_to_screen(self.position)

        draw_rect = pygame.Rect(
            screen_pos[0] - self.display_size / 2,
            screen_pos[1] - self.display_size / 2,
            self.display_size,
            self.display_size
        )

        pygame.draw.rect(surface, config.RESOURCE_VISUAL_COLORS.get(self.resource_type, (0, 0, 255)), draw_rect)

        resource_text = f"{int(self.current_quantity)}"
        text_surface = font.render(resource_text, True, config.RESOURCE_TEXT_COLOR)
        text_rect = text_surface.get_rect(center=screen_pos)
        surface.blit(text_surface, text_rect)