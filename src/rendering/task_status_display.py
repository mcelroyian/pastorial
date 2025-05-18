import pygame
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..tasks.task_manager import TaskManager
    from ..tasks.task import Task, GatherAndDeliverTask
    from ..tasks.task_types import TaskStatus # Added for explicit reference if needed by _render_task_details
    from ..core import config # For potential color or layout configs

class TaskStatusDisplay:
    """
    Displays the current status of tasks in the simulation.
    """
    def __init__(self,
                 task_manager: 'TaskManager',
                 font: pygame.font.Font,
                 panel_rect: pygame.Rect,
                 screen_surface: pygame.Surface,
                 config_module: 'config'): # Pass config module for colors etc.
        """
        Initializes the TaskStatusDisplay.

        Args:
            task_manager: Reference to the global TaskManager.
            font: Pygame font for rendering text.
            panel_rect: Rect defining the panel's position and dimensions.
            screen_surface: The main screen surface to blit onto.
            config_module: The game's configuration module.
        """
        self.task_manager_ref = task_manager
        self.font = font
        self.panel_rect = panel_rect
        self.screen_surface = screen_surface
        self.config = config_module

        self.panel_surface = pygame.Surface(self.panel_rect.size)
        self.background_color = pygame.Color(self.config.COLOR_BLACK) # Example, use config
        self.text_color = pygame.Color(self.config.DEBUG_TEXT_COLOR) # Example
        self.header_color = pygame.Color(self.config.COLOR_WHITE) # Example
        self.padding = 10
        self.line_height = self.font.get_linesize() + 2
        self.max_items_per_section = 10 # Configurable or dynamic

        # Colors for different task statuses (can be expanded)
        self.status_colors = {
            "PENDING": pygame.Color('yellow'),
            "ASSIGNED": pygame.Color('orange'),
            "PREPARING": pygame.Color('lightblue'),
            "IN_PROGRESS_MOVE_TO_RESOURCE": pygame.Color('cyan'),
            "IN_PROGRESS_GATHERING": pygame.Color('green'),
            "IN_PROGRESS_MOVE_TO_DROPOFF": pygame.Color('cyan'),
            "IN_PROGRESS_DELIVERING": pygame.Color('lightgreen'),
            "COMPLETED": pygame.Color('grey'),
            "FAILED": pygame.Color('red'),
            "CANCELLED": pygame.Color('magenta'),
        }
        self.default_status_color = self.text_color


    def _draw_text(self, surface: pygame.Surface, text: str, position: tuple[int, int], color: pygame.Color, font: pygame.font.Font) -> None:
        """Helper method to render and blit text."""
        text_surface = font.render(text, True, color)
        surface.blit(text_surface, position)

    def _render_task_details(self, task: 'Task', y_pos: int, surface: pygame.Surface) -> int:
        """Renders details of a single Task object."""
        from ..tasks.task import GatherAndDeliverTask # Local import for type check
        from ..tasks.task_types import TaskStatus # Local import for enum access

        start_y = y_pos
        task_id_short = str(task.task_id).split('-')[0]
        status_color = self.status_colors.get(task.status.name, self.default_status_color)

        # Line 1: Task ID and Type
        line1_text = f"ID: {task_id_short} ({task.task_type.name})"
        self._draw_text(surface, line1_text, (self.padding, y_pos), self.text_color, self.font)
        y_pos += self.line_height

        # Line 2: Status
        line2_text = f"Status: {task.status.name}"
        self._draw_text(surface, line2_text, (self.padding + 10, y_pos), status_color, self.font)
        y_pos += self.line_height

        # Line 3: Agent (if assigned)
        if task.agent_id:
            agent_id_short = str(task.agent_id).split('-')[0]
            line3_text = f"Agent: {agent_id_short}"
            self._draw_text(surface, line3_text, (self.padding + 10, y_pos), self.text_color, self.font)
            y_pos += self.line_height

        # Line 4: Specifics for GatherAndDeliverTask or general description
        details_text = ""
        if isinstance(task, GatherAndDeliverTask):
            details_text = f"Res: {task.resource_type_to_gather.name}, Qty: {task.quantity_gathered}/{task.quantity_to_gather}"
            if task.status in [
                TaskStatus.IN_PROGRESS_MOVE_TO_RESOURCE, TaskStatus.IN_PROGRESS_GATHERING,
                TaskStatus.IN_PROGRESS_MOVE_TO_DROPOFF, TaskStatus.IN_PROGRESS_DELIVERING,
                TaskStatus.PREPARING
            ]:
                details_text += f" | {task.get_target_description()}"

        elif task.status in [
            TaskStatus.IN_PROGRESS_MOVE_TO_RESOURCE, TaskStatus.IN_PROGRESS_GATHERING,
            TaskStatus.IN_PROGRESS_MOVE_TO_DROPOFF, TaskStatus.IN_PROGRESS_DELIVERING,
            TaskStatus.PREPARING # General preparing state
        ]: # For other task types that might have a description
            details_text = task.get_target_description()

        if details_text:
            self._draw_text(surface, details_text, (self.padding + 10, y_pos), self.text_color, self.font)
            y_pos += self.line_height

        # Line 5: Error message (if failed)
        if task.status == TaskStatus.FAILED and task.error_message:
            error_text = f"Error: {task.error_message}"
            # Truncate error message if too long
            max_error_len = (self.panel_rect.width - self.padding * 3) // (self.font.size("A")[0] or 1) # Approx chars
            if len(error_text) > max_error_len:
                error_text = error_text[:max_error_len-3] + "..."
            self._draw_text(surface, error_text, (self.padding + 10, y_pos), self.status_colors.get("FAILED", self.default_status_color), self.font)
            y_pos += self.line_height

        # Separator line
        pygame.draw.line(surface, self.text_color, (self.padding, y_pos), (self.panel_rect.width - self.padding, y_pos), 1)
        y_pos += self.padding // 2
        return y_pos

    def draw(self) -> None:
        """Draws the task status panel."""
        self.panel_surface.fill(self.background_color)
        current_y = self.padding

        # Section: Pending Tasks
        header_text_pending = f"Pending Tasks ({len(self.task_manager_ref.pending_tasks)})"
        self._draw_text(self.panel_surface, header_text_pending, (self.padding, current_y), self.header_color, self.font)
        current_y += self.line_height + self.padding // 2
        for i, task in enumerate(self.task_manager_ref.pending_tasks):
            if i >= self.max_items_per_section:
                self._draw_text(self.panel_surface, f"... and {len(self.task_manager_ref.pending_tasks) - i} more.", (self.padding, current_y), self.text_color, self.font)
                current_y += self.line_height
                break
            current_y = self._render_task_details(task, current_y, self.panel_surface)
        current_y += self.padding # Space before next section

        # Section: In-Progress Tasks
        header_text_assigned = f"In-Progress Tasks ({len(self.task_manager_ref.assigned_tasks)})"
        self._draw_text(self.panel_surface, header_text_assigned, (self.padding, current_y), self.header_color, self.font)
        current_y += self.line_height + self.padding // 2
        for i, task in enumerate(list(self.task_manager_ref.assigned_tasks.values())): # Convert dict_values to list for enumerate
            if i >= self.max_items_per_section:
                self._draw_text(self.panel_surface, f"... and {len(self.task_manager_ref.assigned_tasks) - i} more.", (self.padding, current_y), self.text_color, self.font)
                current_y += self.line_height
                break
            current_y = self._render_task_details(task, current_y, self.panel_surface)
        current_y += self.padding

        # Section: Recently Completed Tasks
        completed_tasks_to_show = self.task_manager_ref.completed_tasks[-self.max_items_per_section:]
        header_text_completed = f"Recently Completed ({len(completed_tasks_to_show)} of {len(self.task_manager_ref.completed_tasks)})"
        self._draw_text(self.panel_surface, header_text_completed, (self.padding, current_y), self.header_color, self.font)
        current_y += self.line_height + self.padding // 2
        for task in reversed(completed_tasks_to_show): # Show newest first
            current_y = self._render_task_details(task, current_y, self.panel_surface)
            if current_y > self.panel_rect.height - self.padding: # Stop if panel is full
                 break
        current_y += self.padding

        # Section: Recently Failed Tasks
        failed_tasks_to_show = self.task_manager_ref.failed_tasks[-self.max_items_per_section:]
        header_text_failed = f"Recently Failed ({len(failed_tasks_to_show)} of {len(self.task_manager_ref.failed_tasks)})"
        self._draw_text(self.panel_surface, header_text_failed, (self.padding, current_y), self.header_color, self.font)
        current_y += self.line_height + self.padding // 2
        for task in reversed(failed_tasks_to_show): # Show newest first
            current_y = self._render_task_details(task, current_y, self.panel_surface)
            if current_y > self.panel_rect.height - self.padding: # Stop if panel is full
                 break
        current_y += self.padding

        # Blit the panel surface to the main screen
        self.screen_surface.blit(self.panel_surface, self.panel_rect.topleft)