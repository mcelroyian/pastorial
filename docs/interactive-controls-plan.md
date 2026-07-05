# Design for Interactive Simulation Controls

This document outlines the design for adding interactive controls to the simulation, allowing for pausing, agent inspection, and manual task management.

### 1. Core Concepts & System Flow

This section provides a detailed architectural plan for the interactive simulation controls. It outlines the necessary changes to core classes, defines data structures for communication, and specifies the interfaces between different parts of the system.

#### 1.1. State Management in GameLoop

The `GameLoop` will be the central authority for managing the global interactive states. This ensures a single source of truth and simplifies state-related logic across the system.

*   **Location:** [`src/core/game_loop.py`](src/core/game_loop.py)
*   **New Attributes:**
    *   `paused: bool = False`: When `True`, the `update()` logic for game entities (agents, resources) will be skipped. Rendering and input handling will continue.
    *   `manual_control_mode: bool = False`: When `True`, the autonomous task generation in `TaskManager` is suppressed, and the UI for manual task creation is enabled.
    *   `selected_agent: Optional[Agent] = None`: Stores a reference to the currently selected `Agent` object. Will be `None` if no agent is selected.

#### 1.2. Detailed Concept Breakdown

##### 1.2.1. Simulation Pausing

*   **Description:** A global state that halts game logic updates while allowing rendering and UI interaction to continue. This is crucial for giving the player time to inspect the simulation and issue commands without pressure.
*   **Implementation Details:**
    *   **[`src/core/game_loop.py`](src/core/game_loop.py) (`GameLoop` class):**
        *   **Attribute:** `paused: bool = False`
        *   **Method Modification:** In `run()`, the `while self.accumulator >= self.dt:` loop will be guarded by `if not self.paused:`.
            ```python
            # In GameLoop.run()
            while self.accumulator >= self.dt:
                if not self.paused:
                    self.update(self.dt)
                self.accumulator -= self.dt
            ```
    *   **[`src/input/handlers.py`](src/input/handlers.py):**
        *   **Method Modification:** `process_events()` will be updated to detect a key press (e.g., `P`) and return a corresponding action.
            ```python
            # In process_events()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_p:
                    actions['toggle_pause'] = True
            ```
    *   **[`src/core/game_loop.py`](src/core/game_loop.py) (`GameLoop` class):**
        *   **Method Modification:** `handle_input()` will toggle the `self.paused` state.
            ```python
            # In GameLoop.handle_input()
            if user_actions['toggle_pause']:
                self.paused = not self.paused
            ```

##### 1.2.2. Agent Selection

*   **Description:** The ability to click on an agent to make it the "selected" entity. The selected agent becomes the focus for the Inspector Panel and manual commands.
*   **Implementation Details:**
    *   **[`src/input/handlers.py`](src/input/handlers.py):**
        *   **Method Modification:** `process_events()` will detect `MOUSEBUTTONDOWN` events and store the click position.
            ```python
            # In process_events()
            if event.type == pygame.MOUSEBUTTONDOWN:
                actions['mouse_click'] = event.pos
            ```
    *   **[`src/core/game_loop.py`](src/core/game_loop.py) (`GameLoop` class):**
        *   **Attribute:** `selected_agent: Optional[Agent] = None`
        *   **Method Modification:** `handle_input()` will process the click.
            ```python
            # In GameLoop.handle_input()
            if 'mouse_click' in user_actions:
                click_pos_screen = user_actions['mouse_click']
                click_pos_grid = self.grid.screen_to_grid(pygame.math.Vector2(click_pos_screen))
                self.selected_agent = self.agent_manager.get_agent_at_position(click_pos_grid)
            ```
    *   **[`src/agents/manager.py`](src/agents/manager.py) (`AgentManager` class):**
        *   **New Method:** `get_agent_at_position(grid_pos: pygame.math.Vector2) -> Optional[Agent]`
            *   This method will iterate through `self.agents` and return the first agent whose rectangular area on the grid contains the `grid_pos`. It will need to account for agent size.
    *   **[`src/agents/agent.py`](src/agents/agent.py) (`Agent` class):**
        *   **Method Modification:** `draw()` will be updated to render a visual indicator (e.g., a highlight circle or outline) if the agent instance is the same as the one stored in `GameLoop.selected_agent`. This requires passing the `selected_agent` from the `GameLoop` down to the `draw` call.
            ```python
            # In GameLoop.render()
            self.agent_manager.render_agents(self.screen, self.grid, self.selected_agent)

            # In AgentManager.render_agents()
            for agent in self.agents:
                agent.draw(screen, grid, selected_agent)

            # In Agent.draw()
            def draw(self, screen, grid, selected_agent):
                is_selected = (self == selected_agent)
                # ... drawing logic ...
                if is_selected:
                    # draw highlight
            ```

##### 1.2.3. Inspector Panel

*   **Description:** A new UI element that displays detailed, real-time information about the selected agent.
*   **Implementation Details:**
    *   **New File:** `src/rendering/inspector_display.py`
    *   **New Class:** `InspectorDisplay`
        *   **`__init__(self, surface, font)`**: Constructor.
        *   **`draw(self, agent_data: Optional[Dict[str, Any]])`**: The core rendering method. It will check if `agent_data` is not `None` and then draw the information.
    *   **Data Flow:** The `GameLoop` will be responsible for gathering the necessary data and passing it to the `InspectorDisplay`. This decouples the UI from the core game logic.
        *   **In `GameLoop.render()`:**
            1.  If `self.selected_agent` is not `None`:
            2.  Call a new helper method, e.g., `_get_agent_display_data(self.selected_agent)`, to construct a dictionary.
            3.  Pass this dictionary to `self.inspector_display.draw()`.
        *   **New Helper Method in `GameLoop`:** `_get_agent_display_data(agent: Agent) -> Dict[str, Any]`
            *   This method will query the `agent` and the `task_manager` to build a serializable dictionary. This prevents the UI from holding direct references to complex game objects.

##### 1.2.4. Manual Control Mode

*   **Description:** A mode that allows the user to manually create and assign tasks to a selected agent, bypassing the autonomous `TaskManager` logic.
*   **Implementation Details:**
    *   **[`src/core/game_loop.py`](src/core/game_loop.py) (`GameLoop` class):**
        *   **Attribute:** `manual_control_mode: bool = False`
        *   **Method Modification:** `handle_input()` will check for a key (e.g., `M`) to toggle this mode.
    *   **[`src/tasks/task_manager.py`](src/tasks/task_manager.py) (`TaskManager` class):**
        *   **Method Modification:** The `_generate_tasks_if_needed()` method will be guarded by a check on the `manual_control_mode` flag (passed from `GameLoop`).
        *   **New Method:** `force_assign_task(self, task: Task, agent: Agent)`:
            *   This method will immediately assign a new task to an agent.
            *   It will first check if the agent has a current task. If so, it will call a new `cancel_task()` helper to gracefully stop the current task and release any claimed resources.
            *   It will then assign the new task and call `task.prepare()`.
    *   **UI (Future Chunk):** A new UI component, `ManualTaskCreatorUI`, will be responsible for gathering task parameters from the user. When the user confirms, this UI will call a method in `GameLoop` (e.g., `create_and_assign_manual_task(...)`) which in turn uses the `TaskManager` to create and force-assign the task.

#### 1.3. Data Flow Specification

The flow of information is critical. We will use dictionaries to pass data to the UI, avoiding direct coupling.

*   **Agent Selection:**
    *   `InputHandler` -> `GameLoop`: `{'mouse_click': (x, y)}`
    *   `GameLoop` -> `AgentManager`: `get_agent_at_position(grid_pos)`
    *   `AgentManager` -> `GameLoop`: `Optional[Agent]` object reference.

*   **Inspector Panel Data (`agent_data` dictionary):**
    *   This dictionary is constructed by `GameLoop._get_agent_display_data()` and passed to `InspectorDisplay.draw()`.
    ```python
    agent_data = {
        'name': agent.name,
        'id': agent.id,
        'position': (agent.position.x, agent.position.y),
        'inventory': {
            'type': agent.current_inventory['resource_type'].name if agent.current_inventory['resource_type'] else 'None',
            'quantity': agent.current_inventory['quantity']
        },
        'behavior': agent.current_behavior.__class__.__name__,
        'intent': agent.current_intent.get_description() if agent.current_intent else 'None',
        'task': None # Populated below
    }

    if agent.current_intent and agent.current_intent.originating_task_id:
        task = self.task_manager.get_task_by_id(agent.current_intent.originating_task_id)
        if task:
            agent_data['task'] = {
                'type': task.task_type.name,
                'status': task.status.name,
                'description': task.get_description() # A new method on the Task class
            }
    ```

#### 1.4. Interface Definitions (Method Signatures)

*   **`AgentManager`** ([`src/agents/manager.py`](src/agents/manager.py)):
    *   `get_agent_at_position(self, grid_pos: pygame.math.Vector2) -> Optional[Agent]`
*   **`TaskManager`** ([`src/tasks/task_manager.py`](src/tasks/task_manager.py)):
    *   `force_assign_task(self, task: Task, agent: Agent)`
    *   `cancel_task(self, task: Task)` (Helper for `force_assign_task`)
*   **`Task`** ([`src/tasks/task.py`](src/tasks/task.py)):
    *   `get_description(self) -> str`
*   **`GameLoop`** ([`src/core/game_loop.py`](src/core/game_loop.py)):
    *   `_get_agent_display_data(self, agent: Agent) -> Dict[str, Any]`

#### 1.5. Updated System Flow Diagram

```mermaid
graph TD
    subgraph User Input
        A[Input Handler: process_events()]
    end

    subgraph Game Core
        B[GameLoop]
        C[AgentManager]
        D[TaskManager]
        E[Agent]
    end

    subgraph UI / Rendering
        F[InspectorDisplay]
        G[ManualTaskCreatorUI]
    end

    A -- {'mouse_click': pos} --> B
    A -- {'toggle_pause': True} --> B
    A -- {'toggle_manual_mode': True} --> B

    B -- toggles self.paused --> B
    B -- toggles self.manual_control_mode --> B
    B -- get_agent_at_position(pos) --> C
    C -- returns Optional[Agent] --> B
    B -- sets self.selected_agent --> B

    B -- if selected_agent --> E
    E -- reads attributes --> B
    B -- if task_id --> D
    D -- get_task_by_id() --> B
    B -- constructs agent_data dict --> F

    F -- draw(agent_data) --> Screen

    B -- if manual_control_mode --> G
    G -- User creates task --> B
    B -- create_and_assign_manual_task() --> D
    D -- force_assign_task(task, agent) --> E
    E -- receives new task/intent --> E
```

### 2. Feature Breakdown & Implementation Plan

The implementation is broken down into the following manageable chunks.

**Chunk 1: Pausing and Agent Selection**

*   **Goal:** Implement the foundational mechanics of pausing the simulation and selecting an agent with a mouse click.
*   **Steps:**
    1.  Modify `GameLoop` to include a `paused` boolean state.
    2.  In `GameLoop.run()`, skip the `update()` call when `paused` is `True`.
    3.  Update `input/handlers.py` to detect a key press (e.g., 'P') to toggle `GameLoop.paused`.
    4.  Update `input/handlers.py` to detect `MOUSEBUTTONDOWN` events and pass the position to the `GameLoop`.
    5.  Implement `AgentManager.get_agent_at_position(pos)` to find and return an agent at the given coordinates.
    6.  Add a `selected_agent` attribute to `GameLoop` and update it based on clicks.
    7.  Add a visual indicator for the selected agent (e.g., a highlight circle drawn in `Agent.draw()`).

**Chunk 2: The Inspector Panel**

*   **Goal:** Display the state of the selected agent.
*   **Steps:**
    1.  Create a new file: `src/rendering/inspector_display.py`.
    2.  Create an `InspectorDisplay` class that takes a `pygame.Surface` and a font in its constructor.
    3.  Create a `draw(selected_agent, task_manager)` method in `InspectorDisplay`.
    4.  This method will check if `selected_agent` is not `None`. If it exists, it will:
        *   Display agent's name, position, and inventory.
        *   Display the agent's current behavior (`agent.current_behavior.__class__.__name__`).
        *   If the agent has an `originating_task_id` in its `current_intent`, use `task_manager.get_task_by_id()` to fetch the task.
        *   Display the task's type, status, and target description.
    5.  Instantiate `InspectorDisplay` in `GameLoop` and call its `draw()` method in `GameLoop.render()`.

**Chunk 3: Manual Task Creation & Assignment**

*   **Goal:** Allow the user to manually create a task and assign it to the selected agent.
*   **Steps:**
    1.  Introduce a "manual control mode" to the `GameLoop`. This could be a simple boolean flag for now.
    2.  Add a key press (e.g., 'C') to enter this mode.
    3.  Create a simple UI for creating tasks (we can start with keyboard prompts and print to console before building a graphical UI). This UI will call the existing `TaskManager.create_..._task` methods. The new task will be stored temporarily in the `GameLoop`.
    4.  Add a new method `TaskManager.force_assign_task(task, agent)`. This method will:
        *   Check if the agent has an existing task. If so, it will cancel it (we'll need a `cancel_task` helper method).
        *   Assign the new task to the agent.
        *   Call `task.prepare(agent, resource_manager)`.
    5.  Add a key press (e.g., 'A') that, when a task is manually created and an agent is selected, calls `TaskManager.force_assign_task`.