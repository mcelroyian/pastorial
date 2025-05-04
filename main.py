import pygame
import sys
from src.core import config
from src.core.game_loop import GameLoop
from src.rendering import debug_display

def main():
    """Initializes Pygame, creates the game window and runs the game loop."""
    try:
        pygame.init()
    except Exception as e:
        sys.exit(1)

    # Initialize font module for debug display
    # It's better to initialize it once here than potentially multiple times
    # or checking every frame in the display function.
    try:
        pygame.font.init()
        # debug_display.init_debug_font() is called within display_fps if needed now
    except Exception as e:
        print(f"ERROR: pygame.font.init() failed: {e}") # DEBUG
        # Continue without font if it fails, but log it.

    try:
        screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))

    except Exception as e:
        pygame.quit()
        sys.exit(1)

    pygame.display.set_caption("Pastorial - Resource Chain Simulator")

    # Create and run the game loop
    try:
        game = GameLoop(screen)
    except Exception as e:
        pygame.quit()
        sys.exit(1)

    try:
        game.run()
    except Exception as e:
        print(f"FATAL: Error during game.run(): {e}") # DEBUG


    # Quit Pygame and exit the program
    pygame.quit()
    sys.exit()

if __name__ == '__main__':
    main()