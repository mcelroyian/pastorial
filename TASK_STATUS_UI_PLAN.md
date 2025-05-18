# Plan: Task Status Display Panel UI Feature

**1. Objective:**
To provide a visual overview of tasks within the simulation, showing their current states (pending, in-progress, completed, failed), assigned agents, and other relevant details. This will help the user understand the ongoing activities managed by the `TaskManager`.

**2. New UI Component File:**
A new file will be created to house the UI component: `src/rendering/task_status_display.py`.

**3. Class Definition: `TaskStatusDisplay`**
This class will be responsible for rendering the task status information.

*   **File:** `src/rendering/task_status_display.py`
*   **Class Name:** `TaskStatusDisplay`

    *   **`__init__(self, task_manager: TaskManager, font: pygame.font.Font, panel_rect: pygame.Rect, screen_surface: pygame.Surface)`**
        *   `task_manager`: A reference to the global `TaskManager` instance to fetch task data.
        *   `font`: A `pygame.font.Font` object for rendering text.
        *   `panel_rect`: A `pygame.Rect` object defining the position and dimensions of the task display panel on the main screen.
        *   `screen_surface`: The main Pygame screen surface onto which this panel will be drawn.
        *   **Internal Attributes:**
            *   `self.panel_surface = pygame.Surface(panel_rect.size)`: A dedicated surface for drawing the panel's content.
            *   `self.background_color`: Color for the panel's background.
            *   `self.text_color`: Default color for text.
            *   `self.header_color`: Color for section headers.
            *   `self.padding`: Padding within the panel.
            *   `self.line_height`: Vertical spacing for text lines.
            *   `self.max_items_per_section`: To limit display.

    *   **`_draw_text(self, surface: pygame.Surface, text: str, position: tuple[int, int], color: pygame.Color, font: pygame.font.Font) -> None`**
        *   A helper method to render and blit a single line of text.

    *   **`_render_task_details(self, task: Task, y_pos: int, surface: pygame.Surface) -> int`**
        *   Renders the details of a single `Task` object.
        *   Information to display:
            *   Task ID (shortened).
            *   Task Type (`task.task_type.name`).
            *   Status (`task.status.name`).
            *   For `GatherAndDeliverTask`: Resource (`task.resource_type_to_gather.name`), Quantity (`task.quantity_gathered` / `task.quantity_to_gather`).
            *   If `task.agent_id` is set: "Agent: [agent_id]".
            *   For `IN_PROGRESS_*` tasks: Use `task.get_target_description()`.
            *   If `task.status` is `FAILED`: Display `task.error_message`.
        *   Returns the new `y_pos`.

    *   **`draw(self) -> None`**
        *   Main rendering method.
        *   Fill `self.panel_surface`.
        *   **Pending Tasks Section:** Header and list of pending tasks.
        *   **In-Progress Tasks Section:** Header and list of in-progress tasks.
        *   **Recently Completed Tasks Section (Optional):** Header and list of completed tasks.
        *   **Recently Failed Tasks Section (Optional):** Header and list of failed tasks.
        *   Blit `self.panel_surface` onto `self.screen_surface`.

**4. Integration into `GameLoop` (`src/core/game_loop.py`):**

*   **In `GameLoop.__init__`:**
    *   Import `TaskStatusDisplay`.
    *   Initialize `self.ui_font`.
    *   Define `task_panel_rect` (e.g., `panel_width = 300`, `panel_x = config.SCREEN_WIDTH - panel_width`).
    *   Instantiate `self.task_display = TaskStatusDisplay(self.task_manager, self.ui_font, task_panel_rect, self.screen)`.

*   **In `GameLoop.render`:**
    *   Call `self.task_display.draw()`.

**5. Data Flow:**
The `TaskStatusDisplay` directly accesses task lists from the `TaskManager`.

**Future Enhancements (Out of Scope for Initial Version):**
*   Clickable tasks for more details.
*   Scrolling.
*   Filtering options.
*   Visual indicators (color-coding).