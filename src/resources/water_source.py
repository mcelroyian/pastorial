import pygame
from .node import ResourceNode
from src.core import config
from ..resources.resource_types import ResourceType

# SVG-based Color Constants for the Well
WELL_ROOF_FILL = (139, 69, 19)      # SaddleBrown, from #8B4513
WELL_ROOF_STROKE = (92, 51, 23)     # Brown, from #5C3317
WELL_POST_FILL = (139, 69, 19)      # SaddleBrown, from #8B4513
WELL_POST_STROKE = (92, 51, 23)     # Brown, from #5C3317
WELL_BASE_FILL = (176, 176, 176)    # LightGray, from #B0B0B0
WELL_BASE_STROKE = (128, 128, 128)  # Gray, from #808080

class WaterSource(ResourceNode):
    """
    Represents a Water Source (Well) resource node in the simulation.
    """
    GRID_WIDTH = 2
    GRID_HEIGHT = 3

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
        self.grid_width = WaterSource.GRID_WIDTH
        self.grid_height = WaterSource.GRID_HEIGHT

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, grid):
        """
        Draws the well using a detailed SVG-like representation and its current resource count.

        Args:
            surface: The pygame surface to draw on.
            font: The pygame font to use for rendering the resource count.
            grid: The game grid object for coordinate conversions.
        """
        # Base position and dimensions
        cell_x_start = self.position.x * config.GRID_CELL_SIZE
        cell_y_start = self.position.y * config.GRID_CELL_SIZE
        
        # SVG viewBox is 200x300
        svg_viewbox_width = 200.0
        svg_viewbox_height = 300.0
        
        # Scale to the new grid area of the well
        target_render_width = self.grid_width * config.GRID_CELL_SIZE
        target_render_height = self.grid_height * config.GRID_CELL_SIZE
        
        scale_x = target_render_width / svg_viewbox_width
        scale_y = target_render_height / svg_viewbox_height

        # Helper to scale and offset coordinates
        def so(x, y):
            return (
                int(x * scale_x + cell_x_start),
                int(y * scale_y + cell_y_start)
            )
        
        def s(value, axis='x'):
            return int(value * (scale_x if axis == 'x' else scale_y))

        # Roof: <polygon points="50,40 100,10 150,40 150,60 50,60" />
        roof_points_svg = [(50, 40), (100, 10), (150, 40), (150, 60), (50, 60)]
        roof_points_scaled = [so(p[0], p[1]) for p in roof_points_svg]
        roof_stroke_w = max(1, s(2))
        pygame.draw.polygon(surface, WELL_ROOF_FILL, roof_points_scaled)
        pygame.draw.polygon(surface, WELL_ROOF_STROKE, roof_points_scaled, roof_stroke_w)

        # Side Posts: <rect x="45" y="60" width="10" height="90" /> and <rect x="145" y="60" width="10" height="90" />
        post1_pos = so(45, 60)
        post1_dims = (s(10, 'x'), s(90, 'y'))
        post_stroke_w = max(1, s(1))
        pygame.draw.rect(surface, WELL_POST_FILL, (post1_pos[0], post1_pos[1], post1_dims[0], post1_dims[1]))
        pygame.draw.rect(surface, WELL_POST_STROKE, (post1_pos[0], post1_pos[1], post1_dims[0], post1_dims[1]), post_stroke_w)

        post2_pos = so(145, 60)
        post2_dims = (s(10, 'x'), s(90, 'y'))
        pygame.draw.rect(surface, WELL_POST_FILL, (post2_pos[0], post2_pos[1], post2_dims[0], post2_dims[1]))
        pygame.draw.rect(surface, WELL_POST_STROKE, (post2_pos[0], post2_pos[1], post2_dims[0], post2_dims[1]), post_stroke_w)

        # Stone Base: <rect x="50" y="150" width="100" height="100" />
        base_pos = so(50, 150)
        base_dims = (s(100, 'x'), s(100, 'y'))
        base_stroke_w = max(1, s(2))
        pygame.draw.rect(surface, WELL_BASE_FILL, (base_pos[0], base_pos[1], base_dims[0], base_dims[1]))
        pygame.draw.rect(surface, WELL_BASE_STROKE, (base_pos[0], base_pos[1], base_dims[0], base_dims[1]), base_stroke_w)

        # Stone Lines (Vertical and Horizontal)
        line_stroke_w = max(1, s(1))
        # Vertical
        pygame.draw.line(surface, WELL_BASE_STROKE, so(75, 150), so(75, 250), line_stroke_w)
        pygame.draw.line(surface, WELL_BASE_STROKE, so(100, 150), so(100, 250), line_stroke_w)
        pygame.draw.line(surface, WELL_BASE_STROKE, so(125, 150), so(125, 250), line_stroke_w)
        # Horizontal
        pygame.draw.line(surface, WELL_BASE_STROKE, so(50, 175), so(150, 175), line_stroke_w)
        pygame.draw.line(surface, WELL_BASE_STROKE, so(50, 200), so(150, 200), line_stroke_w)
        pygame.draw.line(surface, WELL_BASE_STROKE, so(50, 225), so(150, 225), line_stroke_w)

        # --- Text Overlay ---
        # Center text in the new larger area
        structure_rect = pygame.Rect(
            cell_x_start,
            cell_y_start,
            target_render_width,
            target_render_height
        )
        resource_text = f"{int(self.current_quantity)}"
        text_surface = font.render(resource_text, True, config.RESOURCE_TEXT_COLOR)
        text_rect = text_surface.get_rect(center=structure_rect.center)
        surface.blit(text_surface, text_rect)