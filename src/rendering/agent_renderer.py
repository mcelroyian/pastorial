import pygame
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.agents.agent import Agent

from src.agents.agent_behaviors import (
    IdleBehavior, MovingBehavior, InteractingBehavior,
    PathFailedBehavior, EvaluatingIntentBehavior,
)
from src.core import config

_BEHAVIOR_COLORS = {
    IdleBehavior: (255, 255, 0),
    MovingBehavior: (0, 200, 50),
    InteractingBehavior: (50, 150, 255),
    PathFailedBehavior: (255, 0, 0),
    EvaluatingIntentBehavior: (200, 200, 200),
}
_DEFAULT_COLOR = (255, 0, 255)


def draw_agent(agent: 'Agent', screen: pygame.Surface, grid, selected_agent: Optional['Agent'] = None):
    screen_pos = grid.grid_to_screen(agent.position)
    agent_radius = grid.cell_width // 2

    color = _BEHAVIOR_COLORS.get(type(agent.current_behavior), _DEFAULT_COLOR)
    pygame.draw.circle(screen, color, screen_pos, agent_radius)

    if agent is selected_agent:
        pygame.draw.circle(screen, config.COLOR_WHITE, screen_pos, agent_radius + 2, 2)

    if agent.current_inventory['quantity'] > 0 and agent.current_inventory['resource_type'] is not None:
        carried = agent.current_inventory['resource_type']
        resource_color = config.RESOURCE_VISUAL_COLORS.get(carried, (128, 128, 128))
        icon_radius = agent_radius // 2
        pygame.draw.circle(
            screen,
            resource_color,
            (screen_pos[0], screen_pos[1] - agent_radius - icon_radius // 2),
            icon_radius,
        )

    # Hunger bar — thin rect below the agent circle
    if hasattr(agent, 'needs'):
        bar_w = agent_radius * 2
        bar_h = 3
        bar_x = screen_pos[0] - agent_radius
        bar_y = screen_pos[1] + agent_radius + 2
        # background
        pygame.draw.rect(screen, (60, 60, 60), (bar_x, bar_y, bar_w, bar_h))
        # fill: green → red as hunger drops
        hunger = agent.needs.hunger
        fill_color = (int(255 * (1 - hunger)), int(255 * hunger), 0)
        fill_w = max(1, int(bar_w * hunger))
        pygame.draw.rect(screen, fill_color, (bar_x, bar_y, fill_w, bar_h))
