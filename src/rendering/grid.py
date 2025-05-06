import pygame
from src.core import config
from pygame.math import Vector2

class Grid:
    """
    Represents the simulation grid, handling drawing and coordinate conversions.
    """
    def __init__(self):
        """Initializes the grid based on configuration."""
        self.screen_width = config.SCREEN_WIDTH
        self.screen_height = config.SCREEN_HEIGHT
        self.cell_size = config.GRID_CELL_SIZE # Assuming square cells for now
        self.cell_width = self.cell_size
        self.cell_height = self.cell_size
        self.grid_color = config.GRID_COLOR

        if self.cell_width <= 0 or self.cell_height <= 0:
            raise ValueError("GRID_CELL_SIZE must be positive.")

        self.width_in_cells = self.screen_width // self.cell_width
        self.height_in_cells = self.screen_height // self.cell_height

        print(f"Grid initialized: {self.width_in_cells}x{self.height_in_cells} cells of size {self.cell_size}x{self.cell_size}") # Debug

    def draw(self, surface: pygame.Surface):
        """Draws the grid lines on the given surface."""
        # Draw vertical lines
        for x in range(0, self.screen_width, self.cell_width):
            pygame.draw.line(surface, self.grid_color, (x, 0), (x, self.screen_height))

        # Draw horizontal lines
        for y in range(0, self.screen_height, self.cell_height):
            pygame.draw.line(surface, self.grid_color, (0, y), (self.screen_width, y))

    def grid_to_screen(self, grid_pos: Vector2) -> tuple[int, int]:
        """
        Converts grid coordinates (e.g., Vector2(5, 3)) to screen pixel coordinates
        (center of the cell).
        """
        screen_x = int(grid_pos.x * self.cell_width + self.cell_width / 2)
        screen_y = int(grid_pos.y * self.cell_height + self.cell_height / 2)
        return screen_x, screen_y

    def screen_to_grid(self, screen_pos: tuple[int, int]) -> Vector2:
        """
        Converts screen pixel coordinates to grid coordinates.
        """
        grid_x = screen_pos[0] // self.cell_width
        grid_y = screen_pos[1] // self.cell_height
        return Vector2(grid_x, grid_y)

    def is_within_bounds(self, grid_pos: Vector2) -> bool:
        """Checks if a grid position is within the valid grid cell range."""
        return 0 <= grid_pos.x < self.width_in_cells and 0 <= grid_pos.y < self.height_in_cells