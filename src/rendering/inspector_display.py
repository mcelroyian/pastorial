import pygame
from typing import Optional, Dict, Any

from src.core import config

class InspectorDisplay:
    """
    A UI component to display detailed information about a selected agent.
    """
    def __init__(self, surface: pygame.Surface, font: pygame.font.Font):
        """
        Initializes the InspectorDisplay.

        Args:
            surface (pygame.Surface): The surface to draw the panel on.
            font (pygame.font.Font): The font to use for rendering text.
        """
        self.surface = surface
        self.font = font
        self.panel_rect = pygame.Rect(
            config.SCREEN_WIDTH - config.INSPECTOR_PANEL_WIDTH, 
            0, 
            config.INSPECTOR_PANEL_WIDTH, 
            config.SCREEN_HEIGHT
        )
        self.text_color = config.COLOR_WHITE
        self.bg_color = config.COLOR_GRAY

    def draw(self, agent_data: Optional[Dict[str, Any]]):
        """
        Draws the inspector panel with the provided agent data.

        Args:
            agent_data (Optional[Dict[str, Any]]): A dictionary containing the
                information to display. If None, the panel is not drawn.
        """
        if not agent_data:
            return # Don't draw if no agent is selected

        # Draw panel background
        pygame.draw.rect(self.surface, self.bg_color, self.panel_rect)
        pygame.draw.rect(self.surface, self.text_color, self.panel_rect, 1) # Border

        y_offset = 10
        x_offset = self.panel_rect.x + 10

        # Display each piece of data
        for key, value in agent_data.items():
            text = f"{key.replace('_', ' ').title()}:"
            self._draw_text(text, x_offset, y_offset)
            y_offset += 20

            # Handle nested dictionaries for task/inventory
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    sub_text = f"  {sub_key.title()}: {sub_value}"
                    self._draw_text(sub_text, x_offset, y_offset)
                    y_offset += 20
            else:
                self._draw_text(str(value), x_offset + 15, y_offset)
                y_offset += 25
        
            y_offset += 5 # Add a little space between main attributes

    def _draw_text(self, text: str, x: int, y: int):
        """Helper to render a line of text."""
        text_surface = self.font.render(text, True, self.text_color)
        self.surface.blit(text_surface, (x, y))