# Plan: Implement Fully Dynamic Precomputed Spawn Points for Mills

This document outlines the plan to change the mill spawning logic in the game from fixed positions to a fully dynamic system based on precomputed available spawn points. This will ensure that the desired number of mills are spawned if space is available, rather than failing if specific hardcoded locations are occupied.

## Affected Files:

*   `src/core/config.py`: To add a configuration for the desired number of mills.
*   `src/core/game_loop.py`: To implement the new spawning logic and helper methods.
*   `src/resources/mill.py`: (Reference for `Mill.GRID_WIDTH` and `Mill.GRID_HEIGHT`)

## Detailed Plan:

1.  **Add Configuration for Desired Mills:**
    *   In `src/core/config.py`, add the following setting:
        ```python
        DESIRED_NUM_MILLS = 2 # Default desired number of mills
        ```

2.  **Create Helper Method `_find_available_spawn_points` in `GameLoop` (`src/core/game_loop.py`):**
    *   **Signature:** `_find_available_spawn_points(self, entity_grid_width: int, entity_grid_height: int) -> List[pygame.math.Vector2]`
    *   **Purpose:** To scan the entire game grid and identify all valid top-left coordinates where an entity of the given dimensions (`entity_grid_width`, `entity_grid_height`) can be placed without overlapping existing entities or going out of bounds.
    *   **Logic:**
        *   Initialize an empty list `available_spots`.
        *   Iterate `gy` from `0` to `config.GRID_HEIGHT - entity_grid_height`.
        *   Iterate `gx` from `0` to `config.GRID_WIDTH - entity_grid_width`.
        *   For each potential top-left coordinate `(gx, gy)`, call `self.is_area_free(gx, gy, entity_grid_width, entity_grid_height)`.
        *   If `is_area_free` returns `True`, add `pygame.math.Vector2(gx, gy)` to the `available_spots` list.
        *   Return the `available_spots` list.

3.  **Modify `_spawn_initial_resources()` in `src/core/game_loop.py`:**
    *   Remove or comment out the existing mill spawning logic (currently attempting to place mills at fixed `Vector2` positions).
    *   Implement the new dynamic spawning logic:
        ```python
        # --- Start of new Mill spawning logic (within _spawn_initial_resources) ---
        print(f"Attempting to spawn {config.DESIRED_NUM_MILLS} mills...")
        mill_width = Mill.GRID_WIDTH  # From src.resources.mill
        mill_height = Mill.GRID_HEIGHT # From src.resources.mill
        
        available_mill_spots = self._find_available_spawn_points(mill_width, mill_height)
        
        if not available_mill_spots:
            print(f"Warning: No available space found to spawn any mills of size {mill_width}x{mill_height}.")
        else:
            random.shuffle(available_mill_spots) # Shuffle for random placement from available spots
            
            spawned_mills_count = 0
            # Attempt to spawn up to the desired number of mills, or fewer if not enough spots
            for i in range(min(config.DESIRED_NUM_MILLS, len(available_mill_spots))):
                pos_vec = available_mill_spots[i] # Get a pre-validated spot
                gx, gy = int(pos_vec.x), int(pos_vec.y)
                
                # While _find_available_spawn_points should ensure freedom, a re-check can be a safeguard
                # if other entities could theoretically be placed between finding spots and this step.
                # For initial spawning, this is less likely to be an issue.
                # if self.is_area_free(gx, gy, mill_width, mill_height): # Optional re-check
                
                mill = Mill(pos_vec) # Position is top-left grid coordinates
                self.resource_manager.add_processing_station(mill)
                self.update_occupancy(mill, gx, gy, mill_width, mill_height, is_placing=True)
                print(f"DEBUG: Spawned Mill (size {mill_width}x{mill_height}) at grid_pos: {pos_vec}")
                spawned_mills_count += 1
                # else:
                #     print(f"Warning: Could not spawn Mill at pre-calculated free spot {pos_vec}. Area became occupied unexpectedly.")

            if spawned_mills_count < config.DESIRED_NUM_MILLS and len(available_mill_spots) > 0 :
                print(f"Warning: Successfully spawned {spawned_mills_count} out of {config.DESIRED_NUM_MILLS} desired mills due to limited available space.")
            elif spawned_mills_count > 0:
                 print(f"Successfully spawned {spawned_mills_count} mills.")
            # If spawned_mills_count is 0 and available_mill_spots was empty, the initial warning covers it.
        # --- End of new Mill spawning logic ---
        ```

## Visual Plan (Mermaid Diagram):

```mermaid
graph TD
    A[Start GameLoop._spawn_initial_resources] --> B{Read config.DESIRED_NUM_MILLS};
    B --> C[Call _find_available_spawn_points(Mill.GRID_WIDTH, Mill.GRID_HEIGHT)];
    C --> D{Receive list of available_spots};
    D -- No spots available --> E[Print Warning: No space for mills];
    D -- Spots available --> F[Shuffle available_spots list];
    F --> G{Loop up to min(DESIRED_NUM_MILLS, len(available_spots)) times};
    G -- Get spot --> H[Select next position from available_spots];
    H --> I[Create Mill instance at position];
    I --> J[Add Mill to ResourceManager];
    J --> K[Update Occupancy Grid using self.update_occupancy];
    K --> L[Print Spawn Confirmation Message];
    L --> G;
    G -- Loop finished --> M{Actual spawned_mills_count < DESIRED_NUM_MILLS?};
    M -- Yes (fewer spawned) --> N[Print Warning: Not all desired mills spawned due to space];
    M -- No (all spawned or no spots initially) --> O[Mill spawning process complete];
    N --> O;
    E --> O;

    subgraph _find_available_spawn_points
        direction LR
        S1[Start method with entity_width, entity_height] --> S2{Iterate all possible top-left (gx, gy) for entity};
        S2 -- For each (gx,gy) --> S3[Call self.is_area_free(gx, gy, entity_width, entity_height)];
        S3 -- Area is Free --> S4[Add (gx,gy) to list of free_spots];
        S4 --> S2;
        S3 -- Area Not Free --> S2;
        S2 -- All (gx,gy) checked --> S5[Return list of free_spots];
    end
```

## Next Steps:

After this plan is reviewed and approved, the implementation can proceed by switching to a development mode (e.g., "Code" mode).