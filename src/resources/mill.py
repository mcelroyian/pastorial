import pygame
from .processing import ProcessingStation
from ..resources.resource_types import ResourceType
from ..core import config # For GRID_CELL_SIZE, colors etc.

# SVG-based Color Constants for the Mill
MILL_SVG_BASE_FILL = (139, 94, 60)      # Hex: #8B5E3C
MILL_SVG_STROKE_COLOR = (101, 67, 33)   # Hex: #654321
MILL_SVG_ROOF_FILL = (160, 82, 45)      # Hex: #A0522D
MILL_SVG_DOOR_FILL = (101, 67, 33)      # Hex: #654321 (Same as stroke)
MILL_SVG_CENTER_FILL = (51, 51, 51)     # Hex: #333333
MILL_SVG_BLADE_COLOR = (85, 85, 85)     # Hex: #555555

class Mill(ProcessingStation):
    """
    A specific processing station that converts Wheat into Flour Powder.
    """
    # Note: MILL_COLOR_IDLE and MILL_COLOR_PROCESSING from the original implementation
    # are no longer used for the main body of the mill with the new SVG-style drawing.
    # They were (139, 69, 19) and (160, 82, 45) respectively.
    # self.color and self.processing_color are set in __init__ but won't affect the new draw method's main graphics.

    def __init__(self, position: pygame.Vector2):
        """
        Initializes a Mill.

        Args:
            position: The position of the mill on the grid.
        """
        super().__init__(
            position=position,
            accepted_input_type=ResourceType.WHEAT,
            produced_output_type=ResourceType.FLOUR_POWDER,
            conversion_ratio=1.0,  # 1 Wheat -> 1 Flour Powder
            processing_speed=8,    # 8 simulation ticks per unit
            input_capacity=25,
            output_capacity=25
        )
        # self.color and self.processing_color are initialized by the ProcessingStation base class.
        # The Mill's custom draw method uses MILL_SVG_* constants for its appearance,
        # so we don't need to override self.color and self.processing_color here
        # with the old MILL_COLOR_IDLE/MILL_COLOR_PROCESSING.

    def draw(self, surface: pygame.Surface, font: pygame.font.Font):
        """
        Draws the mill on the given surface using a detailed SVG-like representation.
        Overrides ProcessingStation.draw().
        """
        cell_x_start = self.position.x * config.GRID_CELL_SIZE
        cell_y_start = self.position.y * config.GRID_CELL_SIZE
        
        # SVG viewBox is 200x200, scale to GRID_CELL_SIZE
        svg_viewbox_size = 200.0
        scale_factor = config.GRID_CELL_SIZE / svg_viewbox_size

        # Helper to scale and offset coordinates
        def s(value): # scale
            return value * scale_factor
        def so(value, offset_to_add): # scale and offset
             return int(value * scale_factor + offset_to_add)

        # Mill Base: <rect x="70" y="100" width="60" height="80" stroke-width="2" />
        base_x = so(70, cell_x_start)
        base_y = so(100, cell_y_start)
        base_w = int(s(60))
        base_h = int(s(80))
        base_stroke_w = max(1, int(s(2)))
        pygame.draw.rect(surface, MILL_SVG_BASE_FILL, (base_x, base_y, base_w, base_h))
        pygame.draw.rect(surface, MILL_SVG_STROKE_COLOR, (base_x, base_y, base_w, base_h), base_stroke_w)

        # Roof: <polygon points="70,100 100,70 130,100" stroke-width="2" />
        roof_points_svg = [(70,100), (100,70), (130,100)]
        roof_points_scaled = [
            (so(p[0], cell_x_start), so(p[1], cell_y_start)) for p in roof_points_svg
        ]
        roof_stroke_w = max(1, int(s(2)))
        pygame.draw.polygon(surface, MILL_SVG_ROOF_FILL, roof_points_scaled)
        pygame.draw.polygon(surface, MILL_SVG_STROKE_COLOR, roof_points_scaled, roof_stroke_w)

        # Door: <rect x="95" y="140" width="10" height="40" />
        door_x = so(95, cell_x_start)
        door_y = so(140, cell_y_start)
        door_w = max(1, int(s(10))) # Ensure door is at least 1px wide
        door_h = max(1, int(s(40))) # Ensure door is at least 1px high
        pygame.draw.rect(surface, MILL_SVG_DOOR_FILL, (door_x, door_y, door_w, door_h))
        
        # Windmill Center: <circle cx="100" cy="85" r="5" />
        center_cx = so(100, cell_x_start)
        center_cy = so(85, cell_y_start)
        center_r = max(1, int(s(5)))
        pygame.draw.circle(surface, MILL_SVG_CENTER_FILL, (center_cx, center_cy), center_r)

        # Blades: <line stroke-width="4"/> (all start at 100,85)
        blade_start_svg_x, blade_start_svg_y = 100, 85
        blade_start_x = so(blade_start_svg_x, cell_x_start)
        blade_start_y = so(blade_start_svg_y, cell_y_start)
        blade_stroke_w = max(1, int(s(4)))

        blade_ends_svg = [
            (140, 45), (60, 45),
            (140, 125), (60, 125)
        ]
        for end_x_svg, end_y_svg in blade_ends_svg:
            end_x = so(end_x_svg, cell_x_start)
            end_y = so(end_y_svg, cell_y_start)
            pygame.draw.line(surface, MILL_SVG_BLADE_COLOR, (blade_start_x, blade_start_y), (end_x, end_y), blade_stroke_w)

        # --- Text Overlays (copied and adapted from ProcessingStation.draw) ---
        station_rect = pygame.Rect(cell_x_start, cell_y_start, config.GRID_CELL_SIZE, config.GRID_CELL_SIZE)

        # Display input: "I:type qty/cap"
        input_text_str = f"I:{self.accepted_input_type.name[0]}:{int(self.current_input_quantity)}/{self.input_capacity}"
        input_surface = font.render(input_text_str, True, config.DEBUG_TEXT_COLOR)
        input_rect = input_surface.get_rect(midtop=station_rect.midtop)
        input_rect.y += 2 # Small offset
        surface.blit(input_surface, input_rect)
        
        # Display output: "O:type qty/cap"
        output_text_str = f"O:{self.produced_output_type.name[0]}:{int(self.current_output_quantity)}/{self.output_capacity}"
        output_surface = font.render(output_text_str, True, config.DEBUG_TEXT_COLOR)
        output_rect = output_surface.get_rect(midbottom=station_rect.midbottom)
        output_rect.y -= 2 # Small offset
        surface.blit(output_surface, output_rect)

        if self.is_processing:
            progress_text_str = f"{self.processing_progress}/{self.processing_speed}"
            progress_surface = font.render(progress_text_str, True, config.DEBUG_TEXT_COLOR)
            progress_rect = progress_surface.get_rect(center=station_rect.center)
            # Potentially adjust progress_rect.y if it clashes with mill center/blades
            # For now, let's keep it centered.
            surface.blit(progress_surface, progress_rect)

    def __str__(self):
        return super().__str__() # Or customize if needed

    def __repr__(self):
        return f"Mill(position={self.position})"