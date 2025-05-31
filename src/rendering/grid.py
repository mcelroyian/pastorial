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

        # 0 for walkable, 1 for occupied
        self.occupancy_grid: list[list[int]] = [
            [0 for _ in range(self.width_in_cells)] for _ in range(self.height_in_cells)
        ]

        print(f"Grid initialized: {self.width_in_cells}x{self.height_in_cells} cells of size {self.cell_size}x{self.cell_size}, occupancy grid created.") # Debug

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

    def is_walkable(self, grid_x: int, grid_y: int) -> bool:
        """
        Checks if a given grid cell is walkable.
        Considers a cell walkable if it's within bounds and not marked as occupied.
        """
        if not self.is_within_bounds(Vector2(grid_x, grid_y)):
            return False
        return self.occupancy_grid[grid_y][grid_x] == 0

    def update_occupancy(self, entity, grid_x: int, grid_y: int, width: int, height: int, is_placing: bool):
        """
        Updates the occupancy status of a rectangular area on the grid.
        'entity' is currently unused but kept for potential future use.
        """
        value_to_set = 1 if is_placing else 0 # 1 for occupied, 0 for walkable
        for r in range(height):
            for c in range(width):
                cell_x, cell_y = grid_x + c, grid_y + r
                if self.is_within_bounds(Vector2(cell_x, cell_y)):
                    self.occupancy_grid[cell_y][cell_x] = value_to_set
                # else:
                #     print(f"Warning: Attempted to update occupancy out of bounds at ({cell_x}, {cell_y})")


    def is_area_free(self, grid_x: int, grid_y: int, width: int, height: int) -> bool:
        """
        Checks if a rectangular area on the grid is free (all cells walkable and within bounds).
        """
        for r in range(height):
            for c in range(width):
                cell_x, cell_y = grid_x + c, grid_y + r
                if not self.is_within_bounds(Vector2(cell_x, cell_y)):
                    return False # Part of the area is out of bounds
                if self.occupancy_grid[cell_y][cell_x] != 0: # Cell is occupied
                    return False
        return True