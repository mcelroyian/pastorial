# Implementation Plan: Agent Resource Gathering & Targeting Enhancements

This plan integrates the solutions for "Problem 1: Agents Gather Resources Even if Storage is Full" and "Problem 2: Multiple Agents Target the Same Resource Node" as detailed in [`RESOURCE_TARGET_PLAN.md`](RESOURCE_TARGET_PLAN.md).

## Phase 1: Enhance `ResourceNode` for Reservation

**File:** [`src/resources/node.py`](src/resources/node.py)

1.  **Add `is_targeted` attribute to `ResourceNode.__init__`:**
    *   Modify the `__init__` method to include `self.is_targeted: bool = False`.
    ```python
    # In src/resources/node.py, within the ResourceNode class:
    class ResourceNode(ABC):
        def __init__(self, position: pygame.Vector2, capacity: int, generation_rate: float, resource_type: ResourceType):
            # ... existing initializations ...
            self.current_quantity = 0.0
            
            # --- NEW ATTRIBUTE for reservation ---
            self.is_targeted: bool = False
    ```

2.  **Implement `claim(self) -> bool` method in `ResourceNode`:**
    *   Add the `claim` method as specified in [`RESOURCE_TARGET_PLAN.md#L166-L173`](RESOURCE_TARGET_PLAN.md:166).
    ```python
    # In src/resources/node.py, within the ResourceNode class:
    
        # --- NEW METHODS for reservation ---
        def claim(self) -> bool:
            """Attempts to claim this resource node. Returns True if successful, False otherwise."""
            if not self.is_targeted:
                self.is_targeted = True
                # print(f"DEBUG: Node {self.position} claimed.") # Optional debug
                return True
            # print(f"DEBUG: Node {self.position} FAILED to claim (already targeted).") # Optional debug
            return False
    ```

3.  **Implement `release(self)` method in `ResourceNode`:**
    *   Add the `release` method as specified in [`RESOURCE_TARGET_PLAN.md#L175-L181`](RESOURCE_TARGET_PLAN.md:175).
    ```python
    # In src/resources/node.py, within the ResourceNode class:
    
        def release(self):
            """Releases the claim on this resource node."""
            if self.is_targeted:
                self.is_targeted = False
                # print(f"DEBUG: Node {self.position} released.") # Optional debug
            # else:
                # print(f"DEBUG: Node {self.position} release called but was not targeted.") # Optional debug
    ```
    *   Ensure necessary imports like `pygame` and `ResourceType` are present (they appear to be already).

## Phase 2: Integrate Reservation and Pre-Gathering Checks into `Agent` Logic

**File:** [`src/agents/agent.py`](src/agents/agent.py)

1.  **Modify `_find_best_resource_target` method:**
    *   Integrate the logic from [`RESOURCE_TARGET_PLAN.md#L199-L249`](RESOURCE_TARGET_PLAN.md:199) to check `node.is_targeted` and call `node.claim()`.

2.  **Modify `Agent.update` method - `IDLE` state:**
    *   Replace the current `IDLE` state block with the refined logic from [`RESOURCE_TARGET_PLAN.md#L364-L433`](RESOURCE_TARGET_PLAN.md:364). This refined logic incorporates:
        *   Releasing any previous target if an agent unexpectedly returns to `IDLE`.
        *   Checking inventory: if not empty, transition to `CARRYING_RESOURCE`.
        *   If inventory is empty:
            *   Iterate through `self.resource_priorities`.
            *   For each `res_type_priority`:
                *   Get candidate nodes (available quantity, not `is_targeted`).
                *   Sort candidates by distance (optional, but good practice).
                *   For each `potential_node` in sorted candidates:
                    *   Call `self._can_find_dropoff_for_resource(potential_node.resource_type, 1, resource_manager)`.
                    *   If a drop-off exists, attempt `potential_node.claim()`.
                    *   If claimed successfully, this `potential_node` becomes `chosen_node_to_gather`. Break from loops.
            *   If `chosen_node_to_gather` is found:
                *   Set `self.target_resource_node = chosen_node_to_gather`.
                *   Set `self.target_position`.
                *   Change `self.state` to `AgentState.MOVING_TO_RESOURCE`.
            *   Else (no suitable raw resource found):
                *   Attempt to find a processed good to collect (e.g., `FLOUR_POWDER`), including a `_can_find_dropoff_for_resource` check for it.
                *   If successful, set target and state to `MOVING_TO_PROCESSOR`.
            *   Else (no tasks found):
                *   Change `self.state` to `AgentState.MOVING_RANDOMLY`.

3.  **Modify `Agent.update` method - Other State Transitions for Releasing Claims:**
    *   **`IDLE` state (entry):**
        *   As per [`RESOURCE_TARGET_PLAN.md#L262-L266`](RESOURCE_TARGET_PLAN.md:262) and refined logic [`RESOURCE_TARGET_PLAN.md#L366-L370`](RESOURCE_TARGET_PLAN.md:366). If `self.target_resource_node` exists, call `release()` and set it to `None`.
    *   **`MOVING_TO_RESOURCE` state:**
        *   As per [`RESOURCE_TARGET_PLAN.md#L284-L294`](RESOURCE_TARGET_PLAN.md:284).
        *   If `self.target_resource_node` is `None` or `self.target_position` is `None`: release node (if any), set state to `IDLE`.
        *   If `self.target_resource_node.current_quantity <= 0` (target depleted): release node, set state to `IDLE`.
    *   **`GATHERING_RESOURCE` state:**
        *   As per [`RESOURCE_TARGET_PLAN.md#L302-L332`](RESOURCE_TARGET_PLAN.md:302).
        *   If `self.target_resource_node` is `None`: set state to `IDLE`.
        *   If `self.target_resource_node.current_quantity <= 0` (depleted during gathering): release node, set state to `CARRYING_RESOURCE`.
        *   After gathering is complete (timer <= 0): release `self.target_resource_node`, set it to `None`, and transition to `CARRYING_RESOURCE`.

## Visual Plan: Mermaid Diagram

```mermaid
classDiagram
    class Agent {
        +state: AgentState
        +target_resource_node: Optional~ResourceNode~
        +resource_priorities: List~ResourceType~
        +current_inventory: Dict
        +update(dt, resource_manager)
        -_find_best_resource_target(resource_manager) Optional~ResourceNode~
        -_can_find_dropoff_for_resource(resource_type, quantity, resource_manager) bool
    }
    class ResourceNode {
        +position: Vector2
        +resource_type: ResourceType
        +current_quantity: float
        +is_targeted: bool  // New
        +claim() bool      // New
        +release()         // New
        +collect_resource(amount) int
    }
    class ResourceManager {
        +nodes: List~ResourceNode~
        +storage_points: List~StoragePoint~
        +processing_stations: List~ProcessingStation~
        +get_nodes_by_type(resource_type) List~ResourceNode~
        +get_nearest_station_accepting(position, resource_type) Optional~ProcessingStation~
        +get_stations_with_output(resource_type) List~ProcessingStation~
    }
    class StoragePoint {
        +can_accept(resource_type, quantity) bool
    }
    class ProcessingStation {
        +can_accept_input(resource_type, quantity) bool
        +has_output() bool
    }

    Agent --|> ResourceManager : uses
    Agent --|> ResourceNode : targets
    Agent --|> StoragePoint : uses for dropoff
    Agent --|> ProcessingStation : uses for dropoff/pickup
    ResourceManager o-- ResourceNode
    ResourceManager o-- StoragePoint
    ResourceManager o-- ProcessingStation

stateDiagram-v2
    [*] --> IDLE
    IDLE --> MOVING_TO_RESOURCE : Found & Claimed Node\nAND Dropoff Exists
    IDLE --> MOVING_TO_PROCESSOR : Found Output & Dropoff Exists
    IDLE --> CARRYING_RESOURCE : Has Inventory
    IDLE --> MOVING_RANDOMLY : No suitable task

    MOVING_TO_RESOURCE --> GATHERING_RESOURCE : Reached Node
    MOVING_TO_RESOURCE --> IDLE : Target Invalid (Release Node)
    
    GATHERING_RESOURCE --> CARRYING_RESOURCE : Finished/Interrupted (Release Node)
    GATHERING_RESOURCE --> IDLE : Target Invalid (Release Node)

    CARRYING_RESOURCE --> MOVING_TO_STORAGE : Found Storage
    CARRYING_RESOURCE --> MOVING_TO_PROCESSOR : Found Processor for Input
    CARRYING_RESOURCE --> IDLE : Inventory Empty
    CARRYING_RESOURCE --> MOVING_RANDOMLY : No Dropoff

    MOVING_TO_STORAGE --> DELIVERING_RESOURCE
    DELIVERING_RESOURCE --> IDLE : Delivered
    DELIVERING_RESOURCE --> CARRYING_RESOURCE : Delivery Failed/Partial

    MOVING_TO_PROCESSOR --> DELIVERING_TO_PROCESSOR : Reached (to deliver input)
    MOVING_TO_PROCESSOR --> COLLECTING_FROM_PROCESSOR : Reached (to collect output)
    MOVING_TO_PROCESSOR --> IDLE : Target Invalid

    DELIVERING_TO_PROCESSOR --> IDLE : Delivered
    DELIVERING_TO_PROCESSOR --> CARRYING_RESOURCE : Delivery Failed

    COLLECTING_FROM_PROCESSOR --> CARRYING_RESOURCE : Collected
    COLLECTING_FROM_PROCESSOR --> IDLE : Collection Failed
    
    MOVING_RANDOMLY --> IDLE : Reached Random Target