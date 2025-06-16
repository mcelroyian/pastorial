import pygame
from .node import ResourceNode
from src.core import config
from ..resources.resource_types import ResourceType

# SVG-based Color Constants for the Berry Bush
BUSH_LEAF_FILL = (0, 128, 0)      # Green
BUSH_TRUNK_FILL = (139, 69, 19)   # SaddleBrown
BERRY_FILL = (255, 0, 0)          # Red
BERRY_STROKE = (0, 0, 0)          # Black
BERRY_STEM_COLOR = (165, 42, 42)  # Brown

class BerryBush(ResourceNode):
    """
    Represents a Berry Bush resource node in the simulation.
    """
    GRID_WIDTH = 2
    GRID_HEIGHT = 2

    def __init__(self, grid_position: pygame.Vector2):
        """
        Initializes a BerryBush node.

        Args:
            grid_position: The grid coordinates of the bush (pygame.Vector2).
        """
        super().__init__(
            position=grid_position,
            capacity=config.BERRY_BUSH_CAPACITY,
            generation_interval=config.BERRY_BUSH_GENERATION_INTERVAL,
            resource_type=ResourceType.BERRY
        )
        self.grid_width = BerryBush.GRID_WIDTH
        self.grid_height = BerryBush.GRID_HEIGHT

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, grid):
        """
        Draws the berry bush using a detailed SVG-like representation.
        """
        cell_x_start = self.position.x * config.GRID_CELL_SIZE
        cell_y_start = self.position.y * config.GRID_CELL_SIZE

        # SVG viewBox is 300x300
        svg_viewbox_size = 300.0
        
        target_render_width = self.grid_width * config.GRID_CELL_SIZE
        scale_factor = target_render_width / svg_viewbox_size

        def s(value): # scale
            return value * scale_factor
        def so(value, offset_to_add): # scale and offset
             return int(value * scale_factor + offset_to_add)

        # Trunk: <rect x="140" y="200" width="20" height="30" fill="saddlebrown" />
        trunk_x = so(140, cell_x_start)
        trunk_y = so(200, cell_y_start)
        trunk_w = int(s(20))
        trunk_h = int(s(30))
        pygame.draw.rect(surface, BUSH_TRUNK_FILL, (trunk_x, trunk_y, trunk_w, trunk_h))

        # Solid leafy bush: <ellipse cx="150" cy="140" rx="80" ry="60" fill="green" />
        bush_cx = so(150, cell_x_start)
        bush_cy = so(140, cell_y_start)
        bush_rx = int(s(80))
        bush_ry = int(s(60))
        bush_rect = pygame.Rect(bush_cx - bush_rx, bush_cy - bush_ry, 2 * bush_rx, 2 * bush_ry)
        pygame.draw.ellipse(surface, BUSH_LEAF_FILL, bush_rect)

        # Berries and Stems
        berries_data = [
            {'cx': 120, 'cy': 130, 'r': 5, 'stem_x1': 120, 'stem_y1': 125, 'stem_x2': 120, 'stem_y2': 120},
            {'cx': 150, 'cy': 110, 'r': 5, 'stem_x1': 150, 'stem_y1': 105, 'stem_x2': 150, 'stem_y2': 100},
            {'cx': 170, 'cy': 130, 'r': 5, 'stem_x1': 170, 'stem_y1': 125, 'stem_x2': 170, 'stem_y2': 120},
            {'cx': 160, 'cy': 150, 'r': 5, 'stem_x1': 160, 'stem_y1': 145, 'stem_x2': 160, 'stem_y2': 140},
            {'cx': 140, 'cy': 160, 'r': 5, 'stem_x1': 140, 'stem_y1': 155, 'stem_x2': 140, 'stem_y2': 150},
        ]

        for berry in berries_data:
            # Stem
            stem_start = (so(berry['stem_x1'], cell_x_start), so(berry['stem_y1'], cell_y_start))
            stem_end = (so(berry['stem_x2'], cell_x_start), so(berry['stem_y2'], cell_y_start))
            stem_width = max(1, int(s(2)))
            pygame.draw.line(surface, BERRY_STEM_COLOR, stem_start, stem_end, stem_width)
            
            # Berry
            berry_cx = so(berry['cx'], cell_x_start)
            berry_cy = so(berry['cy'], cell_y_start)
            berry_r = max(1, int(s(berry['r'])))
            stroke_w = max(1, int(s(1)))
            pygame.draw.circle(surface, BERRY_FILL, (berry_cx, berry_cy), berry_r)
            pygame.draw.circle(surface, BERRY_STROKE, (berry_cx, berry_cy), berry_r, stroke_w)

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