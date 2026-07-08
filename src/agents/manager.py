import pygame
import uuid
import logging
from typing import List, TYPE_CHECKING, Optional
from .agent import Agent
from ..resources.resource_types import ResourceType
from ..rendering import agent_renderer
from ..tasks.task_types import TaskStatus

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
        self.logger = logging.getLogger(__name__)
        self.next_agent_number = 1

    def add_agent(self, agent: Agent):
        """Adds an existing Agent instance to the manager."""
        self.agents.append(agent)

    def create_agent(self,
                     position: pygame.math.Vector2,
                     speed: float,
                     inventory_capacity: int = 5,
                     resource_priorities: List[ResourceType] = None,
                     faction_id: Optional[int] = None,
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
        agent_name = f"Agent-{self.next_agent_number}"
        self.next_agent_number += 1

        if resource_priorities is None:
            # Provide a default if not specified, e.g. based on global config or common resources
            resource_priorities = [ResourceType.BERRY, ResourceType.WHEAT]

        # Validate agent spawn position
        if not self.grid.is_walkable(int(position.x), int(position.y)):
            self.logger.warning(f"Attempting to spawn agent {agent_name} ({agent_id}) at non-walkable position {position}. This may lead to issues.")
            # Optionally, add logic here to find a nearby walkable tile or prevent spawning.

        new_agent = Agent(
            agent_id=agent_id,
            agent_name=agent_name,
            position=position,
            speed=speed,
            grid=self.grid,
            task_manager=self.task_manager_ref,
            inventory_capacity=inventory_capacity,
            resource_priorities=resource_priorities
        )
        new_agent.owner_faction_id = faction_id
        self.add_agent(new_agent)
        self.logger.info(f"Created agent {agent_name} ({agent_id}) at {position} faction={faction_id}")
        return new_agent

    def update_agents(self, dt: float, resource_manager, metrics=None) -> None:
        """Updates all agents; removes those that have starved to death."""
        dead = []
        for agent in self.agents:
            agent.update(dt, resource_manager)
            if agent.needs.is_dead:
                dead.append(agent)
        for agent in dead:
            self._remove_dead_agent(agent, resource_manager, metrics)

    def _remove_dead_agent(self, agent, resource_manager, metrics=None) -> None:
        self.logger.warning(f"Agent {agent.name} ({agent.id}) starved to death.")
        if metrics is not None:
            metrics.record("agent_death", agent_name=agent.name, faction_id=agent.owner_faction_id)

        # Release current task claims and re-post to job board (use agent's own TM)
        agent_tm = getattr(agent, 'task_manager_ref', self.task_manager_ref)
        current_task = agent_tm.assigned_tasks.get(agent.id)
        if current_task is not None:
            current_task.cleanup(agent, resource_manager, success=False)
            agent_tm.report_task_outcome(current_task, TaskStatus.FAILED, agent)

        # Drop carried inventory (log and discard; no item-on-ground yet)
        qty = agent.current_inventory.get('quantity', 0)
        if qty:
            self.logger.info(f"Agent {agent.name} dropped {qty}x {agent.current_inventory.get('resource_type')} on death (discarded).")
        agent.current_inventory['quantity'] = 0
        agent.current_inventory['resource_type'] = None

        # Clear grid occupancy at agent's current position
        gx, gy = int(round(agent.position.x)), int(round(agent.position.y))
        self.grid.update_occupancy(agent, gx, gy, 1, 1, is_placing=False)

        self.agents.remove(agent)

    def render_agents(self, screen: pygame.Surface, grid, selected_agent: Optional[Agent] = None):
        for agent in self.agents:
            agent_renderer.draw_agent(agent, screen, grid, selected_agent)

    def get_agent_at_position(self, grid_pos: pygame.math.Vector2) -> Optional[Agent]:
        """
        Finds and returns an agent at the given grid coordinates.
        Since agents are 1x1, it checks if the agent's integer position matches.
        """
        target_gx, target_gy = int(grid_pos.x), int(grid_pos.y)
        for agent in self.agents:
            agent_gx, agent_gy = int(agent.position.x), int(agent.position.y)
            if agent_gx == target_gx and agent_gy == target_gy:
                self.logger.info(f"Found agent {agent.name} at position {grid_pos}")
                return agent
        return None