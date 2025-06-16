import pygame
from ..core import config
from .processing import MultiInputProcessingStation
from .resource_types import ResourceType
from .recipe import Recipe

# Define the recipe for bread
BREAD_RECIPE = Recipe(
    inputs={
        ResourceType.FLOUR_POWDER: 2,
        ResourceType.WATER: 1
    },
    outputs={
        ResourceType.BREAD: 1
    }
)

class Bakery(MultiInputProcessingStation):
    """
    A bakery that processes ingredients into bread based on a recipe.
    Inherits from the data-driven MultiInputProcessingStation.
    """
    GRID_WIDTH = 2
    GRID_HEIGHT = 2

    def __init__(self, position: pygame.Vector2):
        super().__init__(
            position=position,
            recipe=BREAD_RECIPE,
            processing_speed=config.BAKERY_PROCESSING_SPEED,
            input_capacity=config.BAKERY_FLOUR_CAPACITY,  # Using flour capacity as a general input capacity
            output_capacity=config.BAKERY_OUTPUT_CAPACITY
        )

        # Visuals
        self.color = config.BAKERY_COLOR
        self.processing_color = config.BAKERY_PROCESSING_COLOR

    def draw(self, surface: pygame.Surface, font: pygame.font.Font):
        """Draws the bakery on the given surface."""
        rect_x = self.position.x * config.GRID_CELL_SIZE
        rect_y = self.position.y * config.GRID_CELL_SIZE
        station_rect = pygame.Rect(rect_x, rect_y, self.GRID_WIDTH * config.GRID_CELL_SIZE, self.GRID_HEIGHT * config.GRID_CELL_SIZE)

        current_color = self.processing_color if self.is_processing else self.color
        pygame.draw.rect(surface, current_color, station_rect)
        pygame.draw.rect(surface, config.COLOR_BLACK, station_rect, 1)

        # Display inputs based on recipe
        y_offset = 5
        for resource_type, required in self.recipe.inputs.items():
            text = f"{resource_type.name[0]}: {int(self.current_input_quantity.get(resource_type, 0))}/{self.input_capacity}"
            text_surface = font.render(text, True, config.DEBUG_TEXT_COLOR)
            surface.blit(text_surface, (station_rect.x + 5, station_rect.y + y_offset))
            y_offset += 20

        # Display output based on recipe
        for resource_type, produced in self.recipe.outputs.items():
            output_text = f"{resource_type.name[0]}: {int(self.current_output_quantity.get(resource_type, 0))}/{self.output_capacity}"
            output_surface = font.render(output_text, True, config.DEBUG_TEXT_COLOR)
            output_rect = output_surface.get_rect(bottomright=(station_rect.right - 5, station_rect.bottom - 5))
            surface.blit(output_surface, output_rect)

        if self.is_processing:
            progress_text = f"{self.processing_progress}/{self.processing_speed}"
            progress_surface = font.render(progress_text, True, config.DEBUG_TEXT_COLOR)
            progress_rect = progress_surface.get_rect(center=station_rect.center)
            surface.blit(progress_surface, progress_rect)

    def __str__(self):
        inputs = ", ".join([f"{r.name}: {q:.1f}/{self.input_capacity}" for r, q in self.current_input_quantity.items()])
        outputs = ", ".join([f"{r.name}: {q:.1f}/{self.output_capacity}" for r, q in self.current_output_quantity.items()])
        return (f"{self.__class__.__name__} at {self.position} "
                f"Inputs: [{inputs}] -> Outputs: [{outputs}] "
                f"State: {self.get_visual_state()} ({self.processing_progress}/{self.processing_speed})")