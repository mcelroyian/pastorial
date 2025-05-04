import pygame
from src.core import config

# Initialize font module (ideally done once at startup in main)
# pygame.font.init() # Assuming it's initialized in main.py later
debug_font = None

def init_debug_font():
    """Initializes the font used for debug text."""
    global debug_font
    # Prioritize Pygame's default font due to potential system font issues (fc-list missing)
    try:
        debug_font = pygame.font.Font(None, 20) # Pygame's default font
    except Exception as e:
        debug_font = None # Ensure it's None if default fails

def display_fps(surface, clock):
    """Renders the current FPS onto the surface."""
    # print("DEBUG: display_fps called") # DEBUG - Redundant with GameLoop log
    if not debug_font:
        init_debug_font() # Initialize if not already done

    if debug_font:
        # print("DEBUG: display_fps - debug_font available, rendering FPS") # DEBUG
        fps = clock.get_fps()
        fps_text = f"FPS: {fps:.2f}"
        try:
            text_surface = debug_font.render(fps_text, True, config.DEBUG_TEXT_COLOR)
            surface.blit(text_surface, (10, 10)) # Position at top-left
            # print("DEBUG: display_fps - FPS text blitted") # DEBUG
        except Exception as e: 
            print(f"ERROR: Failed to render FPS text: {e}")