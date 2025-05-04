import pygame
import time
import random # Added for random placement
from src.core import config
from src.input import handlers as input_handlers
from src.rendering import grid as grid_renderer
from src.rendering import debug_display as debug_renderer
from src.resources.manager import ResourceManager # Added
from src.resources.berry_bush import BerryBush # Added

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

        # Initialize font for resource display (ensure pygame.font.init() was called in main)
        try:
            self.resource_font = pygame.font.Font(None, config.RESOURCE_FONT_SIZE)
        except Exception as e:
            print(f"Warning: Could not load default font. Resource text might not display. Error: {e}")
            # Create a fallback font object that might work or fail gracefully in draw
            self.resource_font = pygame.font.Font(pygame.font.get_default_font(), config.RESOURCE_FONT_SIZE)


        # Initialize Resource Manager and spawn initial resources
        self.resource_manager = ResourceManager()
        self._spawn_initial_resources()

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
            pos_x = random.uniform(spawn_margin, config.SCREEN_WIDTH - spawn_margin)
            pos_y = random.uniform(spawn_margin, config.SCREEN_HEIGHT - spawn_margin)
            position = pygame.Vector2(pos_x, pos_y)
            bush = BerryBush(position)
            self.resource_manager.add_node(bush)
            print(f"  Spawned BerryBush at {position}") # DEBUG

    def update(self, dt):
        """Updates game state, including resource nodes."""
        # Update resource nodes
        self.resource_manager.update_nodes(dt)

        # Placeholder for other game entity updates
        pass

    def render(self):
        """Renders the current game state."""
        self.screen.fill(config.COLOR_BLACK) # Clear screen

        # Draw the grid
        grid_renderer.draw_grid(self.screen)

        # Draw resource nodes
        self.resource_manager.draw_nodes(self.screen, self.resource_font)

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