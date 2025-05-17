import pygame
from .node import ResourceNode
from src.core import config # Assuming config will have the necessary variables
from ..resources.resource_types import ResourceType # Import ResourceType

class BerryBush(ResourceNode):
    """
    Represents a Berry Bush resource node in the simulation.
    """
    def __init__(self, grid_position: pygame.Vector2): # Position is now grid_position
        """
        Initializes a BerryBush node.

        Args:
            grid_position: The grid coordinates of the bush (pygame.Vector2).
        """
        # Use configuration values for capacity and generation rate
        super().__init__(
            position=grid_position, # Store grid_position
            capacity=config.BERRY_BUSH_CAPACITY,
            generation_interval=config.BERRY_BUSH_GENERATION_INTERVAL,
            resource_type=ResourceType.BERRY
        )
        # Size of the bush representation (visual size on screen)
        self.display_size = config.GRID_CELL_SIZE # This is a pixel size for drawing
        # self.rect is now calculated in draw() as it depends on screen coordinates


    def draw(self, surface: pygame.Surface, font: pygame.font.Font, grid): # Add grid parameter
        """
        Draws the berry bush (a square) and its current resource count.

        Args:
            surface: The pygame surface to draw on.
            font: The pygame font to use for rendering the resource count.
            grid: The game grid object for coordinate conversions.
        """
        # Convert grid position to screen position for drawing
        screen_pos = grid.grid_to_screen(self.position)

        # Calculate the rect for drawing based on screen position
        # self.position is grid coords, screen_pos is pixel coords (center of cell)
        draw_rect = pygame.Rect(
            screen_pos[0] - self.display_size / 2,
            screen_pos[1] - self.display_size / 2,
            self.display_size,
            self.display_size
        )

        # Draw the bush square
        pygame.draw.rect(surface, config.BERRY_BUSH_COLOR, draw_rect)

        # Draw the resource count text
        resource_text = f"{int(self.current_quantity)}"
        text_surface = font.render(resource_text, True, config.RESOURCE_TEXT_COLOR)
        # Center text on the screen position of the bush
        text_rect = text_surface.get_rect(center=screen_pos)
        surface.blit(text_surface, text_rect)

    # update method is inherited from ResourceNode
    # collect method is inherited from ResourceNode