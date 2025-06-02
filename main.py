import pygame
import sys
import logging # Added
from src.core import config
from src.core.game_loop import GameLoop
from src.rendering import debug_display
from src.core.logger import setup_logging # Added

def main():
    """Initializes Pygame, creates the game window and runs the game loop."""
    # Configure logging:
    # - Default log level is INFO.
    # - Set 'src.agents.agent' logger to DEBUG for more detailed agent logs.
    per_module_log_levels = {
        "src.agents.agent": logging.DEBUG,
        "src.agents.agent_behaviors": logging.INFO,
        "src.resources.storage_point": logging.DEBUG, # Changed for StoragePoint debugging
        "src.resources.node": logging.INFO,
        "src.pathfinding.astar": logging.INFO,
        "src.tasks.task_manager": logging.DEBUG, # Added for TaskManager debugging
        "src.tasks.task": logging.DEBUG # Added for Task debugging
    }
    setup_logging(default_level=logging.INFO, per_module_levels=per_module_log_levels)
    logger = logging.getLogger(__name__) # Added

    try:
        pygame.init()
        logger.info("Pygame initialized successfully.") # Added
    except Exception as e:
        logger.critical(f"Pygame initialization failed: {e}") # Changed
        sys.exit(1)

    # Initialize font module for debug display
    # It's better to initialize it once here than potentially multiple times
    # or checking every frame in the display function.
    try:
        pygame.font.init()
        logger.info("Pygame font module initialized successfully.") # Added
        # debug_display.init_debug_font() is called within display_fps if needed now
    except Exception as e:
        logger.error(f"pygame.font.init() failed: {e}") # Changed
        # Continue without font if it fails, but log it.

    try:
        screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        logger.info(f"Screen set to {config.SCREEN_WIDTH}x{config.SCREEN_HEIGHT}") # Added
    except Exception as e:
        logger.critical(f"Failed to set screen mode: {e}") # Changed
        pygame.quit()
        sys.exit(1)

    pygame.display.set_caption("Pastorial - Resource Chain Simulator")
    logger.info("Window caption set.") # Added

    # Create and run the game loop
    try:
        game = GameLoop(screen)
        logger.info("GameLoop initialized.") # Added
    except Exception as e:
        logger.critical(f"Error initializing GameLoop: {e}")  # Changed
        raise  # Re-raise the exception to see the full traceback
        pygame.quit()
        sys.exit(1)

    try:
        logger.info("Starting game run loop.") # Added
        game.run()
    except Exception as e:
        logger.critical(f"FATAL: Error during game.run(): {e}") # Changed
        raise
    finally: # Added
        logger.info("Game loop ended. Quitting Pygame.") # Added

    # Quit Pygame and exit the program
    pygame.quit()
    sys.exit()

if __name__ == '__main__':
    main()