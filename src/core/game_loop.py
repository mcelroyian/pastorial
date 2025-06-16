import pygame
import asyncio
import time
import random
import logging # Added
from typing import List, Optional, Any # Added for type hinting
from pygame.math import Vector2 # Added for agent positions
from src.core import config
from src.input import handlers as input_handlers
from src.rendering.grid import Grid # Changed from grid_renderer function to Grid class
from src.rendering import debug_display as debug_renderer
from src.resources.manager import ResourceManager
from src.resources.berry_bush import BerryBush
from src.resources.wheat_field import WheatField # Added WheatField
from src.resources.water_source import WaterSource
from src.resources.mill import Mill # Added Mill
from src.resources.bakery import Bakery
from src.agents.manager import AgentManager # Added AgentManager
from src.tasks.task_manager import TaskManager # Added TaskManager
from src.resources.storage_point import StoragePoint
from src.resources.resource_types import ResourceType
from src.rendering.task_status_display import TaskStatusDisplay # Added for Task UI

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
        self.show_task_panel = True # Added for toggling task panel visibility
        self.logger = logging.getLogger(__name__) # Added
 
        # Initialize Grid
        try:
            self.grid = Grid()
            self.logger.info("Grid initialized successfully.") # Added
        except ValueError as e:
            self.logger.critical(f"Grid initialization failed: {e}") # Changed
            # Consider how to handle this - maybe raise exception or exit?
            # For now, let's assume config is valid.
            raise # Re-raise the exception to stop execution if grid fails

        # Occupancy grid is now managed by self.grid

        # Initialize font for resource display (ensure pygame.font.init() was called in main)
        try:
            self.resource_font = pygame.font.Font(None, config.RESOURCE_FONT_SIZE)
            self.logger.info("Resource display font loaded.") # Added
        except Exception as e:
            self.logger.warning(f"Could not load default font for resource display. Error: {e}") # Changed
            # Create a fallback font object that might work or fail gracefully in draw
            self.resource_font = pygame.font.Font(pygame.font.get_default_font(), config.RESOURCE_FONT_SIZE)


        # Initialize Resource Manager and spawn initial resources
        self.resource_manager = ResourceManager()
        self._spawn_initial_resources() # Will also spawn Mills here
        self._spawn_initial_storage_points()

        # Initialize Task Manager
        # AgentManager needs a TaskManager, and TaskManager needs an AgentManager.
        # Initialize TaskManager first, potentially with a placeholder for agent_manager_ref if needed,
        # or ensure TaskManager can function/be updated before agent_manager_ref is fully set.
        # Based on current TaskManager constructor, it needs resource_manager and agent_manager.
        # Let's initialize AgentManager first, then TaskManager, then link them.

        # Initialize Agent Manager (will need TaskManager soon)
        # For now, AgentManager's __init__ takes task_manager. So TaskManager must be first.
        self.task_manager = TaskManager(resource_manager=self.resource_manager, agent_manager=None) # type: ignore
        
        # Initialize Agent Manager and pass the TaskManager
        self.agent_manager = AgentManager(grid=self.grid, task_manager=self.task_manager) # occupancy_grid removed
        
        # Now, set the agent_manager_ref in TaskManager
        self.task_manager.agent_manager_ref = self.agent_manager

        self._spawn_initial_agents() # Uses grid coords

        # Initialize UI Font and Task Display Panel
        try:
            self.ui_font = pygame.font.Font(None, 24) # General UI font, size can be from config
            self.logger.info("UI font loaded.") # Added
        except Exception as e:
            self.logger.warning(f"Could not load default font for UI. Error: {e}") # Changed
            self.ui_font = pygame.font.Font(pygame.font.get_default_font(), 24)

        panel_width = 350  # Width of the task panel
        panel_height = config.SCREEN_HEIGHT
        panel_x = config.SCREEN_WIDTH - panel_width
        panel_y = 0
        task_panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        
        self.task_display = TaskStatusDisplay(
            task_manager=self.task_manager,
            font=self.ui_font, # Use a dedicated UI font
            panel_rect=task_panel_rect,
            screen_surface=self.screen,
            config_module=config # Pass the config module
        )

    def _spawn_initial_agents(self):
        """Creates and places the initial agents."""
        # Example: Spawn agents at specific grid coordinates
        # Ensure these coordinates are valid for the grid size
        for _ in range(config.INITIAL_AGENTS):
            screen_pos_x = random.uniform(config.SCREEN_SPAWN_MARGIN, config.SCREEN_WIDTH - config.SCREEN_SPAWN_MARGIN)
            screen_pos_y = random.uniform(config.SCREEN_SPAWN_MARGIN, config.SCREEN_HEIGHT - config.SCREEN_SPAWN_MARGIN)
            screen_position = pygame.Vector2(screen_pos_x, screen_pos_y)
            grid_position = self.grid.screen_to_grid(screen_position) # Convert to grid coordinates
            
            # Agents are 1x1
            entity_grid_width = 1
            entity_grid_height = 1
            gx, gy = int(grid_position.x), int(grid_position.y)

            if self.grid.is_area_free(gx, gy, entity_grid_width, entity_grid_height):
                agent = self.agent_manager.create_agent(position=grid_position, speed=config.AGENT_SPEED) # Pass grid position
                self.grid.update_occupancy(agent, gx, gy, entity_grid_width, entity_grid_height, is_placing=True)
                self.logger.debug(f"Spawned Agent {agent.id} at grid position {grid_position}") # Changed
            else:
                self.logger.warning(f"Could not spawn agent at {grid_position}, area occupied.") # Changed


    def handle_input(self):
        """Handles user input using the input handler module."""
        user_actions = input_handlers.process_events()
        if user_actions['quit']:
            self.is_running = False
        if user_actions['toggle_panel']:
            self.show_task_panel = not self.show_task_panel

    def _spawn_entity(self, entity_class, num_to_spawn, **kwargs):
        """
        Generic function to spawn a specified number of entities of a given class.
        """
        entity_name = entity_class.__name__
        self.logger.info(f"Attempting to spawn {num_to_spawn} {entity_name}(s)...")

        entity_grid_width = getattr(entity_class, 'GRID_WIDTH', 1)
        entity_grid_height = getattr(entity_class, 'GRID_HEIGHT', 1)

        available_spots = self._find_available_spawn_points(entity_grid_width, entity_grid_height)

        if not available_spots:
            self.logger.warning(f"No available space found to spawn any {entity_name}s of size {entity_grid_width}x{entity_grid_height}.")
            return

        random.shuffle(available_spots)
        
        spawned_count = 0
        for i in range(min(num_to_spawn, len(available_spots))):
            pos_vec = available_spots[i]
            gx, gy = int(pos_vec.x), int(pos_vec.y)
            
            entity = entity_class(pos_vec, **kwargs)
            
            if isinstance(entity, (Mill, Bakery)):
                self.resource_manager.add_processing_station(entity)
            else:
                self.resource_manager.add_node(entity)

            self.grid.update_occupancy(entity, gx, gy, entity_grid_width, entity_grid_height, is_placing=True)
            self.logger.debug(f"Spawned {entity_name} (size {entity_grid_width}x{entity_grid_height}) at grid_pos: {pos_vec}")
            spawned_count += 1

        if spawned_count < num_to_spawn:
            self.logger.warning(f"Successfully spawned {spawned_count} out of {num_to_spawn} desired {entity_name}s due to limited available space.")
        elif spawned_count > 0:
            self.logger.info(f"Successfully spawned {spawned_count} {entity_name}(s).")

    def _spawn_initial_resources(self):
        """Creates and places the initial resource nodes using the generic spawn function."""
        self._spawn_entity(BerryBush, config.INITIAL_BERRY_BUSHES)
        self._spawn_entity(WheatField, config.INITIAL_WHEAT_FIELD)
        self._spawn_entity(WaterSource, config.INITIAL_WELLS)
        self._spawn_entity(Mill, config.DESIRED_NUM_MILLS)
        self._spawn_entity(Bakery, config.INITIAL_BAKERIES)

    def _spawn_initial_storage_points(self):
        """Creates and places the initial storage points."""
        # Calculate middle of the screen in grid coordinates
        middle_screen_x_pixels = config.SCREEN_WIDTH / 2
        middle_screen_y_pixels = config.SCREEN_HEIGHT / 2
        middle_screen_pixel_pos = pygame.math.Vector2(middle_screen_x_pixels, middle_screen_y_pixels)
        storage_position_grid_float = self.grid.screen_to_grid(middle_screen_pixel_pos)
        sgx, sgy = int(storage_position_grid_float.x), int(storage_position_grid_float.y)
        storage_position_grid = Vector2(sgx, sgy) # Use int coords for placement

        # Storage points are 1x1
        entity_grid_width = 1
        entity_grid_height = 1

        # Define storage point properties
        capacity = config.DEFAULT_STORAGE_CAPACITY
        accepted_types = [ResourceType.BERRY, ResourceType.WHEAT]

        if self.grid.is_area_free(sgx, sgy, entity_grid_width, entity_grid_height):
            berry_storage_point = StoragePoint(
                position=storage_position_grid,
                overall_capacity=capacity,
                accepted_resource_types=accepted_types
            )
            self.resource_manager.add_storage_point(berry_storage_point)
            self.grid.update_occupancy(berry_storage_point, sgx, sgy, entity_grid_width, entity_grid_height, is_placing=True)
            self.logger.debug(f"Spawned StoragePoint at grid_pos: {storage_position_grid} for BERRY and WHEAT with capacity {capacity}") # Changed
        else:
            self.logger.warning(f"Could not spawn BERRY/WHEAT StoragePoint at {storage_position_grid}, area occupied.") # Changed


        # Spawn StoragePoint for Flour Powder
        flour_storage_pos_float = Vector2(self.grid.width_in_cells / 2 + 5, self.grid.height_in_cells / 2)
        fsgx, fsgy = int(flour_storage_pos_float.x), int(flour_storage_pos_float.y)
        
        # Ensure it's on grid by clamping, then use these clamped values
        fsgx = max(0, min(fsgx, self.grid.width_in_cells -1))
        fsgy = max(0, min(fsgy, self.grid.height_in_cells -1))
        flour_storage_position_grid = Vector2(fsgx, fsgy)


        flour_storage_capacity = 30
        flour_accepted_types = [ResourceType.FLOUR_POWDER, ResourceType.BREAD]
 
        if self.grid.is_area_free(fsgx, fsgy, entity_grid_width, entity_grid_height): # Still 1x1
            flour_storage_point = StoragePoint(
                position=flour_storage_position_grid,
                overall_capacity=flour_storage_capacity,
                accepted_resource_types=flour_accepted_types
            )
            self.resource_manager.add_storage_point(flour_storage_point)
            self.grid.update_occupancy(flour_storage_point, fsgx, fsgy, entity_grid_width, entity_grid_height, is_placing=True)
            self.logger.debug(f"Spawned StoragePoint at grid_pos: {flour_storage_position_grid} for FLOUR_POWDER with capacity {flour_storage_capacity}") # Changed
        else:
            self.logger.warning(f"Could not spawn FLOUR StoragePoint at {flour_storage_position_grid}, area occupied.") # Changed

    # Grid Occupancy Helper Functions are now part of the Grid class.
    # GameLoop will call self.grid.is_area_free() and self.grid.update_occupancy()

    def remove_entity_from_occupancy(self, entity: Any):
        """
        Placeholder for removing an entity and clearing its footprint from the occupancy_grid.
        This would be called when an entity is destroyed or removed from the game.
        Assumes entity has position, grid_width, and grid_height attributes.
        """
        if not hasattr(entity, 'position') or \
           not hasattr(entity, 'grid_width') or \
           not hasattr(entity, 'grid_height'):
            self.logger.warning(f"Tried to remove entity {entity} from occupancy, but it's missing required attributes (position, grid_width, or grid_height).") # Changed
            return

        start_x = int(entity.position.x)
        start_y = int(entity.position.y)
        width = entity.grid_width
        height = entity.grid_height
        
        # Call grid's update_occupancy with is_placing=False
        self.grid.update_occupancy(entity, start_x, start_y, width, height, is_placing=False)
        self.logger.debug(f"Cleared occupancy for entity {entity} at ({start_x},{start_y}) with size ({width}x{height}).") # Changed

    def _find_available_spawn_points(self, entity_grid_width: int, entity_grid_height: int) -> List[Vector2]:
        """
        Scans the grid to find all valid top-left coordinates where an entity
        of the given dimensions can be placed without overlapping or going out of bounds.
        """
        available_spots: List[Vector2] = []
        # Iterate considering the entity's dimensions to prevent out-of-bounds access
        # The loop range ensures that the entity fully fits within the grid.
        # Uses grid's dimensions now.
        for gy in range(self.grid.height_in_cells - entity_grid_height + 1):
            for gx in range(self.grid.width_in_cells - entity_grid_width + 1):
                if self.grid.is_area_free(gx, gy, entity_grid_width, entity_grid_height):
                    available_spots.append(Vector2(gx, gy))
        return available_spots

    def update(self, dt):
        """Updates game state, including resource nodes."""
        # Update resource nodes
        self.resource_manager.update_nodes(dt)

        # Update Task Manager (e.g., for task generation, timeouts)
        self.task_manager.update(dt)

        # Update agents (agents will interact with TaskManager)
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

        # Draw the Task Status Display Panel
        if hasattr(self, 'task_display') and self.show_task_panel: # Ensure it's initialized and toggled on
            self.task_display.draw()

        pygame.display.flip() # Update the full display Surface to the screen

    async def run(self):
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
            await asyncio.sleep(0)

        # Pygame quit is handled in main.py after the loop exits