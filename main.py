import pygame
import sys
import logging
import asyncio
from src.core import config
from src.core.game_loop import GameLoop
from src.rendering import debug_display
from src.core.logger import setup_logging

async def main():
    """Initializes Pygame, creates the game window and runs the game loop."""
    # Configure logging:
    # - Default log level is INFO.
    # - Set 'src.agents.agent' logger to DEBUG for more detailed agent logs.
    per_module_log_levels = {
        "src.agents.agent": logging.INFO,
        "src.agents.agent_behaviors": logging.INFO,
        "src.resources.storage_point": logging.INFO,
        "src.resources.node": logging.INFO,
        "src.pathfinding.astar": logging.INFO,
        "src.tasks.task_manager": logging.INFO,
        "src.tasks.task": logging.INFO
    }
    setup_logging(default_level=logging.INFO, per_module_levels=per_module_log_levels)
    logger = logging.getLogger(__name__)

    try:
        pygame.init()
        logger.info("Pygame initialized successfully.")
    except Exception as e:
        logger.critical(f"Pygame initialization failed: {e}")
        sys.exit(1)

    # Initialize font module for debug display
    # It's better to initialize it once here than potentially multiple times
    # or checking every frame in the display function.
    try:
        pygame.font.init()
        logger.info("Pygame font module initialized successfully.")
        # debug_display.init_debug_font() is called within display_fps if needed now
    except Exception as e:
        logger.error(f"pygame.font.init() failed: {e}")
        # Continue without font if it fails, but log it.

    try:
        screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        logger.info(f"Screen set to {config.SCREEN_WIDTH}x{config.SCREEN_HEIGHT}")
    except Exception as e:
        logger.critical(f"Failed to set screen mode: {e}")
        pygame.quit()
        sys.exit(1)

    pygame.display.set_caption("Pastorial - Resource Chain Simulator")
    logger.info("Window caption set.")

    # Create and run the game loop
    try:
        game = GameLoop(screen)
        logger.info("GameLoop initialized.")
    except Exception as e:
        logger.critical(f"Error initializing GameLoop: {e}")
        raise

    try:
        logger.info("Starting game run loop.")
        await game.run()
    except Exception as e:
        logger.critical(f"FATAL: Error during game.run(): {e}")
        raise
    finally:
        logger.info("Game loop ended. Quitting Pygame.")

    # Quit Pygame and exit the program
    pygame.quit()
    sys.exit()

if __name__ == '__main__':
    asyncio.run(main())