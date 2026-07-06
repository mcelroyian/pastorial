import pygame

from src.rendering.grid import Grid
from src.pathfinding.astar import find_path


def _grid():
    return Grid()


def test_straight_path_found():
    grid = _grid()
    start = pygame.math.Vector2(0, 5)
    end = pygame.math.Vector2(4, 5)
    path = find_path(start, end, grid)
    assert path is not None
    assert path[0] == start
    assert path[-1] == end


def test_path_routes_around_obstacle():
    grid = _grid()
    # Vertical wall at x=2, rows y=0..4
    for y in range(5):
        grid.occupancy_grid[y][2] = 1
    start = pygame.math.Vector2(0, 2)
    end = pygame.math.Vector2(4, 2)
    path = find_path(start, end, grid)
    assert path is not None
    assert path[-1] == end
    # No step should land on a blocked cell
    for pos in path[1:]:
        gx, gy = int(pos.x), int(pos.y)
        assert grid.occupancy_grid[gy][gx] == 0, f"Path passed through blocked cell {pos}"


def test_fully_blocked_returns_none():
    grid = _grid()
    # Start at corner (0,0); only exits are East (1,0) and South (0,1) — block both
    grid.occupancy_grid[0][1] = 1  # cell (x=1, y=0)
    grid.occupancy_grid[1][0] = 1  # cell (x=0, y=1)
    path = find_path(pygame.math.Vector2(0, 0), pygame.math.Vector2(5, 5), grid)
    assert path is None


def test_blocked_goal_returns_none():
    grid = _grid()
    goal = pygame.math.Vector2(3, 3)
    grid.occupancy_grid[3][3] = 1  # block the goal itself
    path = find_path(pygame.math.Vector2(0, 0), goal, grid)
    assert path is None


def test_start_equals_goal():
    grid = _grid()
    pos = pygame.math.Vector2(3, 3)
    path = find_path(pos, pos, grid)
    assert path is not None
    assert len(path) == 1
    assert path[0] == pos
