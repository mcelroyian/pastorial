import pygame
import asyncio
import time
import logging
from typing import Optional, Any, Dict
from src.core import config
from src.core.simulation import Simulation
from src.input import handlers as input_handlers
from src.rendering import debug_display as debug_renderer
from src.rendering.task_status_display import TaskStatusDisplay
from src.rendering.inspector_display import InspectorDisplay
from src.agents.agent import Agent


class GameLoop:
    """Thin rendering/input shell around a Simulation instance."""

    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.is_running = False
        self.last_time = time.perf_counter()
        self.accumulator = 0.0
        self.dt = 1.0 / config.TARGET_FPS
        self.show_task_panel = True
        self.logger = logging.getLogger(__name__)

        self.paused: bool = False
        self.manual_control_mode: bool = False
        self.selected_agent: Optional[Agent] = None

        try:
            self.resource_font = pygame.font.Font(None, config.RESOURCE_FONT_SIZE)
        except Exception as e:
            self.logger.warning(f"Could not load resource font: {e}")
            self.resource_font = pygame.font.Font(pygame.font.get_default_font(), config.RESOURCE_FONT_SIZE)

        try:
            self.ui_font = pygame.font.Font(None, 24)
        except Exception as e:
            self.logger.warning(f"Could not load UI font: {e}")
            self.ui_font = pygame.font.Font(pygame.font.get_default_font(), 24)

        self.sim = Simulation()

        task_panel_rect = pygame.Rect(
            config.SCREEN_WIDTH - 350, 0, 350, config.SCREEN_HEIGHT
        )
        self.task_display = TaskStatusDisplay(
            task_manager=self.sim.task_manager,
            font=self.ui_font,
            panel_rect=task_panel_rect,
            screen_surface=self.screen,
            config_module=config,
        )
        self.inspector_display = InspectorDisplay(surface=self.screen, font=self.ui_font)

    def _get_agent_display_data(self, agent: Agent) -> Dict[str, Any]:
        hunger = agent.needs.hunger if hasattr(agent, 'needs') else 1.0
        agent_data = {
            'name': agent.name,
            'id': agent.id,
            'position': f"({agent.position.x:.1f}, {agent.position.y:.1f})",
            'hunger': f"{hunger:.0%}",
            'inventory': {
                'type': agent.current_inventory['resource_type'].name if agent.current_inventory['resource_type'] else 'None',
                'quantity': agent.current_inventory['quantity'],
            },
            'behavior': agent.current_behavior.__class__.__name__,
            'intent': agent.current_intent.get_description() if agent.current_intent else 'None',
            'task': 'None',
        }
        if agent.current_intent and agent.current_intent.originating_task_id:
            task = self.sim.task_manager.get_task_by_id(agent.current_intent.originating_task_id)
            if task:
                agent_data['task'] = {
                    'type': task.task_type.name,
                    'status': task.status.name,
                    'description': task.get_description(),
                }
        return agent_data

    def handle_input(self):
        user_actions = input_handlers.process_events()
        if user_actions['quit']:
            self.is_running = False
        if user_actions['toggle_panel']:
            self.show_task_panel = not self.show_task_panel
        if user_actions['toggle_pause']:
            self.paused = not self.paused
            self.logger.info(f"Game {'PAUSED' if self.paused else 'UNPAUSED'}")
        if user_actions['mouse_click']:
            click_pos_screen = user_actions['mouse_click']
            click_pos_grid = self.sim.grid.screen_to_grid(pygame.math.Vector2(click_pos_screen))
            self.selected_agent = self.sim.agent_manager.get_agent_at_position(click_pos_grid)
        if user_actions['toggle_manual_mode']:
            self.manual_control_mode = not self.manual_control_mode
            self.logger.info(f"Manual Control Mode {'ACTIVATED' if self.manual_control_mode else 'DEACTIVATED'}")

    def update(self, dt):
        self.sim.update(dt, self.manual_control_mode)

    def render(self):
        # Clear selection if the selected agent has died
        if self.selected_agent and self.selected_agent not in self.sim.agent_manager.agents:
            self.selected_agent = None

        self.screen.fill(config.COLOR_BLACK)
        self.sim.grid.draw(self.screen)
        self.sim.resource_manager.draw_nodes(self.screen, self.resource_font, self.sim.grid)
        self.sim.agent_manager.render_agents(self.screen, self.sim.grid, self.selected_agent)
        debug_renderer.display_fps(self.screen, self.clock)
        if self.show_task_panel:
            self.task_display.draw()
        if self.selected_agent:
            self.inspector_display.draw(self._get_agent_display_data(self.selected_agent))
        pygame.display.flip()

    async def run(self):
        self.is_running = True
        self.last_time = time.perf_counter()

        while self.is_running:
            current_time = time.perf_counter()
            frame_time = min(current_time - self.last_time, 0.25)
            self.last_time = current_time
            self.accumulator += frame_time

            self.handle_input()

            while self.accumulator >= self.dt:
                if not self.paused:
                    self.update(self.dt)
                self.accumulator -= self.dt

            self.render()
            self.clock.tick()
            await asyncio.sleep(0)
