import pygame
import time
import random
from pygame.math import Vector2 # Added for agent positions
from src.core import config
from src.input import handlers as input_handlers
from src.rendering.grid import Grid # Changed from grid_renderer function to Grid class
from src.rendering import debug_display as debug_renderer
from src.resources.manager import ResourceManager
from src.resources.berry_bush import BerryBush
from src.agents.manager import AgentManager # Added AgentManager

class GameLoop:
    """
    Manages the main game loop with a fixed timestep for updates
    and variable rendering based on available time.
    """
    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.is_running = False
        self.last_time = time.perf_counter()
        self.accumulator = 0.0
        self.dt = 1.0 / config.TARGET_FPS # Timestep duration

        # Initialize Grid
        try:
            self.grid = Grid()
        except ValueError as e:
            print(f"FATAL: Grid initialization failed: {e}")
            # Consider how to handle this - maybe raise exception or exit?
            # For now, let's assume config is valid.
            raise # Re-raise the exception to stop execution if grid fails

        # Initialize font for resource display (ensure pygame.font.init() was called in main)
        try:
            self.resource_font = pygame.font.Font(None, config.RESOURCE_FONT_SIZE)
        except Exception as e:
            print(f"Warning: Could not load default font. Resource text might not display. Error: {e}")
            # Create a fallback font object that might work or fail gracefully in draw
            self.resource_font = pygame.font.Font(pygame.font.get_default_font(), config.RESOURCE_FONT_SIZE)


        # Initialize Resource Manager and spawn initial resources
        self.resource_manager = ResourceManager()
        self._spawn_initial_resources() # Uses screen coords currently

        # Initialize Agent Manager and spawn initial agents
        self.agent_manager = AgentManager(grid=self.grid)
        self._spawn_initial_agents() # Uses grid coords

    def _spawn_initial_agents(self):
        """Creates and places the initial agents."""
        # Example: Spawn agents at specific grid coordinates
        # Ensure these coordinates are valid for the grid size
        initial_positions = [Vector2(5, 5), Vector2(10, 15)]
        agent_speed = config.AGENT_SPEED # Assuming this exists in config

        print(f"Spawning {len(initial_positions)} agents...") # DEBUG
        for pos in initial_positions:
            if self.grid.is_within_bounds(pos):
                agent = self.agent_manager.create_agent(position=pos, speed=agent_speed)
                # Optionally set initial state or target
                # agent.state = AgentState.MOVING_RANDOMLY
                print(f"  Spawned Agent at grid position {pos}") # DEBUG
            else:
                print(f"Warning: Initial agent position {pos} is outside grid bounds ({self.grid.width_in_cells}x{self.grid.height_in_cells}). Skipping.")


    def handle_input(self):
        """Handles user input using the input handler module."""
        if input_handlers.process_events():
            self.is_running = False

    def _spawn_initial_resources(self):
        """Creates and places the initial resource nodes."""
        print(f"Spawning {config.INITIAL_BERRY_BUSHES} berry bushes...") # DEBUG
        spawn_margin = 50 # Avoid spawning too close to screen edges
        for _ in range(config.INITIAL_BERRY_BUSHES):
            # Ensure bushes are placed within screen bounds, respecting margin
            screen_pos_x = random.uniform(spawn_margin, config.SCREEN_WIDTH - spawn_margin)
            screen_pos_y = random.uniform(spawn_margin, config.SCREEN_HEIGHT - spawn_margin)
            screen_position = pygame.Vector2(screen_pos_x, screen_pos_y)
            grid_position = self.grid.screen_to_grid(screen_position) # Convert to grid coordinates
            
            bush = BerryBush(grid_position) # Pass grid coordinates
            self.resource_manager.add_node(bush)
            print(f"DEBUG: Spawned BerryBush at screen_pos: {screen_position}, which is grid_pos: {grid_position}. Bush stores: {bush.position}")

    def update(self, dt):
        """Updates game state, including resource nodes."""
        # Update resource nodes
        self.resource_manager.update_nodes(dt)

        # Update agents
        self.agent_manager.update_agents(dt, self.resource_manager)

        # Placeholder for other game entity updates

    def render(self):
        """Renders the current game state."""
        self.screen.fill(config.COLOR_BLACK) # Clear screen

        # Draw the grid using the Grid object
        self.grid.draw(self.screen)

        # Draw resource nodes
        self.resource_manager.draw_nodes(self.screen, self.resource_font, self.grid) # Pass grid object

        # Draw agents
        self.agent_manager.render_agents(self.screen, self.grid)

        # Draw debug info (FPS)
        # Use clock attribute directly for FPS calculation
        debug_renderer.display_fps(self.screen, self.clock)

        pygame.display.flip() # Update the full display Surface to the screen

    def run(self):
        """Executes the main game loop."""
        self.is_running = True
        self.last_time = time.perf_counter() # Reset timer before loop starts

        while self.is_running:
            current_time = time.perf_counter()
            frame_time = current_time - self.last_time
            self.last_time = current_time

            # Cap frame time to avoid spiral of death
            if frame_time > 0.25:
                frame_time = 0.25

            self.accumulator += frame_time

            # Input handling happens once per frame
            self.handle_input()

            # Fixed timestep updates
            while self.accumulator >= self.dt:
                self.update(self.dt)
                self.accumulator -= self.dt

            # Rendering happens based on available time
            # Optional: Could add interpolation factor here: alpha = self.accumulator / self.dt
            self.render()

            # Yield control, helps manage CPU usage slightly
            # We can use clock.tick here to limit the *rendering* frame rate
            # if needed, but the update logic is decoupled by the fixed step.
            self.clock.tick() # Tick without arg just measures time for get_fps()

        # Pygame quit is handled in main.py after the loop exits