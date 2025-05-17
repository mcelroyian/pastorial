import pygame
import uuid # For agent ID
from enum import Enum, auto
import random
from typing import List, Dict, Optional, TYPE_CHECKING
import math # For math.inf

from ..resources.resource_types import ResourceType
from ..core import config # Agent still uses config for timers, capacity if not overridden by task

# Forward references for type hinting
if TYPE_CHECKING:
    from ..tasks.task import Task
    from ..tasks.task_manager import TaskManager
    from ..resources.manager import ResourceManager # For passing to tasks
    # from ..core.grid import Grid # Assuming Grid class type hint


class AgentState(Enum):
    """Defines the possible states an agent can be in. Tasks will set these."""
    IDLE = auto()
    MOVING_RANDOMLY = auto()
    MOVING_TO_RESOURCE = auto()
    GATHERING_RESOURCE = auto()
    MOVING_TO_STORAGE = auto()
    DELIVERING_RESOURCE = auto()
    MOVING_TO_PROCESSOR = auto()
    DELIVERING_TO_PROCESSOR = auto()
    COLLECTING_FROM_PROCESSOR = auto()

class Agent:
    """Represents an autonomous agent in the simulation, executing tasks."""

    def __init__(self,
                 agent_id: uuid.UUID, 
                 position: pygame.math.Vector2,
                 speed: float,
                 grid, # 'Grid' type hint
                 task_manager: 'TaskManager', 
                 inventory_capacity: int,
                 resource_priorities: Optional[List[ResourceType]] = None):
        """
        Initializes an Agent.
        Args:
            agent_id (uuid.UUID): Unique identifier for this agent.
            position (pygame.math.Vector2): The starting grid coordinates of the agent.
            speed (float): The movement speed of the agent (grid units per second).
            grid (Grid): The simulation grid object.
            task_manager (TaskManager): Reference to the global task manager.
            inventory_capacity (int): Maximum number of resource units the agent can carry.
            resource_priorities (Optional[List[ResourceType]]): Ordered list of resource types the agent prefers.
                                                               Might be used by TaskManager.
        """
        self.id: uuid.UUID = agent_id
        self.position = position
        self.speed = speed
        self.grid = grid # type: ignore
        self.task_manager_ref: 'TaskManager' = task_manager
        self.config = config 

        self.state = AgentState.IDLE
        self.target_position: Optional[pygame.math.Vector2] = None # Set by tasks
        self.color = (255, 255, 0)

        self.state_colors = {
            AgentState.IDLE: (255, 255, 0),
            AgentState.MOVING_RANDOMLY: (255, 165, 0),
            AgentState.MOVING_TO_RESOURCE: (0, 200, 50),
            AgentState.GATHERING_RESOURCE: (50, 150, 255),
            AgentState.MOVING_TO_STORAGE: (0, 200, 200),
            AgentState.DELIVERING_RESOURCE: (100, 100, 255),
            AgentState.MOVING_TO_PROCESSOR: (255, 140, 0),
            AgentState.DELIVERING_TO_PROCESSOR: (138, 43, 226),
            AgentState.COLLECTING_FROM_PROCESSOR: (0, 128, 128),
        }
        self.target_tolerance = 0.1

        self.inventory_capacity: int = inventory_capacity
        self.current_inventory: Dict[str, Optional[ResourceType] | int] = {
            'resource_type': None,
            'quantity': 0
        }
        
        self.current_task: Optional['Task'] = None
        self.resource_priorities: Optional[List[ResourceType]] = resource_priorities

        self.gathering_timer: float = 0.0
        self.delivery_timer: float = 0.0

    def set_target(self, target_position: pygame.math.Vector2):
        """Sets the agent's target position. Primarily called by tasks."""
        self.target_position = target_position
        # The agent's state (e.g., MOVING_TO_RESOURCE) should be set by the task itself.
        # print(f"DEBUG: Agent {self.id} set_target: NewTargetGridPos={self.target_position}")

    def _move_towards_target(self, dt: float) -> bool:
        """
        Moves the agent towards its target position.
        Args: dt (float): Delta time.
        Returns: bool: True if the target was reached this frame, False otherwise.
        """
        if self.target_position is None:
            return False

        direction = self.target_position - self.position
        distance = direction.length()

        if distance < self.target_tolerance:
            self.position = pygame.math.Vector2(self.target_position) 
            self.target_position = None 
            return True
        elif distance > 0:
            normalized_direction = direction.normalize()
            movement = normalized_direction * self.speed * dt
            if movement.length() >= distance:
                self.position = pygame.math.Vector2(self.target_position)
                self.target_position = None
                return True
            else:
                self.position += movement
        return False

    def _move_randomly(self, dt: float):
        """Moves the agent randomly within the grid bounds."""
        if self.target_position is None: 
            if self.grid.width_in_cells > 0 and self.grid.height_in_cells > 0: # type: ignore
                self.target_position = pygame.math.Vector2(
                    random.uniform(0, self.grid.width_in_cells - 1), # type: ignore
                    random.uniform(0, self.grid.height_in_cells - 1) # type: ignore
                )
                self.target_position.x = max(0, min(self.target_position.x, self.grid.width_in_cells - 1)) # type: ignore
                self.target_position.y = max(0, min(self.target_position.y, self.grid.height_in_cells - 1)) # type: ignore
            else: 
                self.state = AgentState.IDLE 
                return

        if self._move_towards_target(dt): 
            self.state = AgentState.IDLE

    def update(self, dt: float, resource_manager: 'ResourceManager'):
        """Updates the agent's state and behavior based on its current task or idleness."""
        from ..tasks.task_types import TaskStatus 

        if self.current_task:
            new_task_status = self.current_task.execute_step(self, dt, resource_manager)
            
            if new_task_status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                self.current_task.cleanup(self, resource_manager, success=(new_task_status == TaskStatus.COMPLETED))
                self.task_manager_ref.report_task_outcome(self.current_task, new_task_status, self)
                
                self.current_task = None
                self.state = AgentState.IDLE 
                self.target_position = None   

                if new_task_status == TaskStatus.COMPLETED and self.current_inventory['quantity'] == 0:
                    self.current_inventory['resource_type'] = None
        
        elif self.state == AgentState.IDLE: 
            assigned_task = self.task_manager_ref.request_task_for_agent(self)
            if assigned_task:
                self.current_task = assigned_task
                if self.current_task: # mypy check
                    self.current_task.agent_id = self.id 
                
                    if self.current_task.prepare(self, resource_manager):
                        pass 
                    else:
                        self.current_task.cleanup(self, resource_manager, success=False) 
                        self.task_manager_ref.report_task_outcome(self.current_task, TaskStatus.FAILED, self)
                        self.current_task = None
                        self.state = AgentState.IDLE 
            else:
                self.state = AgentState.MOVING_RANDOMLY 
        
        if self.current_task is None: 
            if self.state == AgentState.MOVING_RANDOMLY:
                self._move_randomly(dt)
            elif self.state != AgentState.IDLE: 
                self.state = AgentState.IDLE
                self.target_position = None

    def draw(self, screen: pygame.Surface, grid): 
        """Draws the agent on the screen."""
        screen_pos = self.grid.grid_to_screen(self.position) # type: ignore
        agent_radius = self.grid.cell_width // 2 # type: ignore

        current_agent_color = self.state_colors.get(self.state, self.color)
        pygame.draw.circle(screen, current_agent_color, screen_pos, agent_radius)

        if self.current_inventory['quantity'] > 0 and self.current_inventory['resource_type'] is not None:
            carried_resource_type = self.current_inventory['resource_type']
            resource_color = self.config.RESOURCE_VISUAL_COLORS.get(carried_resource_type, (128, 128, 128)) 

            icon_radius = agent_radius // 2
            icon_offset_y = -agent_radius - icon_radius // 2 
            icon_center_x = screen_pos[0]
            icon_center_y = screen_pos[1] + icon_offset_y
            
            pygame.draw.circle(screen, resource_color, (icon_center_x, icon_center_y), icon_radius)