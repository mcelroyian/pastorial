import pygame
import uuid # For generating agent IDs
import logging # Added
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
        self.logger = logging.getLogger(__name__) # Added

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

        # Validate agent spawn position
        if not self.grid.is_walkable(int(position.x), int(position.y)):
            self.logger.warning(f"Attempting to spawn agent {agent_id} at non-walkable position {position}. This may lead to issues.")
            # Optionally, add logic here to find a nearby walkable tile or prevent spawning.

        new_agent = Agent(
            agent_id=agent_id,
            position=position,
            speed=speed,
            grid=self.grid,
            task_manager=self.task_manager_ref, # Pass the TaskManager reference
            inventory_capacity=inventory_capacity,
            resource_priorities=resource_priorities
        )
        self.add_agent(new_agent)
        self.logger.info(f"Created agent {agent_id} at {position}") # Changed
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