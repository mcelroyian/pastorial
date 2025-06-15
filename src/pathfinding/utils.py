import pygame
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..rendering.grid import Grid

def find_closest_walkable_tile(
    start_pos: pygame.math.Vector2,
    max_radius: int,
    grid: 'Grid'
) -> Optional[pygame.math.Vector2]:
    """
    Performs a spiral search for the closest walkable tile around a start position.

    Args:
        start_pos (pygame.math.Vector2): The center position to search from.
        max_radius (int): The maximum search radius.
        grid (Grid): The grid object containing walkability info.

    Returns:
        Optional[pygame.math.Vector2]: The position of the closest walkable tile, or None if not found.
    """
    if grid.is_walkable(int(start_pos.x), int(start_pos.y)):
        return start_pos

    for r in range(1, max_radius + 1):
        # Check top and bottom edges of the search square
        for i in range(-r, r + 1):
            for dy in [-r, r]:
                pos = pygame.math.Vector2(start_pos.x + i, start_pos.y + dy)
                if grid.is_within_bounds(pos) and grid.is_walkable(int(pos.x), int(pos.y)):
                    return pos
        # Check left and right edges (excluding corners already checked)
        for i in range(-r + 1, r):
            for dx in [-r, r]:
                pos = pygame.math.Vector2(start_pos.x + dx, start_pos.y + i)
                if grid.is_within_bounds(pos) and grid.is_walkable(int(pos.x), int(pos.y)):
                    return pos
    return None