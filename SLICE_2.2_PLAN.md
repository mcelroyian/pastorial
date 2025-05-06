## Final Plan: Epic 2, Slice 2.2 - Resource Collection

**Goal:** Implement the agent's ability to detect, gather, carry, and deliver resources to designated storage points. Agents will prioritize resources based on a list provided at creation, attempt to gather up to their inventory capacity, and deliver to storage points with overall capacity limits. Visual feedback will include state-based color changes and a simple icon when carrying resources.

**Key Files to Modify/Create:**

*   `src/agents/agent.py`: Extend `AgentState` enum, update `Agent` class methods and attributes.
*   `src/agents/manager.py` (potentially): For managing agents or helping with resource/storage lookup (e.g., providing access to `ResourceManager`).
*   `src/resources/node.py`: Modify to allow resource collection.
*   `src/resources/storage_point.py` (New File): Define the `StoragePoint` class.
*   `src/core/config.py`: For new global constants like gathering/delivery times and default agent inventory capacity.
*   A new file for `ResourceTypeEnum` (e.g., `src/resources/resource_types.py`) if not already implicitly defined or handled by strings.

**Detailed Steps:**

1.  **Define `ResourceTypeEnum` (e.g., `src/resources/resource_types.py`):**
    *   If not already present, create an enum for resource types (e.g., `BERRY`, `WHEAT`). This will be used for agent priorities, storage acceptance, etc.
    ```python
    # src/resources/resource_types.py
    from enum import Enum, auto

    class ResourceType(Enum):
        BERRY = auto()
        WHEAT = auto()
        # ... other types
    ```

2.  **Refactor `Agent._move_towards_target()` (`src/agents/agent.py`):**
    *   Modify `_move_towards_target(self, dt: float) -> bool`:
        *   The method should return `True` if the target is reached within this update cycle, `False` otherwise.
        *   It should **not** directly set `self.state = AgentState.IDLE`. It will just update `self.position` and clear `self.target_position` upon arrival.

3.  **Expand `AgentState` Enum (`src/agents/agent.py`):**
    *   Add new states: `MOVING_TO_RESOURCE`, `GATHERING_RESOURCE`, `CARRYING_RESOURCE`, `MOVING_TO_STORAGE`, `DELIVERING_RESOURCE`.
    *   Update `self.state_colors` in `Agent.__init__` for these new states.

4.  **Implement Agent Inventory & Attributes (`src/agents/agent.py`):**
    *   In `Agent.__init__(self, position, speed, grid, resource_priorities: list[ResourceType], inventory_capacity: int)`:
        *   `self.resource_priorities: list[ResourceType]` (passed during creation).
        *   `self.inventory_capacity: int` (passed during creation, or from `config`).
        *   `self.current_inventory: dict` (e.g., `{'resource_type': ResourceType | None, 'quantity': 0}`).
        *   `self.gathering_timer: float = 0.0`
        *   `self.delivery_timer: float = 0.0`
        *   `self.target_resource_node: ResourceNode | None = None`
        *   `self.target_storage_point: StoragePoint | None = None`

5.  **Implement `StoragePoint` Class (`src/resources/storage_point.py`):**
    *   Define `class StoragePoint:`
        *   `__init__(self, position: pygame.math.Vector2, overall_capacity: int, accepted_resource_types: list[ResourceType] | None = None)`
        *   Attributes: `self.position`, `self.overall_capacity`, `self.accepted_resource_types` (if `None`, accepts all), `self.stored_resources: dict[ResourceType, int]` (e.g., `{ResourceType.BERRY: 10}`).
        *   Methods:
            *   `add_resource(self, resource_type: ResourceType, quantity: int) -> int`: Adds resources, respects `accepted_resource_types` and `overall_capacity`. Returns actual quantity added.
            *   `get_current_load(self) -> int`: Returns total quantity of all stored resources.
    *   `ResourceManager` (in `src/resources/manager.py`) should maintain a list of these: `self.storage_points: list[StoragePoint]`.

6.  **Implement Resource/Storage Detection Logic (`src/agents/agent.py`):**
    *   `_find_best_resource_target(self, resource_manager) -> ResourceNode | None`:
        *   Iterates `self.resource_priorities`.
        *   Queries `resource_manager.get_nodes_by_type(resource_type)` (method to be added to `ResourceManager`).
        *   Uses pathfinding to find the nearest available (non-empty) node.
        *   Returns the `ResourceNode` object or `None`.
    *   `_find_best_storage_target(self, resource_manager) -> StoragePoint | None`:
        *   Queries `resource_manager.storage_points`.
        *   Finds nearest `StoragePoint` that can accept `self.current_inventory['resource_type']` and is not full.
        *   Returns the `StoragePoint` object or `None`.

7.  **Implement Agent State Logic in `Agent.update()` (`src/agents/agent.py`):**
    *   (Pass `resource_manager` and `agent_manager` if needed for lookups)
    *   **`IDLE`:**
        *   `self.target_resource_node = self._find_best_resource_target(resource_manager)`
        *   If `self.target_resource_node`:
            *   `self.target_position = self.target_resource_node.position`
            *   `self.state = AgentState.MOVING_TO_RESOURCE`
    *   **`MOVING_TO_RESOURCE`:**
        *   If `self.target_position` is `None` (e.g., resource depleted while en route), go `IDLE`.
        *   `reached = self._move_towards_target(dt)`
        *   If `reached`:
            *   `self.state = AgentState.GATHERING_RESOURCE`
            *   `self.gathering_timer = config.DEFAULT_GATHERING_TIME`
    *   **`GATHERING_RESOURCE`:**
        *   If `self.target_resource_node` is `None` or empty, go `IDLE`.
        *   `self.gathering_timer -= dt`
        *   If `self.gathering_timer <= 0`:
            *   `amount_to_gather = self.inventory_capacity - self.current_inventory['quantity']`
            *   `gathered_amount = self.target_resource_node.collect_resource(amount_to_gather)`
            *   If `gathered_amount > 0`:
                *   `self.current_inventory['resource_type'] = self.target_resource_node.resource_type` (assuming node has a type)
                *   `self.current_inventory['quantity'] += gathered_amount`
            *   `self.target_resource_node = None`
            *   `self.state = AgentState.CARRYING_RESOURCE`
    *   **`CARRYING_RESOURCE`:**
        *   If `self.current_inventory['quantity'] == 0`, go `IDLE`.
        *   `self.target_storage_point = self._find_best_storage_target(resource_manager)`
        *   If `self.target_storage_point`:
            *   `self.target_position = self.target_storage_point.position`
            *   `self.state = AgentState.MOVING_TO_STORAGE`
        *   Else (no suitable storage), go `IDLE` (or a new "WAITING_FOR_STORAGE" state).
    *   **`MOVING_TO_STORAGE`:**
        *   If `self.target_position` is `None` (e.g., storage became full/invalid), go `CARRYING_RESOURCE` to re-evaluate.
        *   `reached = self._move_towards_target(dt)`
        *   If `reached`:
            *   `self.state = AgentState.DELIVERING_RESOURCE`
            *   `self.delivery_timer = config.DEFAULT_DELIVERY_TIME`
    *   **`DELIVERING_RESOURCE`:**
        *   If `self.target_storage_point` is `None`, go `CARRYING_RESOURCE`.
        *   `self.delivery_timer -= dt`
        *   If `self.delivery_timer <= 0`:
            *   `delivered_amount = self.target_storage_point.add_resource(self.current_inventory['resource_type'], self.current_inventory['quantity'])`
            *   `self.current_inventory['quantity'] -= delivered_amount`
            *   If `self.current_inventory['quantity'] <= 0`:
                *   `self.current_inventory['resource_type'] = None`
                *   `self.current_inventory['quantity'] = 0`
            *   `self.target_storage_point = None`
            *   `self.state = AgentState.IDLE` (or `CARRYING_RESOURCE` if still has items)

8.  **Modify `ResourceNode` (`src/resources/node.py`):**
    *   Ensure it has `self.resource_type: ResourceType`.
    *   Add `collect_resource(self, amount_to_collect: int) -> int`: Reduces internal resource count by `amount_to_collect` (or less if not enough available), returns actual amount collected.

9.  **Update `ResourceManager` (`src/resources/manager.py`):**
    *   Add `self.storage_points: list[StoragePoint] = []`.
    *   Add `add_storage_point(self, storage_point: StoragePoint)`.
    *   Add `get_nodes_by_type(self, resource_type: ResourceType) -> list[ResourceNode]`.

10. **Implement Visual Feedback (`src/agents/agent.py`):**
    *   In `Agent.draw()`:
        *   Use `self.state_colors` as before.
        *   If `self.current_inventory['quantity'] > 0`:
            *   Draw a small colored circle (e.g., using `config.RESOURCE_VISUAL_COLORS[self.current_inventory['resource_type']]`) above the agent.

11. **Configuration (`src/core/config.py`):**
    *   Add:
        *   `DEFAULT_GATHERING_TIME = 2.0` (seconds)
        *   `DEFAULT_DELIVERY_TIME = 1.0` (seconds)
        *   `DEFAULT_AGENT_INVENTORY_CAPACITY = 5`
        *   `RESOURCE_VISUAL_COLORS = {ResourceType.BERRY: (255,0,0), ResourceType.WHEAT: (200,200,0)}`

**Mermaid Diagram for Agent State Transitions:**
```mermaid
graph TD
    IDLE -->|Found Resource Target| MOVING_TO_RESOURCE;
    MOVING_TO_RESOURCE -- Reached Resource --> GATHERING_RESOURCE;
    MOVING_TO_RESOURCE -- Target Invalid --> IDLE;
    GATHERING_RESOURCE -- Gathering Complete & Has Resource --> CARRYING_RESOURCE;
    GATHERING_RESOURCE -- Resource Empty/Problem --> IDLE;
    CARRYING_RESOURCE -->|Found Storage Target| MOVING_TO_STORAGE;
    CARRYING_RESOURCE -- No Resource to Carry --> IDLE;
    CARRYING_RESOURCE -- No Storage Target --> IDLE; %% Or a new WAITING_FOR_STORAGE state
    MOVING_TO_STORAGE -- Reached Storage --> DELIVERING_RESOURCE;
    MOVING_TO_STORAGE -- Target Invalid --> CARRYING_RESOURCE;
    DELIVERING_RESOURCE -- Delivery Complete --> IDLE;
    DELIVERING_RESOURCE -- Still Carrying Items --> CARRYING_RESOURCE;
    DELIVERING_RESOURCE -- Target Invalid --> CARRYING_RESOURCE;

    subgraph Agent States
        IDLE
        MOVING_TO_RESOURCE
        GATHERING_RESOURCE
        CARRYING_RESOURCE
        MOVING_TO_STORAGE
        DELIVERING_RESOURCE
    end