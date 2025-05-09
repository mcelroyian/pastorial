import pygame
from .node import ResourceNode
from ..resources.resource_types import ResourceType
from ..core import config

class WheatField(ResourceNode):
    """
    A resource node that generates Wheat.
    """
    GENERATION_TICKS_PER_UNIT = 5 # How many simulation ticks to generate 1 unit of wheat

    def __init__(self, position: pygame.Vector2):
        """
        Initializes a WheatField.

        Args:
            position: The position of the field on the grid (pygame.Vector2).
        """
        # Calculate generation_rate in resources per second
        # ResourceNode expects generation_rate in units per second.
        # The game simulation runs at config.TARGET_FPS ticks per second.
        # We want 1 unit per GENERATION_TICKS_PER_UNIT simulation ticks.
        # So, rate = (1 unit / GENERATION_TICKS_PER_UNIT ticks) * (config.TARGET_FPS ticks / 1 second)
        # rate = config.TARGET_FPS / GENERATION_TICKS_PER_UNIT units/second
        generation_rate_per_second = config.TARGET_FPS / self.GENERATION_TICKS_PER_UNIT

        super().__init__(
            position=position,
            capacity=50, # As per SLICE_3.1_PLAN.md
            generation_rate=generation_rate_per_second,
            resource_type=ResourceType.WHEAT
        )
        self.color = config.RESOURCE_VISUAL_COLORS.get(self.resource_type, (255, 255, 0)) # Default yellow if not in config

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, grid): # Added grid parameter
        """
        Draws the wheat field on the given surface.

        Args:
            surface: The pygame surface to draw on.
            font: The pygame font to use for rendering text.
            grid: The game grid object (unused in this implementation but part of the required signature).
        """
        # The 'grid' parameter is not used here as drawing is based on
        # self.position and config.GRID_CELL_SIZE.
        rect_x = self.position.x * config.GRID_CELL_SIZE
        rect_y = self.position.y * config.GRID_CELL_SIZE
        node_rect = pygame.Rect(rect_x, rect_y, config.GRID_CELL_SIZE, config.GRID_CELL_SIZE)

        pygame.draw.rect(surface, self.color, node_rect)

        # Draw resource count
        resource_text = f"{int(self.current_quantity)}"
        text_surface = font.render(resource_text, True, config.RESOURCE_TEXT_COLOR)
        text_rect = text_surface.get_rect(center=node_rect.center)
        surface.blit(text_surface, text_rect)

    def __str__(self):
        return f"WheatField at {self.position} ({self.current_quantity:.1f}/{self.capacity} {self.resource_type.name})"

    def __repr__(self):
        return f"WheatField(position={self.position})"