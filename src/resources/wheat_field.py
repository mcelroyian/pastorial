import pygame
from .node import ResourceNode
from ..resources.resource_types import ResourceType
from ..core import config

# SVG-based Color Constants for the Wheat Field
WHEAT_MAIN_FILL = (220, 178, 78)      # #dcb24e
WHEAT_SHADOW_FILL = (167, 121, 43)   # #a7792b

class WheatField(ResourceNode):
   """
   A resource node that generates Wheat.
   """
   GRID_WIDTH = 1
   GRID_HEIGHT = 1

   def __init__(self, position: pygame.Vector2):
       """
       Initializes a WheatField.

       Args:
           position: The position of the field on the grid (pygame.Vector2).
       """

       super().__init__(
           position=position,
           capacity=config.WHEAT_FIELD_CAPACITY,
           generation_interval=config.WHEAT_GENERATION_INTERVAL,
           resource_type=ResourceType.WHEAT
       )
       self.grid_width = WheatField.GRID_WIDTH
       self.grid_height = WheatField.GRID_HEIGHT

   def draw(self, surface: pygame.Surface, font: pygame.font.Font, grid):
       """
       Draws the wheat field using an SVG-like representation.
       """
       cell_x_start = self.position.x * config.GRID_CELL_SIZE
       cell_y_start = self.position.y * config.GRID_CELL_SIZE

       # SVG viewBox is 100x100 for this asset
       svg_viewbox_size = 100.0
       
       target_render_width = self.grid_width * config.GRID_CELL_SIZE
       scale_factor = target_render_width / svg_viewbox_size

       def s(value): # scale
           return value * scale_factor
       def so(value, offset_to_add): # scale and offset
            return int(value * scale_factor + offset_to_add)

       # Main wheat bands
       bands_data = [
           {'y': 0, 'h': 14.3}, {'y': 14.3, 'h': 14.3}, {'y': 28.6, 'h': 14.3},
           {'y': 42.9, 'h': 14.3}, {'y': 57.2, 'h': 14.3}, {'y': 71.5, 'h': 14.3},
           {'y': 85.8, 'h': 14.3}
       ]
       for band in bands_data:
           rect = pygame.Rect(
               so(0, cell_x_start), so(band['y'], cell_y_start),
               int(s(100)), int(s(band['h']))
           )
           pygame.draw.rect(surface, WHEAT_MAIN_FILL, rect)

       # Darker inner shadow stripes
       shadows_data = [
           {'y': 12, 'h': 2.5}, {'y': 26.3, 'h': 2.5}, {'y': 40.6, 'h': 2.5},
           {'y': 54.9, 'h': 2.5}, {'y': 69.2, 'h': 2.5}, {'y': 83.5, 'h': 2.5}
       ]
       for shadow in shadows_data:
           rect = pygame.Rect(
               so(0, cell_x_start), so(shadow['y'], cell_y_start),
               int(s(100)), int(s(shadow['h']))
           )
           pygame.draw.rect(surface, WHEAT_SHADOW_FILL, rect)

       # --- Text Overlay ---
       structure_rect = pygame.Rect(
           cell_x_start,
           cell_y_start,
           target_render_width,
           self.grid_height * config.GRID_CELL_SIZE
       )
       resource_text = f"{int(self.current_quantity)}"
       text_surface = font.render(resource_text, True, config.RESOURCE_TEXT_COLOR)
       text_rect = text_surface.get_rect(center=structure_rect.center)
       surface.blit(text_surface, text_rect)

   def __str__(self):
       return f"WheatField at {self.position} ({self.current_quantity:.1f}/{self.capacity} {self.resource_type.name})"

   def __repr__(self):
       return f"WheatField(position={self.position})"