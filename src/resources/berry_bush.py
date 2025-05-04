import pygame
from .node import ResourceNode
from src.core import config # Assuming config will have the necessary variables

class BerryBush(ResourceNode):
    """
    Represents a Berry Bush resource node in the simulation.
    """
    def __init__(self, position: pygame.Vector2):
        """
        Initializes a BerryBush node.

        Args:
            position: The position of the bush on the grid (pygame.Vector2).
        """
        # Use configuration values for capacity and generation rate
        super().__init__(
            position=position,
            capacity=config.BERRY_BUSH_CAPACITY,
            generation_rate=config.BERRY_BUSH_GENERATION_RATE
        )
        # Define the size of the bush representation (e.g., match grid cell size)
        # We might want this in config too, but using GRID_CELL_SIZE for now
        self.size = config.GRID_CELL_SIZE
        self.rect = pygame.Rect(
            self.position.x - self.size / 2,
            self.position.y - self.size / 2,
            self.size,
            self.size
        )
        # Center the rect on the position if position is meant to be the center
        self.rect.center = (int(self.position.x), int(self.position.y))


    def draw(self, surface: pygame.Surface, font: pygame.font.Font):
        """
        Draws the berry bush (a square) and its current resource count.

        Args:
            surface: The pygame surface to draw on.
            font: The pygame font to use for rendering the resource count.
        """
        # Draw the bush square
        pygame.draw.rect(surface, config.BERRY_BUSH_COLOR, self.rect)

        # Draw the resource count text
        resource_text = f"{int(self.current_resources)}"
        text_surface = font.render(resource_text, True, config.RESOURCE_TEXT_COLOR)
        text_rect = text_surface.get_rect(center=self.rect.center)
        surface.blit(text_surface, text_rect)

    # update method is inherited from ResourceNode
    # collect method is inherited from ResourceNode