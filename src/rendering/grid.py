import pygame
from src.core import config

def draw_grid(surface):
    """Draws a grid on the given surface based on config settings."""
    width = config.SCREEN_WIDTH
    height = config.SCREEN_HEIGHT
    cell_size = config.GRID_CELL_SIZE
    grid_color = config.GRID_COLOR

    # Draw vertical lines
    for x in range(0, width, cell_size):
        pygame.draw.line(surface, grid_color, (x, 0), (x, height))

    # Draw horizontal lines
    for y in range(0, height, cell_size):
        pygame.draw.line(surface, grid_color, (0, y), (width, y))