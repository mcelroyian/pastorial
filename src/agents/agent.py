import pygame
from enum import Enum, auto
import random

class AgentState(Enum):
    """Defines the possible states an agent can be in."""
    IDLE = auto()
    MOVING_RANDOMLY = auto()
    MOVING_TO_TARGET = auto()

class Agent:
    """Represents an autonomous agent in the simulation."""

    def __init__(self, position: pygame.math.Vector2, speed: float, grid):
        """
        Initializes an Agent.

        Args:
            position (pygame.math.Vector2): The starting grid coordinates of the agent.
            speed (float): The movement speed of the agent (grid units per second).
            grid (Grid): The simulation grid object.
        """
        self.position = position # Grid coordinates
        self.speed = speed
        self.grid = grid # Store the grid object
        self.state = AgentState.IDLE
        self.target_position: pygame.math.Vector2 | None = None # Grid coordinates
        self.color = (255, 255, 0) # Yellow
        self.state_colors = {
            AgentState.IDLE: (255, 255, 0), # Yellow
            AgentState.MOVING_RANDOMLY: (255, 165, 0), # Orange
            AgentState.MOVING_TO_TARGET: (0, 255, 0), # Green
        }
        # Tolerance for reaching target
        self.target_tolerance = 0.1

    def set_target(self, target_position: pygame.math.Vector2):
        """Sets the agent's target position and changes state."""
        self.target_position = target_position
        self.state = AgentState.MOVING_TO_TARGET
        print(f"Agent at {self.position} set target to {self.target_position}") # Debug

    def _move_towards_target(self, dt: float):
        """Moves the agent towards its target position."""
        if self.target_position is None:
            self.state = AgentState.IDLE
            return

        direction = self.target_position - self.position
        distance = direction.length()

        if distance < self.target_tolerance:
            # Reached target
            self.position = self.target_position # Snap to target
            self.target_position = None
            self.state = AgentState.IDLE
            print(f"Agent reached target at {self.position}") # Debug
        elif distance > 0:
            # Move towards target
            direction.normalize_ip() # Normalize in-place
            movement = direction * self.speed * dt
            # Ensure we don't overshoot
            if movement.length() > distance:
                self.position = self.target_position
                self.target_position = None
                self.state = AgentState.IDLE
                print(f"Agent reached target (overshoot check) at {self.position}") # Debug
            else:
                self.position += movement

    def _move_randomly(self, dt: float):
        """Moves the agent randomly within the grid bounds."""
        # Simple random movement: If idle or finished random move, pick a new random target within grid bounds
        if self.target_position is None:
            self.target_position = pygame.math.Vector2(
                random.uniform(0, self.grid.width_in_cells - 1),
                random.uniform(0, self.grid.height_in_cells - 1)
            )
            # Ensure target is valid if grid is small
            self.target_position.x = max(0, min(self.target_position.x, self.grid.width_in_cells - 1))
            self.target_position.y = max(0, min(self.target_position.y, self.grid.height_in_cells - 1))
            print(f"Agent at {self.position} moving randomly towards {self.target_position}") # Debug
        # Use the move_towards_target logic to handle the actual movement
        self._move_towards_target(dt)

        # If we reached the random target, clear it so a new one is picked next time
        if self.state == AgentState.IDLE:
            self.target_position = None
            # Stay in MOVING_RANDOMLY state until explicitly changed
            self.state = AgentState.MOVING_RANDOMLY


    def update(self, dt: float):
        """Updates the agent's state and position based on delta time."""
        if self.state == AgentState.MOVING_TO_TARGET:
            self._move_towards_target(dt)
        elif self.state == AgentState.MOVING_RANDOMLY:
            self._move_randomly(dt)
        # No action needed for IDLE state

    def draw(self, screen: pygame.Surface, grid):
        """Draws the agent on the screen."""
        # Use the stored grid object's method to convert grid coords to screen coords
        screen_pos = self.grid.grid_to_screen(self.position)
        current_color = self.state_colors.get(self.state, self.color)
        # Draw a circle representing the agent
        # Use grid cell size for radius calculation (e.g., half cell size)
        radius = self.grid.cell_width // 2
        pygame.draw.circle(screen, current_color, screen_pos, radius)