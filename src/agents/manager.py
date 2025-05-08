import pygame
from typing import List
from .agent import Agent # Relative import from the same package
from ..resources.resource_types import ResourceType

class AgentManager:
    """Manages all agents in the simulation."""

    def __init__(self, grid):
        """
        Initializes the AgentManager.

        Args:
            grid (Grid): The simulation grid object.
        """
        self.agents: List[Agent] = []
        self.grid = grid # Store the grid object

    def add_agent(self, agent: Agent):
        """Adds an existing Agent instance to the manager."""
        self.agents.append(agent)

    def create_agent(self, position: pygame.math.Vector2, speed: float) -> Agent:
        """
        Creates a new Agent, adds it to the manager, and returns it.

        Args:
            position (pygame.math.Vector2): The starting position of the agent.
            speed (float): The movement speed of the agent.

        Returns:
            Agent: The newly created agent instance.
        """
        # Pass the stored grid object to the Agent constructor
        new_agent = Agent(position=position, speed=speed, grid=self.grid, resource_priorities=[ResourceType.BERRY],  # Example priority
                        inventory_capacity=5)
        self.add_agent(new_agent)
        print(f"Created agent at {position}") # Debug
        return new_agent

    def update_agents(self, dt: float, resource_manager):
        """Updates all managed agents."""
        for agent in self.agents:
            agent.update(dt, resource_manager)

    def render_agents(self, screen: pygame.Surface, grid):
        """Renders all managed agents."""
        # Render agents after other elements like the grid, but potentially before UI
        for agent in self.agents:
            agent.draw(screen, grid)