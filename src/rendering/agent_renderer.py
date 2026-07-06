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
        key = carried.name if hasattr(carried, 'name') else str(carried)
        resource_color = config.RESOURCE_VISUAL_COLORS.get(key, (128, 128, 128))
        icon_radius = agent_radius // 2
        pygame.draw.circle(
            screen,
            resource_color,
            (screen_pos[0], screen_pos[1] - agent_radius - icon_radius // 2),
            icon_radius,
        )
