import pygame
import logging # Added
from src.core import config

# Initialize font module (ideally done once at startup in main)
# pygame.font.init() # Assuming it's initialized in main.py later
debug_font = None
logger = logging.getLogger(__name__) # Added

def init_debug_font():
    """Initializes the font used for debug text."""
    global debug_font
    # Prioritize Pygame's default font due to potential system font issues (fc-list missing)
    try:
        debug_font = pygame.font.Font(None, 20) # Pygame's default font
        logger.info("Debug font initialized.") # Added
    except Exception as e:
        logger.error(f"Failed to initialize debug font: {e}") # Added
        debug_font = None # Ensure it's None if default fails

def display_fps(surface, clock):
    """Renders the current FPS onto the surface."""
    # logger.debug("display_fps called") # Changed - Redundant with GameLoop log
    if not debug_font:
        init_debug_font() # Initialize if not already done

    if debug_font:
        # logger.debug("display_fps - debug_font available, rendering FPS") # Changed
        fps = clock.get_fps()
        fps_text = f"FPS: {fps:.2f}"
        try:
            text_surface = debug_font.render(fps_text, True, config.DEBUG_TEXT_COLOR)
            surface.blit(text_surface, (10, 10)) # Position at top-left
            # logger.debug("display_fps - FPS text blitted") # Changed
        except Exception as e:
            logger.error(f"Failed to render FPS text: {e}") # Changed