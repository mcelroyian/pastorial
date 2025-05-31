import pygame
import uuid # For generating agent IDs
from typing import List, TYPE_CHECKING, Any, Optional # Added Any, Optional
from .agent import Agent # Relative import from the same package
from ..resources.resource_types import ResourceType

if TYPE_CHECKING:
    from ..tasks.task_manager import TaskManager
    # from ..core.grid import Grid # Assuming Grid class type hint

class AgentManager:
    """Manages all agents in the simulation."""

    def __init__(self, grid, task_manager: 'TaskManager'): # occupancy_grid removed
        """
        Initializes the AgentManager.

        Args:
            grid (Grid): The simulation grid object.
            task_manager (TaskManager): Reference to the task manager.
        """
        self.agents: List[Agent] = []
        self.grid = grid # Store the grid object
        self.task_manager_ref: 'TaskManager' = task_manager # Store task_manager reference
        # self.occupancy_grid = occupancy_grid # Removed

    def add_agent(self, agent: Agent):
        """Adds an existing Agent instance to the manager."""
        self.agents.append(agent)

    def create_agent(self,
                     position: pygame.math.Vector2,
                     speed: float,
                     inventory_capacity: int = 5, # Default value from plan/previous code
                     resource_priorities: List[ResourceType] = None # Default to None or sensible default
                     ) -> Agent:
        """
        Creates a new Agent, adds it to the manager, and returns it.

        Args:
            position (pygame.math.Vector2): The starting position of the agent.
            speed (float): The movement speed of the agent.
            inventory_capacity (int): Agent's inventory capacity.
            resource_priorities (List[ResourceType]): Agent's resource priorities.

        Returns:
            Agent: The newly created agent instance.
        """
        agent_id = uuid.uuid4()
        if resource_priorities is None:
            # Provide a default if not specified, e.g. based on global config or common resources
            resource_priorities = [ResourceType.BERRY, ResourceType.WHEAT]

        new_agent = Agent(
            agent_id=agent_id,
            position=position,
            speed=speed,
            grid=self.grid,
            task_manager=self.task_manager_ref, # Pass the TaskManager reference
            # occupancy_grid=self.occupancy_grid, # Removed
            inventory_capacity=inventory_capacity,
            resource_priorities=resource_priorities
        )
        self.add_agent(new_agent)
        print(f"Created agent {agent_id} at {position}") # Debug
        return new_agent

    def update_agents(self, dt: float, resource_manager): # resource_manager type hint can be added
        """Updates all managed agents."""
        for agent in self.agents:
            agent.update(dt, resource_manager)

    def render_agents(self, screen: pygame.Surface, grid):
        """Renders all managed agents."""
        # Render agents after other elements like the grid, but potentially before UI
        for agent in self.agents:
            agent.draw(screen, grid)