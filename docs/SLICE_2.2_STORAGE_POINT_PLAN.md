# Plan: Add Berry Storage Point to Game Loop (Slice 2.2)

**Goal:** Instantiate a `StoragePoint` that accepts `BERRY` resources with a capacity of 20, and place it in the middle of the game screen. This involves modifying `src/core/game_loop.py`.

**Affected File:** `src/core/game_loop.py`

**Detailed Steps for `src/core/game_loop.py` Modifications:**

1.  **Import necessary classes:**
    *   At the top of the file, ensure these imports are present:
        ```python
        import pygame # Should already be there
        from pygame.math import Vector2 # Should already be there
        from src.core import config # Should already be there
        from src.resources.storage_point import StoragePoint
        from src.resources.resource_types import ResourceType
        # ... other existing imports
        ```

2.  **Create a new method `_spawn_initial_storage_points(self)` within the `GameLoop` class:**
    *   This method will be responsible for creating and registering storage points.
    *   The content of the method will be:
        ```python
        def _spawn_initial_storage_points(self):
            """Creates and places the initial storage points."""
            # Calculate middle of the screen in grid coordinates
            middle_screen_x_pixels = config.SCREEN_WIDTH / 2
            middle_screen_y_pixels = config.SCREEN_HEIGHT / 2
            middle_screen_pixel_pos = pygame.math.Vector2(middle_screen_x_pixels, middle_screen_y_pixels)
            storage_position_grid = self.grid.screen_to_grid(middle_screen_pixel_pos)

            # Define storage point properties
            capacity = 20  # Confirmed capacity
            accepted_types = [ResourceType.BERRY]

            # Create and add the storage point
            berry_storage_point = StoragePoint(
                position=storage_position_grid,
                overall_capacity=capacity,
                accepted_resource_types=accepted_types
            )
            # Assumes add_storage_point method exists in ResourceManager as per SLICE_2.2_PLAN.md
            self.resource_manager.add_storage_point(berry_storage_point) 
            print(f"DEBUG: Spawned StoragePoint at grid_pos: {storage_position_grid} for BERRY with capacity {capacity}")
        ```

3.  **Call the new method in `GameLoop.__init__`:**
    *   Locate the `__init__` method of the `GameLoop` class.
    *   After the line `self._spawn_initial_resources()` and before `self.agent_manager = AgentManager(...)` (or a similar logical placement after resource manager initialization), add the call:
        ```python
        # Inside GameLoop.__init__
        # ...
        self._spawn_initial_resources()
        self._spawn_initial_storage_points() # <-- Add this line
        self.agent_manager = AgentManager(grid=self.grid)
        # ...
        ```

4.  **Ensure `ResourceManager` can draw storage points (Consideration for Implementation Phase):**
    *   The `SLICE_2.2_PLAN.md` indicates `StoragePoint` has a `draw` method and `ResourceManager` will maintain a list `self.storage_points`.
    *   During implementation, ensure that `ResourceManager.draw_nodes()` (or a new `ResourceManager.draw_storage_points()` method) is updated to iterate through `self.storage_points` and call their `draw` methods. This method is called from `GameLoop.render()`.
    *   Example (conceptual, actual implementation in `ResourceManager`):
        ```python
        # In ResourceManager.draw_nodes (or a new draw_storage_points method)
        # for storage_point in self.storage_points:
        #     storage_point.draw(screen, grid)
        ```

**Mermaid Diagram of Proposed Change in `GameLoop`:**

```mermaid
graph TD
    A[GameLoop.__init__] --> B{Initialize ResourceManager};
    B --> C{_spawn_initial_resources};
    C --> D{_spawn_initial_storage_points (New Method)};
    D --> E{Calculate Middle Screen Position};
    E --> F{Convert to Grid Coordinates};
    F --> G{Instantiate StoragePoint (BERRY, capacity=20)};
    G --> H{resource_manager.add_storage_point};
    A --> I{Initialize AgentManager};
    I --> J{_spawn_initial_agents};

    subgraph GameLoop.render
        K[Draw Grid]
        L[resource_manager.draw_nodes (includes bushes)]
        M[resource_manager.draw_storage_points (or integrated into draw_nodes)]
        N[agent_manager.render_agents]
    end
    A --> K;
    A --> L;
    A --> M;
    A --> N;