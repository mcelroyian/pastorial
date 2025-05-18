# Plan to Implement Wheat Collection

This plan outlines the steps to implement wheat collection, following the pattern of existing berry collection, and ensuring berries and wheat can share the same primary storage points.

## 1. Update Configuration ([`core/config.py`](core/config.py))

Add the following new constants to define behavior for wheat collection tasks:

*   `MIN_WHEAT_STOCK_LEVEL = 40`
*   `WHEAT_GATHER_TASK_QUANTITY = 15`
*   `WHEAT_GATHER_TASK_PRIORITY = 4`
*   `MAX_ACTIVE_WHEAT_GATHER_TASKS = 2`

## 2. Modify Existing Storage Point in Game Loop ([`core/game_loop.py`](core/game_loop.py))

*   Navigate to the `_spawn_initial_storage_points` method (around line 558).
*   Locate the initialization of the `berry_storage_point`.
*   Modify its `accepted_resource_types`:
    *   Change from `[ResourceType.BERRY]` to `[ResourceType.BERRY, ResourceType.WHEAT]`.
*   Update its `overall_capacity`:
    *   Change the `capacity` variable used for this storage point from `20` to `25`.

## 3. Update Task Manager ([`tasks/task_manager.py`](tasks/task_manager.py))

*   In the `_generate_tasks_if_needed` method (around line 1775):
    *   After the existing berry task generation logic, add a new section to handle wheat task generation. This section will mirror the structure of the berry logic:
        1.  Retrieve the current global stock of wheat:
            `current_wheat_stock = self.resource_manager_ref.get_global_resource_quantity(ResourceType.WHEAT)`
        2.  Check if `current_wheat_stock` is less than `config.MIN_WHEAT_STOCK_LEVEL`.
        3.  If the stock is low, count the number of currently active (pending or assigned) `GatherAndDeliverTask`s for `ResourceType.WHEAT`.
        4.  If this count is less than `config.MAX_ACTIVE_WHEAT_GATHER_TASKS`, then create a new `GatherAndDeliverTask`:
            ```python
            self.create_gather_task(
                resource_type=ResourceType.WHEAT,
                quantity=config.WHEAT_GATHER_TASK_QUANTITY,
                priority=config.WHEAT_GATHER_TASK_PRIORITY
            )
            ```

## Visual Plan (Mermaid Diagram)

```mermaid
graph TD
    A[Start: Implement Wheat Collection] --> B(1. Update Configuration in core/config.py);
    B --> B1(Add MIN_WHEAT_STOCK_LEVEL = 40);
    B --> B2(Add WHEAT_GATHER_TASK_QUANTITY = 15);
    B --> B3(Add WHEAT_GATHER_TASK_PRIORITY = 4);
    B --> B4(Add MAX_ACTIVE_WHEAT_GATHER_TASKS = 2);

    A --> C(2. Modify Storage Point in core/game_loop.py);
    C --> C1(In _spawn_initial_storage_points method);
    C1 --> C2(Find 'berry_storage_point' creation);
    C2 --> C3(Update accepted_resource_types to [BERRY, WHEAT]);
    C2 --> C4(Update overall_capacity to 25);

    A --> D(3. Update Task Manager in tasks/task_manager.py);
    D --> D1(In _generate_tasks_if_needed method);
    D1 --> D2(Add new section for Wheat task generation);
    D2 --> D3(Get current_wheat_stock);
    D2 --> D4(If stock < MIN_WHEAT_STOCK_LEVEL:);
    D4 --> D5(Count active WHEAT GatherAndDeliverTasks);
    D5 --> D6(If count < MAX_ACTIVE_WHEAT_GATHER_TASKS:);
    D6 --> D7(Create new GatherAndDeliverTask for WHEAT);

    B4 --> E{Plan Ready};
    C4 --> E;
    D7 --> E;