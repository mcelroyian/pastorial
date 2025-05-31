# UI Enhancement Plan for Task List

**Overall Goal:** Enhance the task list UI by adding a toggle, prettier ID naming, and making it non-obstructive.

---

**Phase 1: Implement Task List Toggle Functionality (Key 'T')**

1.  **File: `src/input/handlers.py`**
    *   **Modify `process_events()` function:**
        *   Instead of returning just a boolean for quit, it will return a dictionary indicating actions.
        *   Initialize `actions = {'quit': False, 'toggle_panel': False}` at the beginning of the function.
        *   Inside the event loop (`for event in pygame.event.get():`):
            *   If `event.type == pygame.QUIT`: set `actions['quit'] = True`.
            *   Add a new check: `if event.type == pygame.KEYDOWN:`
                *   If `event.key == pygame.K_t`: set `actions['toggle_panel'] = True`.
        *   Return `actions` at the end of the function.

2.  **File: `src/core/game_loop.py`**
    *   **In `GameLoop.__init__(self, screen)`:**
        *   Add a new attribute: `self.show_task_panel = True` (sets the panel to be visible by default).
    *   **Modify `GameLoop.handle_input(self)`:**
        *   Change logic to process the `actions` dictionary from `input_handlers.process_events()`.
            ```python
            user_actions = input_handlers.process_events()
            if user_actions['quit']:
                self.is_running = False
            if user_actions['toggle_panel']:
                self.show_task_panel = not self.show_task_panel
            ```
    *   **Modify `GameLoop.render(self)`:**
        *   Wrap the call to `self.task_display.draw()` in an `if self.show_task_panel:` condition.
            ```python
            if hasattr(self, 'task_display') and self.show_task_panel:
                self.task_display.draw()
            ```

---

**Phase 2: Implement Sequential Number IDs**

1.  **File: `src/rendering/task_status_display.py`**
    *   **In `TaskStatusDisplay.__init__(...)`:**
        *   Add:
            ```python
            self.task_id_map = {}
            self.agent_id_map = {}
            self.next_task_display_id = 1
            self.next_agent_display_id = 1
            ```
    *   **Modify `TaskStatusDisplay._render_task_details(...)`:**
        *   Replace `task_id_short = str(task.task_id).split('-')[0]` with:
            ```python
            if task.task_id not in self.task_id_map:
                self.task_id_map[task.task_id] = self.next_task_display_id
                self.next_task_display_id += 1
            display_task_id = self.task_id_map[task.task_id]
            ```
        *   Change `line1_text = f"ID: {task_id_short} ({task.task_type.name})"` to:
            ```python
            line1_text = f"Task: {display_task_id} ({task.task_type.name})"
            ```
        *   Inside the `if task.agent_id:` block:
            *   Replace `agent_id_short = str(task.agent_id).split('-')[0]` with:
                ```python
                if task.agent_id not in self.agent_id_map:
                    self.agent_id_map[task.agent_id] = self.next_agent_display_id
                    self.next_agent_display_id += 1
                display_agent_id = self.agent_id_map[task.agent_id]
                ```
            *   Change `line3_text = f"Agent: {agent_id_short}"` to:
                ```python
                line3_text = f"Agent: {display_agent_id}"
                ```

---

**Phase 3: Implement Semi-Transparent Panel**

1.  **File: `src/core/config.py` (Optional but Recommended)**
    *   Add:
        ```python
        PANEL_BACKGROUND_ALPHA = 128  # Value from 0 (transparent) to 255 (opaque)
        ```

2.  **File: `src/rendering/task_status_display.py`**
    *   **In `TaskStatusDisplay.__init__(...)`:**
        *   Change `self.panel_surface = pygame.Surface(self.panel_rect.size)` to:
            ```python
            self.panel_surface = pygame.Surface(self.panel_rect.size, pygame.SRCALPHA)
            ```
        *   Modify `self.background_color`. If using config:
            ```python
            bg_r, bg_g, bg_b = self.config.COLOR_BLACK 
            self.background_color = pygame.Color(bg_r, bg_g, bg_b, self.config.PANEL_BACKGROUND_ALPHA)
            ```
            Otherwise, directly:
            ```python
            self.background_color = pygame.Color(0, 0, 0, 128) # Example: 50% transparent black
            ```
    *   `self.panel_surface.fill(self.background_color)` in the `draw` method will use the alpha-enabled surface and color.

---

**Mermaid Diagram of Plan:**
```mermaid
graph TD
    subgraph Phase 1: Toggle Functionality
        P1_Input["User presses 'T' key"] --> P1_Handler(src/input/handlers.py#process_events);
        P1_Handler -- Returns {'toggle_panel': True} --> P1_GameLoop_Input(src/core/game_loop.py#handle_input);
        P1_GameLoop_Input -- Toggles 'self.show_task_panel' --> P1_GameLoop_State[GameLoop.show_task_panel];
        P1_GameLoop_Render(src/core/game_loop.py#render) -- Checks 'show_task_panel' --> P1_ConditionalRender{Render Panel?};
        P1_ConditionalRender -- Yes --> P1_DrawPanel(src/rendering/task_status_display.py#draw);
        P1_ConditionalRender -- No --> P1_SkipDraw[Panel Not Drawn];
    end

    subgraph Phase 2: Sequential IDs
        P2_RenderDetails(src/rendering/task_status_display.py#_render_task_details) -- Receives Task/Agent UUID --> P2_ID_Map{ID in map?};
        P2_ID_Map -- No --> P2_AssignSeqID[Assign & Store Sequential ID];
        P2_AssignSeqID --> P2_ID_Map;
        P2_ID_Map -- Yes --> P2_UseSeqID[Use Sequential ID];
        P2_UseSeqID --> P2_DisplayFormat["Format 'Task: {num}' / 'Agent: {num}'"];
        P2_DisplayFormat --> P1_DrawPanel;
    end

    subgraph Phase 3: Semi-Transparent Panel
        P3_Config(src/core/config.py) -- Defines PANEL_BACKGROUND_ALPHA (Optional) --> P3_Display_Init;
        P3_Display_Init(src/rendering/task_status_display.py#__init__) -- Creates Surface with pygame.SRCALPHA --> P3_AlphaSurface[panel_surface];
        P3_Display_Init -- Sets background_color with Alpha --> P3_AlphaColor[background_color];
        P3_AlphaSurface & P3_AlphaColor --> P3_FillSurface(src/rendering/task_status_display.py#draw#fill);
        P3_FillSurface --> P1_DrawPanel;
    end

    P1_DrawPanel --> ScreenOutput[Final Screen Display];