# Agent State Machine Refactoring Plan

**Date:** 2025-05-31

**Objective:** Analyze the current agent state machine, its interactions with the task system and pathfinding, and propose a plan for simplification or extraction to improve clarity, maintainability, and reduce debugging complexity.

## 1. Analysis of Current State Machine & Weaknesses

Based on the review of `src/agents/agent_defs.py`, `src/agents/agent.py`, and `src/tasks/task.py`:

*   **Current Structure:**
    *   Agent states are defined in an `Enum` (`AgentState`).
    *   Tasks (e.g., `GatherAndDeliverTask`, `DeliverWheatToMillTask`) directly manipulate the agent's state by calling methods like `agent.set_objective_move_to_resource()`, `agent.set_objective_gather_resource()`, etc., primarily within their `prepare()` and `execute_step()` methods.
    *   The agent's `update()` method contains a large conditional block that:
        *   If a `current_task` exists, it calls `current_task.execute_step()`. The task's `execute_step()` then further directs the agent's state for the next phase of the task.
        *   If no `current_task` exists, the agent transitions itself through `IDLE` -> `EVALUATING_TASKS` -> (potentially) `MOVING_RANDOMLY`.
    *   Pathfinding is initiated by `agent.set_target()`, which is called by the various `set_objective_...` methods. The `_follow_path()` method handles movement along the path.
    *   Timers for actions like gathering or delivering are managed directly within the agent's `update()` loop based on its current state, but the duration is often set by the task or a default config.

*   **Identified Weaknesses & Pain Points:**
    *   **Tight Coupling:** Tasks are tightly coupled to the agent's specific state implementation.
    *   **Blurred Responsibilities:** Responsibility for state transitions is split between tasks and the agent.
    *   **Complex Conditional Logic:** Agent's `update()` and task's `execute_step()` methods rely on extensive conditional logic.
    *   **Implicit State Dependencies:** Task step success often implicitly depends on the agent correctly reaching a state set previously.
    *   **Debugging Complexity:** Difficult to determine if issues lie in task logic, agent state management, or pathfinding.
    *   **State Proliferation Risk:** Direct state setting by tasks can lead to a need for more specific states as task complexity grows.

## 2. Proposed Refactoring Strategy: Hybrid Approach (Task Intents & Agent-Managed States)

This approach aims for a balance between decoupling tasks from the agent's internal workings and avoiding an overly complex agent.

*   **Core Idea:**
    1.  **Tasks Define "Intents":** Tasks communicate high-level goals or "intents" to the agent.
    2.  **Agent Manages Its Own States:** The agent becomes responsible for interpreting these intents and managing its own internal state transitions (using a formal State pattern) to achieve them.
    3.  **Clear Interface:** A well-defined interface (e.g., `Intent` classes) for task-agent communication.

*   **Proposed Architecture (Option C - Hybrid):**

    ```mermaid
    graph TD
        TaskManager -- Assigns Task --> AgentInterface
        Task -- Creates & Submits --> Intent

        subgraph Agent [Agent]
            AgentInterface -- Receives --> IntentProcessor
            IntentProcessor -- Manages --> CurrentAgentStateBehavior
            CurrentAgentStateBehavior -- Uses --> PathfindingService
            CurrentAgentStateBehavior -- Updates --> AgentProperties[Position, Inventory, etc.]
            PathfindingService -- Returns Path/Status --> CurrentAgentStateBehavior

            subgraph AgentInternalStates [Formal State Pattern]
                IdleStateBehavior((IdleState))
                MovingStateBehavior((MovingState))
                InteractingStateBehavior((InteractingState))
                PathFailedStateBehavior((PathFailedState))
                EvaluatingIntentStateBehavior((EvaluatingIntentState))
            end
            IntentProcessor --> EvaluatingIntentStateBehavior
            EvaluatingIntentStateBehavior --> MovingStateBehavior
            MovingStateBehavior --> InteractingStateBehavior
            MovingStateBehavior --> PathFailedStateBehavior
            InteractingStateBehavior --> IdleStateBehavior
            PathFailedStateBehavior --> IdleStateBehavior
            IdleStateBehavior --> EvaluatingIntentStateBehavior
        end

        Intent -- Contains --> GoalDetails[Target, ResourceType, etc.]
        AgentInterface -- Reports Status --> Task

        style Agent fill:#f9f,stroke:#333,stroke-width:2px
        style Task fill:#ccf,stroke:#333,stroke-width:2px
        style TaskManager fill:#ccf,stroke:#333,stroke-width:2px
        style AgentInternalStates fill:#lightgrey,stroke:#333,stroke-width:1px
    ```

    *   **`Task`:**
        *   No longer calls `agent.set_objective_...()`.
        *   `prepare()`: Determines necessary steps, might create `Intent` objects.
        *   `execute_step()`: Checks `Intent` status via `AgentInterface`. Submits next `Intent` or marks task status.
        *   Example `Intent` objects: `MoveIntent(target_position)`, `GatherIntent(resource_node_ref, quantity_to_gather)`, `DeliverIntent(item_in_inventory, dropoff_ref, quantity_to_deliver)`.
    *   **`Agent` (`AgentInterface` & `IntentProcessor`):**
        *   `AgentInterface`: Methods for tasks to submit `Intents` (e.g., `agent.submit_intent(intent_object)`) and query status (e.g., `agent.get_intent_status(intent_id)`).
        *   `IntentProcessor`: Receives `Intents`, determines appropriate internal agent state behavior.
        *   **Internal State Behaviors (State Pattern):** Classes like `IdleStateBehavior`, `MovingStateBehavior`, `InteractingStateBehavior`, `PathFailedStateBehavior` with `enter()`, `update(dt)`, `exit()` methods.
    *   **Pathfinding Interaction:**
        *   Requested by state behaviors (e.g., `MovingStateBehavior.enter()`).
        *   `_follow_path()` returns detailed status: `WAYPOINT_REACHED`, `PATH_COMPLETED`, `STILL_MOVING`, `NO_PATH_PROGRESS`.
        *   `MovingStateBehavior` uses this status for decisions.

## 3. How Proposed Changes Address Complexities

*   **Clearer Separation of Concerns:** Tasks define *what*, agents define *how*.
*   **Reduced Coupling:** Tasks use a stable `Intent` interface.
*   **Simplified Agent Logic:** Agent's main loop delegates to `StateBehavior.update()`. Complex logic is encapsulated.
*   **Improved Debugging:** Layered approach helps pinpoint issues in task intents, agent processing, or state behaviors.
*   **Enhanced Robustness for Pathfinding:** Failures handled by explicit state transitions (e.g., to `PathFailedStateBehavior`).
*   **Maintainability:** Changes localized to relevant `StateBehavior` classes.

## 4. High-Level Outline of Refactoring Steps

1.  **Define `Intent` System:**
    *   Identify and define core `Intent` types and their data.
    *   Define `Intent` statuses (`PENDING`, `ACTIVE`, `COMPLETED`, `FAILED`, `CANCELLED`).
2.  **Refactor `Agent` Class:**
    *   Implement basic State pattern (`current_state_behavior`).
    *   Create initial `StateBehavior` classes.
    *   Implement `AgentInterface` for `Intent` submission/status.
    *   Implement `IntentProcessor` to map `Intents` to `StateBehaviors`.
3.  **Adapt Pathfinding:**
    *   Modify `_follow_path()` for granular status returns.
    *   Integrate into `MovingBehavior`.
4.  **Refactor `Task` Classes:**
    *   Remove direct agent state manipulation.
    *   `prepare()`: Submit first `Intent`.
    *   `execute_step()`: Query `Intent` status, submit next `Intent` or update task status.
5.  **Iterative Refinement & Testing:**
    *   Start with one task type and one agent.
    *   Thoroughly test.
    *   Gradually refactor other task types.
6.  **Simplify `AgentState` Enum:** May become redundant or map to broader categories.

## 5. Potential Risks or Challenges

*   **Initial Overhead:** Designing `Intent` system and refactoring agent core.
*   **Complexity Shift:** Agent's internal state management becomes more sophisticated initially.
*   **Interface Design:** `Intent` interface design is crucial.

This plan aims to create a more robust, maintainable, and understandable agent system.