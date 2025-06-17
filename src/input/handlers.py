import pygame

def process_events():
    """
    Processes Pygame events.
    Returns a dictionary of actions, e.g., {'quit': False, 'toggle_panel': False}.
    """
    actions = {
        'quit': False,
        'toggle_panel': False,
        'toggle_pause': False,
        'mouse_click': None,
        'toggle_manual_mode': False
    }
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            actions['quit'] = True
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_t:
                actions['toggle_panel'] = True
            elif event.key == pygame.K_p:
                actions['toggle_pause'] = True
            elif event.key == pygame.K_m:
                actions['toggle_manual_mode'] = True
        elif event.type == pygame.MOUSEBUTTONDOWN:
            actions['mouse_click'] = event.pos
            
    return actions