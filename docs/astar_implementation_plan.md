## Project Plan: Refactoring Occupancy Grid and Implementing A* Pathfinding

This plan details the necessary refactoring of the `occupancy_grid` and the subsequent implementation of the A* pathfinding algorithm.

### Part 1: Refactoring `occupancy_grid` Management

**Current Situation & Problem:**

Currently, the `occupancy_grid` is created within the `GameLoop` class ([`src/core/game_loop.py`](src/core/game_loop.py)). It's then passed down through the `AgentManager` ([`src/agents/manager.py`](src/agents/manager.py)) to individual `Agent` instances ([`src/agents/agent.py`](src/agents/agent.py)). This creates a chain of dependencies and couples these components tightly to the specific data structure of the `occupancy_grid`. Modifying how occupancy is handled can lead to changes in multiple classes.

**Proposed Refactoring Solution:**

To improve modularity and encapsulation, we will refactor the `Grid` class ([`src/rendering/grid.py`](src/rendering/grid.py)) to manage the `occupancy_grid` data directly.

**Detailed Changes:**

1.  **`Grid` Class Enhancements ([`src/rendering/grid.py`](src/rendering/grid.py)):**
    *   The `Grid` class will internally create and store the `occupancy_grid`.
    *   It will expose methods to query and update this grid. Key methods will include:
        *   `is_walkable(self, grid_x: int, grid_y: int) -> bool`: Checks if a given grid cell is passable.
        *   `update_occupancy(self, entity, grid_x: int, grid_y: int, width: int, height: int, is_placing: bool)`: Updates the occupancy status of a region of the grid. This method will encapsulate the logic currently in `GameLoop.update_occupancy()` ([`src/core/game_loop.py`](src/core/game_loop.py:285)).
        *   `is_area_free(self, grid_x: int, grid_y: int, width: int, height: int) -> bool`: Checks if a rectangular area on the grid is free. This will encapsulate logic similar to `GameLoop.is_area_free()` ([`src/core/game_loop.py`](src/core/game_loop.py:302)).
    *   The `Grid` might also provide methods to get valid neighbors for a given cell, which will be useful for A*.

2.  **`GameLoop` Class Modifications ([`src/core/game_loop.py`](src/core/game_loop.py)):**
    *   Instead of creating and managing `occupancy_grid` directly, `GameLoop` will initialize the occupancy data *within* its `Grid` instance (e.g., `self.grid.initialize_occupancy(...)`).
    *   Calls to `update_occupancy` and `is_area_free` within `GameLoop` will now be delegated to the `self.grid` object (e.g., `self.grid.update_occupancy(...)`, `self.grid.is_area_free(...)`).
    *   `GameLoop` will no longer need to pass `occupancy_grid` to `AgentManager`.

3.  **`AgentManager` Class Modifications ([`src/agents/manager.py`](src/agents/manager.py)):**
    *   `AgentManager` will no longer receive or pass `occupancy_grid` to `Agent` instances. Agents will use their existing `self.grid` reference.

4.  **`Agent` Class Modifications ([`src/agents/agent.py`](src/agents/agent.py)):**
    *   Agents will no longer receive `occupancy_grid` in their constructor.
    *   To check for walkability or other grid-related information, agents will use their existing `self.grid` reference (which is an instance of the `Grid` class) and call its methods (e.g., `self.grid.is_walkable(x, y)`).

**Benefits of Refactoring:**

*   **Improved Encapsulation:** The `Grid` class becomes the single source of truth for grid occupancy information.
*   **Reduced Coupling:** `GameLoop`, `AgentManager`, and `Agent` are no longer directly dependent on the `occupancy_grid`'s specific implementation details.
*   **Enhanced Maintainability:** Changes to how occupancy is stored or calculated will primarily affect only the `Grid` class.

### Part 2: A* Pathfinding Implementation Plan

Once the `occupancy_grid` refactoring is complete, we can proceed with implementing the A* pathfinding algorithm.

**1. New Module Creation:**

*   A new Python module will be created at [`src/pathfinding/astar.py`](src/pathfinding/astar.py). This module will house all A*-related logic.

**2. A* Algorithm Core:**

*   The main A* function within [`src/pathfinding/astar.py`](src/pathfinding/astar.py) will have a signature similar to:
    ```python
    def find_path(start_pos: pygame.math.Vector2, end_pos: pygame.math.Vector2, grid: Grid) -> list[pygame.math.Vector2] | None:
        # A* implementation here
        pass
    ```
*   The algorithm will utilize the `grid` object (an instance of the refactored `Grid` class) to:
    *   Determine if a cell is walkable (e.g., `grid.is_walkable(x, y)`).
    *   Get valid neighboring cells for path exploration.
*   The path will be returned as a list of `pygame.math.Vector2` objects, representing grid coordinates from start to end. If no path is found, it will return `None`.

**3. `Agent` Class Integration ([`src/agents/agent.py`](src/agents/agent.py)):**

*   The `Agent` class will be modified to use the A* algorithm for movement.
*   When an agent receives a `target_position` (e.g., for a task):
    1.  It will call the `find_path` function from [`src/pathfinding/astar.py`](src/pathfinding/astar.py), passing its current grid position, the target grid position, and its `self.grid` reference.
    2.  The returned path (a list of grid coordinates) will be stored within the agent (e.g., `self.current_path`).
    3.  The existing `move_towards_current_target` method ([`src/agents/agent.py`](src/agents/agent.py:167)) will be significantly refactored or replaced. Instead of moving directly towards the final target, it will:
        *   Check if `self.current_path` exists and is not empty.
        *   Pop the next waypoint from `self.current_path`.
        *   Move the agent one step towards this waypoint.
        *   If the waypoint is reached, it will proceed to the next waypoint in the path.
        *   If the path is exhausted, the agent has reached its destination.

### Part 3: Understanding A* Core Concepts

To effectively implement and debug A*, it's crucial to understand its core components. We've already discussed "What is A* and Why Use It?". Let's delve into the next concepts:

**1. Nodes, Open List, and Closed List:**

*   **Node:** A fundamental unit in A*. Each node represents a potential step or state in the pathfinding process, typically corresponding to a cell on the grid. A node usually stores:
    *   Its position (e.g., grid coordinates).
    *   Its parent node (the node from which we reached this current node, used to reconstruct the path).
    *   Its `g_cost`, `h_cost`, and `f_cost` (explained below).

*   **Open List (or Frontier):** A data structure (often a priority queue) that stores nodes that have been discovered but not yet fully evaluated. The A* algorithm repeatedly selects the node with the lowest `f_cost` from the open list to explore next.

*   **Closed List (or Explored Set):** A data structure that stores nodes that have already been evaluated. This prevents the algorithm from processing the same node multiple times, avoiding cycles and redundant work.

**2. Cost Functions (G, H, F):**

These functions are at the heart of A*'s decision-making process.

*   **`g_cost` (Cost from Start):**
    *   This is the actual, known cost of the path from the starting node to the current node.
    *   For a grid, if movement is restricted to adjacent cells (horizontal, vertical, and optionally diagonal), `g_cost` is often calculated by summing the costs of moving between cells. For example, moving to an adjacent horizontal/vertical cell might cost 1, and a diagonal move might cost 1.4 (approx. sqrt(2)).
    *   `g_cost(current_node) = g_cost(parent_node) + cost_to_move(parent_node, current_node)`

*   **`h_cost` (Heuristic Cost to Goal):**
    *   This is an *estimated* cost from the current node to the goal node. The quality of the heuristic is critical for A*'s efficiency.
    *   **Admissibility:** A heuristic is "admissible" if it *never overestimates* the actual cost to reach the goal. If the heuristic is admissible, A* is guaranteed to find the shortest path (assuming non-negative edge costs).
    *   **Common Heuristics for Grids:**
        *   **Manhattan Distance:** `h = abs(current.x - goal.x) + abs(current.y - goal.y)`. Suitable when movement is restricted to cardinal directions (up, down, left, right). It's admissible in such cases.
        *   **Euclidean Distance:** `h = sqrt((current.x - goal.x)^2 + (current.y - goal.y)^2)`. The straight-line distance. It's admissible if any direction of movement is allowed.
        *   **Diagonal Distance (Chebyshev distance for grids allowing diagonal moves):** `h = max(abs(current.x - goal.x), abs(current.y - goal.y))` if diagonal moves have the same cost as cardinal moves. If diagonal moves cost more (e.g., 1.4 vs 1), a more complex heuristic like Octile distance is better.
    *   Choosing a good heuristic is a balance: a more accurate heuristic (closer to the true cost without overestimating) can make A* faster by guiding it more directly to the goal, but it might be more computationally expensive to calculate.

*   **`f_cost` (Total Estimated Cost):**
    *   This is the sum of `g_cost` and `h_cost`: `f_cost = g_cost + h_cost`.
    *   `f_cost` represents the estimated total cost of the cheapest path from the start node to the goal node *that passes through the current node*.
    *   A* always prioritizes exploring the node in the Open List that has the lowest `f_cost`.

**3. The A* Algorithm Loop (Simplified):**

1.  Initialize:
    *   Create the start node and the goal node.
    *   Add the start node to the Open List. Its `g_cost` is 0, and `h_cost` is calculated using the heuristic.
    *   The Closed List is initially empty.
2.  Loop while the Open List is not empty:
    a.  **Select Node:** Get the node with the lowest `f_cost` from the Open List. Let this be `current_node`.
    b.  **Goal Check:** If `current_node` is the goal node, reconstruct the path by backtracking from the goal node to the start node using the parent pointers stored in each node. Return this path.
    c.  **Move to Closed List:** Move `current_node` from the Open List to the Closed List (so it won't be processed again).
    d.  **Process Neighbors:** For each valid (walkable and not in the Closed List) neighbor of `current_node`:
        i.  Calculate the tentative `g_cost` to reach this neighbor through `current_node`.
        ii. If this neighbor is not in the Open List, or if the tentative `g_cost` is lower than its previously recorded `g_cost`:
            *   Set `current_node` as its parent.
            *   Update its `g_cost` to the new, lower tentative `g_cost`.
            *   Calculate its `h_cost` (if not already done).
            *   Calculate its `f_cost` (`g_cost + h_cost`).
            *   If the neighbor is not in the Open List, add it. Otherwise, update its information in the Open List (this might involve re-prioritizing it if using a priority queue).
3.  If the Open List becomes empty and the goal was not reached, it means there is no path from start to goal. Return `None`.

This diagram illustrates the flow:

```mermaid
graph TD
    A[Start] --> B{Initialize Open List with Start Node};
    B --> C{Open List Empty?};
    C -- No --> D[Get Node with Lowest F-Cost (CurrentNode)];
    D --> E{CurrentNode == Goal?};
    E -- Yes --> F[Reconstruct Path & Return];
    E -- No --> G[Move CurrentNode to Closed List];
    G --> H{For Each Neighbor of CurrentNode};
    H -- Valid & Not in Closed List --> I{Calculate Tentative G-Cost};
    I --> J{Neighbor in Open List AND Tentative G-Cost >= Neighbor's G-Cost?};
    J -- No --> K[Update Neighbor: Parent, G-Cost, H-Cost, F-Cost];
    K --> L{Neighbor in Open List?};
    L -- No --> M[Add Neighbor to Open List];
    L -- Yes --> N[Update Neighbor in Open List];
    M --> C;
    N --> C;
    J -- Yes --> H;
    H -- No More Neighbors / Invalid --> C;
    C -- Yes --> Z[No Path Found];
    F --> X[End];
    Z --> X;
```

### Part 4: Implementation Subtasks

The overall implementation can be broken down into these main subtasks:

1.  **Refactor `Grid` Class:**
    *   Modify [`src/rendering/grid.py`](src/rendering/grid.py) to encapsulate `occupancy_grid`.
    *   Implement `is_walkable`, `update_occupancy`, `is_area_free`, and other necessary helper methods within the `Grid` class.
    *   Update [`src/core/game_loop.py`](src/core/game_loop.py) to use the new `Grid` methods and remove direct `occupancy_grid` management.
    *   Update [`src/agents/manager.py`](src/agents/manager.py) and [`src/agents/agent.py`](src/agents/agent.py) to remove `occupancy_grid` passing and use `self.grid` for queries.

2.  **Create A* Module Structure:**
    *   Create the new file [`src/pathfinding/astar.py`](src/pathfinding/astar.py).
    *   Define the `Node` class (or a similar structure) within this module.
    *   Define the main `find_path` function signature.

3.  **Implement A* Core Logic:**
    *   Implement the Open List (e.g., using `heapq` for a priority queue) and Closed List (e.g., a set).
    *   Implement the cost calculation functions (`g_cost`, `h_cost` - choose an appropriate heuristic like Manhattan distance initially, `f_cost`).
    *   Implement the main A* loop as described above, including neighbor processing and path reconstruction.

4.  **Integrate A* into `Agent` Class:**
    *   Modify [`src/agents/agent.py`](src/agents/agent.py).
    *   Add logic for an agent to call `find_path` when a target is set.
    *   Store the returned path.
    *   Refactor or replace `move_towards_current_target` to follow the calculated path step-by-step.

### Conclusion and Next Steps

This plan outlines the refactoring of `occupancy_grid` management into the `Grid` class for better encapsulation, followed by the implementation of the A* pathfinding algorithm. The A* algorithm will enable agents to navigate the game world more intelligently.

The core A* concepts—Nodes, Open/Closed Lists, G/H/F costs, and the main algorithm loop—have been explained to provide a foundation for the implementation.