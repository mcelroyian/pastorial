import pygame
import heapq # For the priority queue (open list)
import logging # Added for debugging
from typing import List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ..rendering.grid import Grid # For type hinting Grid class

logger = logging.getLogger(__name__) # Added for debugging

# Heuristic function (Manhattan distance for grid)
def heuristic(a: pygame.math.Vector2, b: pygame.math.Vector2) -> float:
    """Calculates the Manhattan distance between two points."""
    return abs(a.x - b.x) + abs(a.y - b.y)

class Node:
    """Represents a node in the A* pathfinding grid."""
    def __init__(self, position: pygame.math.Vector2, parent: Optional['Node'] = None):
        self.position = position
        self.parent = parent

        self.g_cost = 0  # Cost from start to current node
        self.h_cost = 0  # Heuristic cost from current node to end
        self.f_cost = 0  # Total cost (g_cost + h_cost)

    def __eq__(self, other):
        return self.position == other.position

    def __lt__(self, other):
        return self.f_cost < other.f_cost

    def __hash__(self):
        # Hash based on position for set operations
        return hash((self.position.x, self.position.y))

def find_path(start_pos: pygame.math.Vector2, end_pos: pygame.math.Vector2, grid: 'Grid') -> Optional[List[pygame.math.Vector2]]:
    """
    Finds a path from start_pos to end_pos using the A* algorithm.

    Args:
        start_pos (pygame.math.Vector2): The starting grid coordinates.
        end_pos (pygame.math.Vector2): The ending grid coordinates.
        grid (Grid): The game grid, providing walkability information.

    Returns:
        Optional[List[pygame.math.Vector2]]: A list of grid coordinates representing the path,
                                             or None if no path is found.
    """
    logger.debug(f"find_path: Called with start_pos={start_pos}, end_pos={end_pos}")
    # Pathfinding should be allowed from the start_pos even if it's "occupied" by the agent itself.
    # The critical check is for the end_pos and intermediate steps.
    if not grid.is_walkable(int(end_pos.x), int(end_pos.y)):
        logger.warning(f"find_path: End position {end_pos} is not walkable. Pathfinding aborted.")
        return None # Pathfinding aborted if end is not walkable
    
    start_node = Node(start_pos)
    end_node = Node(end_pos)

    open_list: List[Node] = []
    closed_list: set[Node] = set() # Using a set for O(1) lookups for Node positions

    heapq.heappush(open_list, start_node)
    logger.debug(f"find_path: Pushed start_node {start_node.position} to open_list. Open list size: {len(open_list)}")

    iteration_count = 0
    max_iterations = grid.width_in_cells * grid.height_in_cells * 2 # Safety break

    while open_list:
        iteration_count += 1
        if iteration_count > max_iterations:
            logger.error(f"find_path: Exceeded max iterations ({max_iterations}). Aborting pathfinding between {start_pos} and {end_pos}.")
            return None

        if not open_list: # Should not happen if while open_list is the condition, but good for sanity
            logger.warning(f"find_path: Open list is empty but loop continued. This should not happen.")
            break
            
        current_node = heapq.heappop(open_list)
        logger.debug(f"find_path: Popped current_node {current_node.position} (g={current_node.g_cost:.2f}, h={current_node.h_cost:.2f}, f={current_node.f_cost:.2f}). Open list size: {len(open_list)}")
        
        if current_node in closed_list: # If we added duplicate nodes to open_list, skip if already processed
            logger.debug(f"find_path: Current node {current_node.position} already in closed_list. Skipping.")
            continue
            
        closed_list.add(current_node)
        logger.debug(f"find_path: Added current_node {current_node.position} to closed_list. Closed list size: {len(closed_list)}")

        if current_node == end_node:
            path = []
            temp = current_node
            while temp is not None:
                path.append(temp.position)
                temp = temp.parent
            logger.info(f"find_path: Path found from {start_pos} to {end_pos}. Length: {len(path)}. Path: {path[::-1]}")
            return path[::-1]  # Return reversed path

        # Get neighbors (adjacent grid cells)
        # Assuming 4-directional movement (up, down, left, right)
        # Can be extended to 8-directional if diagonal movement is allowed and costed appropriately
        neighbors_coords = [
            (0, -1), (0, 1), (-1, 0), (1, 0),
            # (-1, -1), (-1, 1), (1, -1), (1, 1) # Optional: Diagonal neighbors
        ]

        for new_position_offset in neighbors_coords:
            node_position = pygame.math.Vector2(
                current_node.position.x + new_position_offset[0],
                current_node.position.y + new_position_offset[1]
            )

            # Check if within grid bounds
            if not grid.is_within_bounds(node_position):
                logger.debug(f"find_path: Neighbor {node_position} is out of bounds.")
                continue

            # Check if walkable
            if not grid.is_walkable(int(node_position.x), int(node_position.y)):
                logger.debug(f"find_path: Neighbor {node_position} is not walkable.")
                continue

            neighbor = Node(node_position, current_node)

            if neighbor in closed_list:
                logger.debug(f"find_path: Neighbor {neighbor.position} already in closed_list.")
                continue

            # Calculate costs
            # Assuming cost to move to an adjacent cell is 1
            # If diagonal moves are added, their cost might be sqrt(2) or ~1.4
            tentative_g_cost = current_node.g_cost + 1 # Cost to move from current to neighbor

            # Check if neighbor is in open_list and if this path is better
            # This check is a bit tricky with heapq. It's often simpler to allow duplicates
            # in the open_list with different g_costs and let the heapq pop the one with lower f_cost.
            # Or, iterate through open_list to find and update (less efficient for large open_lists).
            # For simplicity here, if a better path is found, we update and re-add/re-prioritize.
            # A more robust way is to store nodes in open_list with a way to update their priority or
            # simply add the new, better node and rely on the fact it will be processed earlier.

            # Let's check if the neighbor is already in open_list with a higher g_cost
            in_open_list = False
            for open_node in open_list:
                if open_node == neighbor and tentative_g_cost >= open_node.g_cost:
                    in_open_list = True # Found a path in open_list that's already as good or better
                    break
            
            if in_open_list:
                continue

            # This path is the best so far. Record it.
            neighbor.g_cost = tentative_g_cost
            neighbor.h_cost = heuristic(neighbor.position, end_node.position)
            neighbor.f_cost = neighbor.g_cost + neighbor.h_cost
            logger.debug(f"find_path: Evaluating neighbor {neighbor.position}. Tentative g_cost={neighbor.g_cost:.2f}, h_cost={neighbor.h_cost:.2f}, f_cost={neighbor.f_cost:.2f}")
            
            # Add the neighbor to the open list
            # If it was already there but with a worse path, this new one will be prioritized.
            # If it wasn't there, it gets added.
            heapq.heappush(open_list, neighbor)
            logger.debug(f"find_path: Pushed neighbor {neighbor.position} to open_list. Open list size: {len(open_list)}")
            
    logger.warning(f"find_path: Path not found from {start_pos} to {end_pos}. Open list became empty after {iteration_count} iterations.")
    return None # Path not found