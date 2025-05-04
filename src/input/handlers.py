import pygame

def process_events():
    """
    Processes Pygame events.
    Returns True if the game should quit, False otherwise.
    """
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return True # Signal to quit
    return False # Continue running