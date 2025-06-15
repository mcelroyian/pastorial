Okay, I can help you with a plan to implement the visual state overlays and provide notes for future improvements based on our discussion.

The core idea for the initial implementation is to **display key agent state information as text above each agent**, which can be toggled on and off.

---
## Plan for Implementing Visual State Overlays

This plan focuses on rendering text above each agent to show its current behavior and intent.

1.  **Objective**:
    * Display the agent's current behavior class name and a short description of its current intent (if any) as text above each agent.
    * This display should be toggleable via a keyboard shortcut.

2.  **Files to Modify**:
    * `input/handlers.py`: To register the toggle key.
    * `core/game_loop.py`: To manage the toggle state and pass it down.
    * `agents/manager.py`: To relay the toggle state to individual agents.
    * `agents/agent.py`: To implement the text rendering in the `draw` method.
    * `rendering/debug_display.py`: To ensure the debug font is accessible.
    * `core/config.py`: For text color.

3.  **Detailed Implementation Steps**:

    * **Step 1: Input Handling for Toggle**
        * In `input/handlers.py` (`process_events` function):
            * Add a new key to the `actions` dictionary, e.g., `actions['toggle_agent_debug_text'] = False`.
            * In the event loop, listen for a key press (e.g., `pygame.K_d`):
                ```python
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_t: # Existing
                        actions['toggle_panel'] = True
                    if event.key == pygame.K_d: # New for agent debug text
                        actions['toggle_agent_debug_text'] = True
                ```

    * **Step 2: Manage Toggle State in GameLoop**
        * In `core/game_loop.py` (`GameLoop` class `__init__`):
            * Add a new attribute: `self.show_agent_debug_text = False`.
            * Ensure `debug_display.init_debug_font()` is called if it's not already, or rely on its lazy initialization in `debug_display.display_fps`. For robustness, you can call it once here:
                ```python
                # In GameLoop __init__
                from src.rendering import debug_display
                debug_display.init_debug_font() # Ensure debug font is loaded once
                ```
        * In `core/game_loop.py` (`handle_input` method):
            * Add logic to toggle the new attribute:
                ```python
                if user_actions['toggle_agent_debug_text']:
                    self.show_agent_debug_text = not self.show_agent_debug_text
                ```
        * In `core/game_loop.py` (`render` method):
            * Pass the `self.show_agent_debug_text` flag to the agent manager's rendering method:
                ```python
                # In render method
                self.agent_manager.render_agents(self.screen, self.grid, self.show_agent_debug_text)
                ```

    * **Step 3: Pass Toggle State Through AgentManager**
        * In `agents/manager.py` (`AgentManager` class `render_agents` method):
            * Modify the method signature to accept the new flag:
                ```python
                def render_agents(self, screen: pygame.Surface, grid, show_debug_text: bool = False):
                ```
            * Pass this flag to each agent's `draw` method:
                ```python
                for agent in self.agents:
                    agent.draw(screen, grid, show_debug_text) # Pass the flag
                ```

    * **Step 4: Implement Text Rendering in Agent**
        * In `agents/agent.py` (`Agent` class `draw` method):
            * Modify the method signature:
                ```python
                def draw(self, screen: pygame.Surface, grid, show_debug_text: bool = False):
                ```
            * Import necessary modules at the top of `agents/agent.py`:
                ```python
                from ..rendering import debug_display # For the font
                # config is already imported
                ```
            * Inside the `draw` method, after drawing the agent's circle and inventory icon, add the following logic:
                ```python
                if show_debug_text and debug_display.debug_font:
                    debug_info_lines = []
                    # Behavior Text
                    behavior_name = self.current_behavior.__class__.__name__
                    if "Behavior" in behavior_name: # Shorten common suffix
                        behavior_name = behavior_name.replace("Behavior", "")
                    debug_info_lines.append(f"B: {behavior_name}")

                    # Intent Text
                    if self.current_intent:
                        intent_desc = self.current_intent.get_description()
                        max_len = 30  # Max length for intent description on screen
                        if len(intent_desc) > max_len:
                            intent_desc = intent_desc[:max_len-3] + "..."
                        debug_info_lines.append(f"I: {intent_desc}")
                    else:
                        debug_info_lines.append("I: None")
                    
                    # Optional: Agent short ID
                    # debug_info_lines.append(f"ID: {str(self.id)[:4]}")

                    line_height = debug_display.debug_font.get_height() + 1
                    for i, text_line in enumerate(debug_info_lines):
                        text_surface = debug_display.debug_font.render(text_line, True, self.config.DEBUG_TEXT_COLOR)
                        # Position text lines above the agent, stacked vertically
                        text_rect = text_surface.get_rect(centerx=screen_pos[0])
                        text_rect.bottom = screen_pos[1] - agent_radius - 5 - ( (len(debug_info_lines) - 1 - i) * line_height )
                        screen.blit(text_surface, text_rect)
                ```

This plan provides a straightforward way to get immediate visual feedback on agent states directly in the simulation.

---
## Notes for Next Improvements 💡

Once the basic visual state overlay is implemented, you can progressively enhance your debugging capabilities. Here are some notes for improvements, keeping simplicity and impact in mind:

1.  **Click-to-Inspect Agent Details**:
    * **Concept**: Allow clicking on an agent to show a dedicated debug panel or overlay with more comprehensive information for that specific agent (e.g., full current intent, path, inventory details, recent errors).
    * **Benefit**: Reduces screen clutter from constant overlays while providing deep-dive capability when needed.

2.  **Visual Path and Target Drawing**:
    * **Concept**: When agent debug text is active (or via another toggle), draw the agent's current `current_path` (list of waypoints) on the grid. Highlight `target_position` and `final_destination`.
    * **Benefit**: Instantly see where an agent is going and diagnose pathfinding issues or stuck agents.

3.  **Agent History Trails**:
    * **Concept**: Store and draw the last N positions of an agent, perhaps color-coding the trail segments by the agent's behavior at that time.
    * **Benefit**: Helps understand agent movement patterns, oscillations, or if an agent frequently gets stuck in a particular area or state.

4.  **Task Link Visualization**:
    * **Concept**: Draw a subtle line from an agent to its key task-related entities (e.g., target resource node for `GatherAndDeliverTask`, or target `StoragePoint`/`Mill`).
    * **Benefit**: Makes it easier to understand what task an agent is performing and its current objective in the world.

5.  **Enhanced Occupancy Grid Visualization**:
    * **Concept**: Add a toggle to render the `Grid.occupancy_grid` directly, showing which cells are marked as occupied.
    * **Benefit**: Helps debug agent placement, pathfinding on occupied cells, and issues with entity placement logic.

6.  **Resource Node/Storage Point Debug Info**:
    * **Concept**: Similar to agent debug text, add toggleable text overlays for resource nodes (e.g., `claimed_by_task_id`) and storage points (e.g., `reservations`, `pickup_reservations`).
    * **Benefit**: Quick insight into resource states and reservation conflicts.

7.  **Improved Readability and Layout**:
    * **Concept**: Refine the positioning of debug text to avoid overlap, especially when many agents are close. Potentially use smaller fonts or contextually reduce information density.
    * **Benefit**: Makes the debug information more usable in dense scenarios.

Start with the plan for visual state overlays, as it provides a high "bang for your buck." Then, consider these improvements based on the specific debugging challenges you encounter. Good luck!