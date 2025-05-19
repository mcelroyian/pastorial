# Plan: Implement Wheat Processing Task (Retrieve from Storage, Deliver to Mill)

**Objective:** Create a task where an agent retrieves Wheat from a StoragePoint and delivers it to a Mill. The agent is then free, and the Mill processes the Wheat autonomously. A separate task (`COLLECT_PROCESSED_AND_DELIVER`) will handle picking up the Flour later.

## I. Define Task Type & Statuses ([`src/tasks/task_types.py`](src/tasks/task_types.py:1))
*   **TaskType Enum:** Use existing `TaskType.PROCESS_RESOURCE`.
*   **TaskStatus Enum:** Ensure statuses cover (or add new ones for):
    *   `IN_PROGRESS_MOVE_TO_STORAGE` (Agent moving to the StoragePoint containing Wheat)
    *   `IN_PROGRESS_COLLECTING_FROM_STORAGE` (Agent at StoragePoint, collecting Wheat)
    *   `IN_PROGRESS_MOVE_TO_PROCESSOR` (Agent moving to the Mill)
    *   `IN_PROGRESS_DELIVERING_TO_PROCESSOR` (Agent at the Mill, transferring Wheat)

## II. Modify `StoragePoint` ([`src/resources/storage_point.py`](src/resources/storage_point.py:8)) (Potential New Methods)
To support agents collecting specific resources for tasks, `StoragePoint` might need:
1.  **`has_resource(self, resource_type: ResourceType, quantity: int) -> bool`**: Checks if a specific quantity of a resource is physically available (not just reserved for dropoff).
2.  **`reserve_for_pickup(self, task_id: uuid.UUID, resource_type: ResourceType, quantity: int) -> int`**: Allows a task to reserve a certain amount of *existing* stock for an agent to pick up. Returns actual quantity reserved.
3.  **`collect_reserved_pickup(self, task_id: uuid.UUID, agent_inventory_space: int) -> Tuple[Optional[ResourceType], int]`**: Agent collects the resources reserved by `task_id`, up to `agent_inventory_space`. Returns the resource type and quantity collected. Releases the pickup reservation.
4.  **`release_pickup_reservation(self, task_id: uuid.UUID)`**: Releases a previously made pickup reservation if the task is cancelled or fails before collection.

## III. Create `DeliverWheatToMillTask` Class ([`src/tasks/task.py`](src/tasks/task.py:17))
1.  **Class Definition:**
    *   `DeliverWheatToMillTask(Task)`
    *   `__init__(self, priority: int, quantity_to_retrieve: int, target_storage_id: Optional[uuid.UUID] = None, target_processor_id: Optional[uuid.UUID] = None)`:
        *   `self.resource_to_retrieve: ResourceType = ResourceType.WHEAT`
        *   `self.quantity_to_retrieve: int = quantity_to_retrieve`
        *   `super().__init__(task_type=TaskType.PROCESS_RESOURCE, priority=priority)`
    *   Internal attributes:
        *   `self.target_storage_ref: Optional['StoragePoint'] = None`
        *   `self.target_processor_ref: Optional['ProcessingStation'] = None` (Mill)
        *   `self.quantity_retrieved: int = 0`
        *   `self.quantity_delivered_to_processor: int = 0`
        *   `self.reserved_at_storage_for_pickup_quantity: int = 0`
        *   `self._current_step_key: str` (e.g., "find_storage_and_mill", "move_to_storage", "collect_from_storage", "move_to_mill", "deliver_to_mill")

2.  **`prepare(self, agent: 'Agent', resource_manager: 'ResourceManager') -> bool` Method:**
    *   Set `self.status = TaskStatus.PREPARING`.
    *   **Constraint:** `if agent.current_inventory['quantity'] > 0: self.status = TaskStatus.FAILED; self.error_message = "Agent inventory not empty."; return False`
    *   **Find StoragePoint with Wheat:**
        *   If `self.target_storage_id` is not set, find the nearest `StoragePoint` that `has_resource(ResourceType.WHEAT, 1)`.
        *   Attempt to `reserve_for_pickup()` the required `self.quantity_to_retrieve` (or up to agent capacity). Store in `self.target_storage_ref` and update `self.reserved_at_storage_for_pickup_quantity`.
    *   **Find Mill:**
        *   If `self.target_processor_id` is not set, find the nearest `Mill` that `can_accept_input(ResourceType.WHEAT)` and has space. Store in `self.target_processor_ref`.
    *   **Validation:** If no suitable StoragePoint or Mill is found/reserved, set `self.error_message`, `self.status = TaskStatus.FAILED`, release any partial reservations, and return `False`.
    *   **Success:** Set `self.status = TaskStatus.IN_PROGRESS_MOVE_TO_STORAGE`, `self._current_step_key = "move_to_storage"`, `agent.set_objective_move_to_storage(self.target_storage_ref.position)`, and return `True`.

3.  **`execute_step(self, agent: 'Agent', dt: float, resource_manager: 'ResourceManager') -> TaskStatus` Method:**
    *   Implement a state machine:
        *   **"move_to_storage"**: Agent moves. If reached: `self._current_step_key = "collect_from_storage"`, `self.status = TaskStatus.IN_PROGRESS_COLLECTING_FROM_STORAGE`, `agent.set_objective_collect_from_storage(agent.config.DEFAULT_COLLECTION_TIME_FROM_STORAGE)`.
        *   **"collect_from_storage"**: Agent's collection timer ticks down. When timer <= 0:
            *   `can_carry = agent.inventory_capacity - agent.current_inventory['quantity']`
            *   `amount_to_collect_this_trip = min(can_carry, self.reserved_at_storage_for_pickup_quantity - self.quantity_retrieved, self.quantity_to_retrieve - self.quantity_retrieved)`
            *   `resource_type, collected_qty = self.target_storage_ref.collect_reserved_pickup(self.task_id, amount_to_collect_this_trip)`
            *   Update `agent.current_inventory` and `self.quantity_retrieved`.
            *   If `self.quantity_retrieved >= self.quantity_to_retrieve` or agent inventory is full: `self._current_step_key = "move_to_mill"`, `self.status = TaskStatus.IN_PROGRESS_MOVE_TO_PROCESSOR`, `agent.set_objective_move_to_processor(self.target_processor_ref.position)`.
            *   Else (need more from storage, or storage ran out): Handle error or re-prepare. For now, assume one collection trip completes or fails.
        *   **"move_to_mill"**: Agent moves. If reached: `self._current_step_key = "deliver_to_mill"`, `self.status = TaskStatus.IN_PROGRESS_DELIVERING_TO_PROCESSOR`, `agent.set_objective_deliver_to_processor(agent.config.DEFAULT_DELIVERY_TIME)`.
        *   **"deliver_to_mill"**: Agent's delivery timer. When timer <= 0:
            *   `amount_to_deliver = agent.current_inventory['quantity']`.
            *   `delivered_to_mill = self.target_processor_ref.receive(ResourceType.WHEAT, amount_to_deliver)`.
            *   Update `agent.current_inventory` and `self.quantity_delivered_to_processor`.
            *   If `self.quantity_delivered_to_processor >= self.quantity_retrieved`: `self.status = TaskStatus.COMPLETED`.
    *   Return `self.status`.

4.  **`cleanup(self, agent: 'Agent', resource_manager: 'ResourceManager', success: bool)` Method:**
    *   If `self.target_storage_ref` and `self.reserved_at_storage_for_pickup_quantity > 0`, call `self.target_storage_ref.release_pickup_reservation(self.task_id, self.reserved_at_storage_for_pickup_quantity)`.

5.  **`get_target_description(self) -> str` Method:**
    *   Provide descriptions for each step.

## IV. Update Agent Logic ([`src/agents/agent.py`](src/agents/agent.py:21))
1.  **`AgentState` Enum:**
    *   Add `COLLECTING_FROM_STORAGE` or ensure `GATHERING_RESOURCE` can be reused.
2.  **New Agent Objective Method:**
    *   `set_objective_collect_from_storage(self, collection_time: float)`: Sets state to `AgentState.COLLECTING_FROM_STORAGE` (or `GATHERING_RESOURCE`) and starts `gathering_timer`.
3.  **`_evaluate_and_select_task()` Method:**
    *   When considering `TaskType.PROCESS_RESOURCE` (our `DeliverWheatToMillTask`):
        *   **Constraint:** `if self.current_inventory['quantity'] > 0: continue`.
        *   Check for `StoragePoint` with available `WHEAT` (e.g., iterate `resource_manager.storage_points` and check `sp.has_resource(ResourceType.WHEAT, 1)`).
        *   Check for `Mill` capacity.

## V. Update TaskManager ([`src/tasks/task_manager.py`](src/tasks/task_manager.py:16))
1.  **Import:** `DeliverWheatToMillTask`.
2.  **Creation Method:** `create_deliver_wheat_to_mill_task(self, quantity: int, priority: int) -> Optional[Task]`.
3.  **Task Generation Logic (`_generate_tasks_if_needed()`):**
    *   Add a new section for generating these tasks:
        *   Check current `FLOUR_POWDER` stock: `current_flour_stock = self.resource_manager_ref.get_global_resource_quantity(ResourceType.FLOUR_POWDER)`.
        *   If `current_flour_stock < config.MIN_FLOUR_STOCK_LEVEL`:
            *   Check if `WHEAT` is available in storage: `current_wheat_in_storage = self.resource_manager_ref.get_global_resource_quantity(ResourceType.WHEAT)`.
            *   Check if any `Mill` can accept `WHEAT`.
            *   Count active `PROCESS_RESOURCE` tasks for `WHEAT`.
            *   If conditions met and `active_process_wheat_tasks < config.MAX_ACTIVE_PROCESS_WHEAT_TASKS` and `current_wheat_in_storage >= config.PROCESS_WHEAT_TASK_QUANTITY`:
                *   `self.create_deliver_wheat_to_mill_task(quantity=config.PROCESS_WHEAT_TASK_QUANTITY, priority=config.PROCESS_WHEAT_TASK_PRIORITY)`.

## VI. Configuration ([`src/core/config.py`](src/core/config.py))
*   `MIN_FLOUR_STOCK_LEVEL = 20`
*   `PROCESS_WHEAT_TASK_QUANTITY = 10` (amount of wheat per task)
*   `PROCESS_WHEAT_TASK_PRIORITY = 75`
*   `MAX_ACTIVE_PROCESS_WHEAT_TASKS = 2`
*   `DEFAULT_COLLECTION_TIME_FROM_STORAGE = 2.0` (example, in seconds)

## VII. Mermaid Diagram of the Process

```mermaid
graph TD
    subgraph Agent Task Execution (DeliverWheatToMillTask)
        direction LR
        A1[Agent Idle (Empty Inventory)] --> A2{Evaluate Tasks};
        A2 -- Selects DeliverWheatToMillTask --> A3[Task Prepare: Find StoragePoint(Wheat) & Mill, Reserve Wheat for Pickup];
        A3 -- Success --> A4[Move to StoragePoint];
        A4 -- Reached --> A5[Collect Reserved Wheat from StoragePoint];
        A5 -- Collected --> A6[Move to Mill];
        A6 -- Reached --> A7[Deliver Wheat to Mill Input];
        A7 -- Delivered --> A8[Task Complete. Agent Free];
        A3 -- Fail (No Resources/Processor/Reservation) --> A9[Task Failed. Agent Idle];
    end

    subgraph TaskManager Task Generation
        direction LR
        TM1[Periodically Check Conditions] --> TM2{Flour Stock Low?};
        TM2 -- Yes --> TM3{Sufficient Wheat in Storage & Mill Capacity?};
        TM3 -- Yes --> TM4{Max Process Tasks Not Reached?};
        TM4 -- Yes --> TM5[Create DeliverWheatToMillTask];
    end

    subgraph Mill Operation (Autonomous)
        direction LR
        M1[Mill with Wheat in Input] --> M2[Mill Processes Wheat];
        M2 --> M3[Flour in Mill Output Buffer];
    end

    A7 -.-> M1;

    subgraph Future Task (Separate)
        direction LR
        F1[CollectProcessedAndDeliver Task for Flour] -.-> M3;
    end

    classDef agentAction fill:#SkyBlue,stroke:#000,stroke-width:1px;
    classDef taskManagerAction fill:#PaleGreen,stroke:#000,stroke-width:1px;
    classDef millAction fill:#Khaki,stroke:#000,stroke-width:1px;
    classDef futureAction fill:#LightCoral,stroke:#000,stroke-width:1px;

    class A1,A2,A3,A4,A5,A6,A7,A8,A9 agentAction;
    class TM1,TM2,TM3,TM4,TM5 taskManagerAction;
    class M1,M2,M3 millAction;
    class F1 futureAction;