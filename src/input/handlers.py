import pygame

def process_events():
    """
    Processes Pygame events.
    Returns a dictionary of actions, e.g., {'quit': False, 'toggle_panel': False}.
    """
    actions = {'quit': False, 'toggle_panel': False}
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            actions['quit'] = True
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_t:
                actions['toggle_panel'] = True
    return actions