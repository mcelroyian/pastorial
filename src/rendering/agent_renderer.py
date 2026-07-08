import pygame
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.agents.agent import Agent

from src.agents.agent_behaviors import (
    IdleBehavior, MovingBehavior, InteractingBehavior,
    PathFailedBehavior, EvaluatingIntentBehavior,
)
from src.core import config

# Behavior ring colors (thin outline around the agent circle)
_BEHAVIOR_RING_COLORS = {
    IdleBehavior: (255, 255, 0),         # yellow = idle
    MovingBehavior: (0, 200, 50),         # green = moving
    InteractingBehavior: (50, 150, 255),  # blue = interacting
    PathFailedBehavior: (255, 0, 0),      # red = stuck
    EvaluatingIntentBehavior: (180, 180, 180),  # grey = thinking
}
_DEFAULT_RING = (255, 0, 255)

# Fallback fill when no faction is assigned
_NO_FACTION_COLOR = (160, 160, 160)


def draw_agent(agent: 'Agent', screen: pygame.Surface, grid, selected_agent: Optional['Agent'] = None):
    screen_pos = grid.grid_to_screen(agent.position)
    agent_radius = grid.cell_width // 2

    # Body fill = faction color
    faction_id = getattr(agent, 'owner_faction_id', None)
    if faction_id is not None:
        from src.core.config import FACTION_CONFIGS
        cfg = FACTION_CONFIGS[faction_id] if faction_id < len(FACTION_CONFIGS) else {}
        fill_color = cfg.get("color", _NO_FACTION_COLOR)
    else:
        fill_color = _NO_FACTION_COLOR

    pygame.draw.circle(screen, fill_color, screen_pos, agent_radius)

    # Behavior ring (thin outline)
    ring_color = _BEHAVIOR_RING_COLORS.get(type(agent.current_behavior), _DEFAULT_RING)
    pygame.draw.circle(screen, ring_color, screen_pos, agent_radius, 2)

    # Selection ring (white, slightly larger)
    if agent is selected_agent:
        pygame.draw.circle(screen, config.COLOR_WHITE, screen_pos, agent_radius + 3, 2)

    # Carried-resource icon above the agent
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
        pygame.draw.rect(screen, (60, 60, 60), (bar_x, bar_y, bar_w, bar_h))
        hunger = agent.needs.hunger
        fill_color_bar = (int(255 * (1 - hunger)), int(255 * hunger), 0)
        fill_w = max(1, int(bar_w * hunger))
        pygame.draw.rect(screen, fill_color_bar, (bar_x, bar_y, fill_w, bar_h))
