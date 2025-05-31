# Refactoring Plan: Decouple Agent and Task Modules

**Overall Goal:**
Refactor the `Agent` and `Task` classes so that `Task` objects direct `Agent` actions by calling specific methods on the `Agent`, rather than directly setting the `Agent`'s state. This will remove the need for `Task` modules to import `AgentState` from the `Agent` module, thus breaking the circular dependency.

---

**Phase 1: Modify `Agent` Class ([`src/agents/agent.py`](src/agents/agent.py:1))**

1.  **Refactor `_move_towards_target` Method:**
    *   Rename the method from `_move_towards_target(self, dt: float) -> bool` to `move_towards_current_target(self, dt: float) -> bool`.
    *   **Functionality:**
        *   It will continue to update `self.position` based on `self.speed`, `dt`, and `self.target_position`.
        *   It will return `True` if `self.target_position` is reached within the current `dt`.
        *   Upon reaching the target, it will set `self.target_position = None`.
        *   Crucially, it will **no longer change `self.state` directly.**

2.  **Add New Agent "Objective" Methods:**
    These methods will be called by `Task` objects (and by the `Agent` itself for non-task-driven state changes) to set the agent's current objective and corresponding state.
    *   `set_objective_idle(self)`:
        *   Sets `self.state = AgentState.IDLE`
        *   Sets `self.target_position = None`
    *   `set_objective_evaluating_tasks(self)`:
        *   Sets `self.state = AgentState.EVALUATING_TASKS`
        *   Sets `self.target_position = None`
    *   `set_objective_move_randomly(self)`:
        *   Sets `self.state = AgentState.MOVING_RANDOMLY`
        *   Sets `self.target_position = None` (the `_move_randomly` method will pick a specific random target)
    *   `set_objective_move_to_resource(self, target_node_position: pygame.math.Vector2)`:
        *   Sets `self.state = AgentState.MOVING_TO_RESOURCE`
        *   Sets `self.target_position = target_node_position`
    *   `set_objective_gather_resource(self, gathering_time: float)`:
        *   Sets `self.state = AgentState.GATHERING_RESOURCE`
        *   Sets `self.gathering_timer = gathering_time`
        *   Sets `self.target_position = None` (as the agent is at the resource)
    *   `set_objective_move_to_storage(self, storage_position: pygame.math.Vector2)`:
        *   Sets `self.state = AgentState.MOVING_TO_STORAGE`
        *   Sets `self.target_position = storage_position`
    *   `set_objective_deliver_resource(self, delivery_time: float)`:
        *   Sets `self.state = AgentState.DELIVERING_RESOURCE`
        *   Sets `self.delivery_timer = delivery_time`
        *   Sets `self.target_position = None` (as the agent is at the storage)
    *   Analogous methods for processor-related states:
        *   `set_objective_move_to_processor(self, processor_position: pygame.math.Vector2)`
        *   `set_objective_deliver_to_processor(self, delivery_time: float)`
        *   `set_objective_collect_from_processor(self, collection_time: float)`

3.  **Update `Agent.update()` Method:**
    *   The main `if self.current_task:` block will remain structurally similar, but the task itself will now call the new `agent.set_objective_...()` methods.
    *   The `else:` block (when `self.current_task is None`) will be modified to use the new objective methods for internal state transitions:
        *   When transitioning from `IDLE` to `EVALUATING_TASKS`, call `self.set_objective_evaluating_tasks()`.
        *   When `EVALUATING_TASKS` results in no suitable task or a failed claim, call `self.set_objective_idle()` or `self.set_objective_move_randomly()` as appropriate.
        *   The `_move_randomly(self, dt: float)` method will be updated:
            *   It will call `self.move_towards_current_target(dt)`.
            *   If `move_towards_current_target` returns `True` (random target reached), `_move_randomly` will then call `self.set_objective_idle()`.
    *   The fallback condition for unexpected states will also use `self.set_objective_idle()`.

4.  **Review Imports in `agent.py`:**
    *   The local import `from ..tasks.task import GatherAndDeliverTask` can likely become a top-level import.
    *   The local import `from ..tasks.task_types import TaskStatus` can also likely become a top-level import.
    *   The `TYPE_CHECKING` block for `Task` and `TaskManager` should remain.

---

**Phase 2: Modify `Task` Classes (Primarily `GatherAndDeliverTask` in [`src/tasks/task.py`](src/tasks/task.py:1))**

1.  **Remove Local Imports of `AgentState`:**
    *   Delete `from ..agents.agent import AgentState` from all methods within `GatherAndDeliverTask` (and any other task classes if they use it).

2.  **Modify `GatherAndDeliverTask.prepare()` Method:**
    *   Instead of directly setting `agent.state` and `agent.target_position`, use:
        `agent.set_objective_move_to_resource(self.target_resource_node_ref.position)`

3.  **Modify `GatherAndDeliverTask.execute_step()` Method:**
    *   **`move_to_resource` step:**
        *   If the agent's state needs to be (re)set, call `agent.set_objective_move_to_resource(self.target_resource_node_ref.position)`.
        *   Change the condition `if agent._move_towards_target(dt):` to `if agent.move_towards_current_target(dt):`.
        *   Upon arrival, call: `agent.set_objective_gather_resource(agent.config.DEFAULT_GATHERING_TIME)`
    *   **`gather_resource` step:**
        *   If state needs re-affirmation, call `agent.set_objective_gather_resource(...)`.
        *   After gathering logic, call: `agent.set_objective_move_to_storage(self.target_dropoff_ref.position)`
    *   **`move_to_dropoff` step:**
        *   If state needs re-affirmation, call `agent.set_objective_move_to_storage(...)`.
        *   Change `if agent._move_towards_target(dt):` to `if agent.move_towards_current_target(dt):`.
        *   Upon arrival, call: `agent.set_objective_deliver_resource(agent.config.DEFAULT_DELIVERY_TIME)`
    *   **`deliver_resource` step:**
        *   If state needs re-affirmation, call `agent.set_objective_deliver_resource(...)`.

4.  **Review Imports in `task.py`:**
    *   The `TYPE_CHECKING` block for `Agent` and `ResourceManager` should remain.
    *   Ensure no other top-level imports from `agent.py` exist that would re-introduce a cycle.

---

**Phase 3: Verification and Testing**

1.  After applying changes, thoroughly test the agent behavior for the `GatherAndDeliverTask` lifecycle.
2.  Verify that agents correctly transition through states as directed by the task.
3.  Confirm that agents correctly become idle and seek new tasks.
4.  Check for any `ImportError` exceptions.
5.  Observe debug logs to ensure state transitions and objective settings are happening as expected.

---

**Visual Plan: New Interaction Flow (Simplified)**

```mermaid
sequenceDiagram
    participant A as Agent
    participant T as Task
    participant TM as TaskManager

    Note over A: Agent is IDLE
    A->>A: set_objective_evaluating_tasks()
    A->>TM: get_available_tasks()
    TM-->>A: tasks_list
    A->>A: _evaluate_and_select_task()
    alt Task Chosen
        A->>TM: attempt_claim_task(chosen_task)
        TM-->>A: claimed_task (now A.current_task)
        A->>T: current_task.prepare(self, RM)
        T->>A: agent.set_objective_move_to_resource(pos)
        Note over A: Agent state is now MOVING_TO_RESOURCE
    end

    loop Task Execution
        A->>T: current_task.execute_step(self, dt, RM)
        alt Example: Reached Resource in Task
            T->>A: agent.set_objective_gather_resource(time)
            Note over A: Agent state is now GATHERING_RESOURCE
        end
        alt Example: Finished Gathering in Task
            T->>A: agent.set_objective_move_to_storage(pos)
            Note over A: Agent state is now MOVING_TO_STORAGE
        end
        T-->>A: task_status (e.g., IN_PROGRESS)
    end

    alt Task Finished (Completed/Failed)
         A->>T: current_task.cleanup()
         A->>TM: report_task_outcome()
         Note over A: current_task becomes None
         A->>A: set_objective_idle()
    end