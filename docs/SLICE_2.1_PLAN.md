# Plan: Epic 2, Slice 2.1 - Agent Movement

This plan focuses on creating the basic `Agent` class, implementing simple movement behaviors, managing agents, and integrating them into the existing simulation loop.

**Goals:**

1.  Establish the core `Agent` class structure.
2.  Implement basic movement logic (direct to target, random).
3.  Create an `AgentManager` to handle multiple agents.
4.  Integrate agent updates and rendering into the main game loop.
5.  Provide simple visual representation and state indication.

**Technical Implementation Steps:**

1.  **Create Agent Module:**
    *   Create a new directory: `src/agents/`
    *   Create `src/agents/__init__.py` (empty file).
    *   Create `src/agents/agent.py`.

2.  **Define `Agent` Class (`src/agents/agent.py`):**
    *   Import necessary modules (e.g., `pygame.math.Vector2`).
    *   Define an `Enum` or constants for agent states: `IDLE`, `MOVING_RANDOMLY`, `MOVING_TO_TARGET`.
    *   Implement the `Agent` class:
        *   `__init__(self, position, speed)`: Initialize `position` (Vector2), `speed`, `state` (default to `IDLE`), `target_position` (None initially), `color` (yellow).
        *   `set_target(self, target_position)`: Sets `target_position` and changes `state` to `MOVING_TO_TARGET`.
        *   `_move_towards_target(self, dt)`: Calculates the direction vector to `target_position`. Normalizes the vector. Updates `self.position` based on `speed` and `dt`. If close enough to the target, set `state` to `IDLE` and `target_position` to None.
        *   `_move_randomly(self, dt)`: Implement simple random movement logic (e.g., pick a random nearby point periodically or maintain a random velocity vector for a duration).
        *   `update(self, dt)`:
            *   If `state` is `MOVING_TO_TARGET`, call `_move_towards_target(dt)`.
            *   If `state` is `MOVING_RANDOMLY`, call `_move_randomly(dt)`.
            *   If `state` is `IDLE`, do nothing.
        *   `draw(self, screen, grid)`: Calculate screen coordinates from grid position. Draw a yellow circle representing the agent. Modify color slightly based on `state` for basic visualization (e.g., slightly brighter yellow for moving states).

3.  **Create `AgentManager` Class (`src/agents/manager.py`):**
    *   Create `src/agents/manager.py`.
    *   Import `Agent`.
    *   Implement the `AgentManager` class:
        *   `__init__(self)`: Initialize an empty list `self.agents`.
        *   `add_agent(self, agent)`: Appends an `Agent` instance to `self.agents`.
        *   `create_agent(self, position, speed)`: Creates an `Agent` instance and adds it to the list. Returns the created agent.
        *   `update_agents(self, dt)`: Loop through `self.agents` and call each agent's `update(dt)` method.
        *   `render_agents(self, screen, grid)`: Loop through `self.agents` and call each agent's `draw(screen, grid)` method.

4.  **Integrate into Game Loop (e.g., `main.py` or `app.py`):**
    *   Import `AgentManager` and `Agent` (or just the manager if using `create_agent`).
    *   Before the main loop, instantiate `agent_manager = AgentManager()`.
    *   Create a few initial agents:
        ```python
        # Example: Create agents at specific grid positions
        agent1 = agent_manager.create_agent(position=Vector2(5, 5), speed=50) # Speed in pixels/sec
        agent2 = agent_manager.create_agent(position=Vector2(10, 10), speed=60)
        # Optionally set initial targets or states
        # agent1.set_target(Vector2(15, 15))
        # agent2.state = AgentState.MOVING_RANDOMLY
        ```
    *   Inside the game loop's **update phase**: Call `agent_manager.update_agents(dt)`.
    *   Inside the game loop's **render phase**: Call `agent_manager.render_agents(screen, grid)`.

5.  **Refinement & Configuration:**
    *   Adjust agent speed in the `Config` class if desired.
    *   Ensure grid coordinates are correctly translated to screen coordinates for drawing.
    *   Refine the state visualization colors/method as needed.

**Mermaid Diagram: Agent System Structure**

```mermaid
graph TD
    subgraph GameLoop [Main Game Loop (main.py/app.py)]
        direction LR
        A[Initialize] --> B(Update Cycle);
        B --> C(Render Cycle);
        C --> B;
    end

    subgraph AgentSystem [Agent System (src/agents/)]
        direction TB
        Manager[AgentManager] --> AgentList{Agents List};
        AgentList --> Agent1[Agent Instance 1];
        AgentList --> Agent2[Agent Instance 2];
        Agent1 --> StateMachine1[State Machine];
        Agent2 --> StateMachine2[State Machine];
        StateMachine1 -- controls --> Movement1[Movement Logic];
        StateMachine2 -- controls --> Movement2[Movement Logic];
        Movement1 --> Position1[Position Update];
        Movement2 --> Position2[Position Update];
    end

    A -- instantiates --> Manager;
    B -- calls --> Manager_Update[AgentManager.update_agents(dt)];
    Manager_Update -- calls --> Agent1_Update[Agent1.update(dt)];
    Manager_Update -- calls --> Agent2_Update[Agent2.update(dt)];
    C -- calls --> Manager_Render[AgentManager.render_agents(screen, grid)];
    Manager_Render -- calls --> Agent1_Draw[Agent1.draw(...)];
    Manager_Render -- calls --> Agent2_Draw[Agent2.draw(...)];

    Agent1_Update --> StateMachine1;
    Agent2_Update --> StateMachine2;

    classDef default fill:#f9f,stroke:#333,stroke-width:2px;
    classDef agent fill:#ccf,stroke:#333,stroke-width:2px;
    class Agent1,Agent2,AgentList,Manager,StateMachine1,StateMachine2,Movement1,Movement2,Position1,Position2 agent;
```

**Testing Criteria Checklist:**

*   [ ] Agents appear on grid (yellow circles) and move smoothly.
*   [ ] Agents move directly towards a set target.
*   [ ] Agents exhibit random movement when in that state.
*   [ ] Movement speed is consistent with simulation rate (`dt`).
*   [ ] Agent states (`IDLE`, `MOVING_RANDOMLY`, `MOVING_TO_TARGET`) are visually distinguishable (e.g., slight color change).
*   [ ] Multiple agents can operate simultaneously without interfering (collision ignored for now).
*   [ ] Agents stop appropriately when reaching their target.