import pygame
from .processing import ProcessingStation
from ..resources.resource_types import ResourceType
from ..core import config # For GRID_CELL_SIZE, colors etc.

class Mill(ProcessingStation):
    """
    A specific processing station that converts Wheat into Flour Powder.
    """
    MILL_COLOR_IDLE = (139, 69, 19)  # SaddleBrown
    MILL_COLOR_PROCESSING = (160, 82, 45) # Sienna

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
        self.color = self.MILL_COLOR_IDLE
        self.processing_color = self.MILL_COLOR_PROCESSING

    # The draw method from ProcessingStation can be used directly if the
    # color and processing_color are set appropriately, as done above.
    # If a more distinct visual is needed, this draw method can be overridden.
    # For now, we rely on the base class draw method with custom colors.

    # def draw(self, surface: pygame.Surface, font: pygame.font.Font):
    #     """
    #     Draws the mill on the given surface.
    #     Overrides ProcessingStation.draw() for specific Mill visuals if needed.
    #     """
    #     # Call super().draw() or implement custom drawing
    #     # For now, let's ensure the colors are set correctly in __init__
    #     # and rely on the base class draw method.
    #     current_display_color = self.processing_color if self.is_processing else self.color
    #
    #     rect_x = self.position.x * config.GRID_CELL_SIZE
    #     rect_y = self.position.y * config.GRID_CELL_SIZE
    #     station_rect = pygame.Rect(rect_x, rect_y, config.GRID_CELL_SIZE, config.GRID_CELL_SIZE)
    #
    #     pygame.draw.rect(surface, current_display_color, station_rect)
    #     pygame.draw.rect(surface, config.COLOR_BLACK, station_rect, 1) # Border
    #
    #     # You can call the base class's text drawing logic or reimplement
    #     super().draw_text_info(surface, font) # Assuming base class has such a helper or draw has it

    def __str__(self):
        return super().__str__() # Or customize if needed

    def __repr__(self):
        return f"Mill(position={self.position})"