import pygame
from enum import Enum, auto
import random
from typing import List, Dict, Optional
import math # For math.inf

# Assuming ResourceType will be in this path, created in Step 1
from ..resources.resource_types import ResourceType
# Assuming ResourceNode is defined in node.py, will be used as type hint
from ..resources.node import ResourceNode # Assuming ResourceNode has position, resource_type, current_quantity and collect_resource method
from ..resources.storage_point import StoragePoint # Make sure this is not commented out
from ..core import config # For default times and capacities


class AgentState(Enum):
    """Defines the possible states an agent can be in."""
    IDLE = auto()
    MOVING_RANDOMLY = auto()
    MOVING_TO_TARGET = auto() # Generic movement to a point
    MOVING_TO_RESOURCE = auto()
    GATHERING_RESOURCE = auto()
    CARRYING_RESOURCE = auto() # Agent has a resource, deciding/moving to storage
    MOVING_TO_STORAGE = auto()
    DELIVERING_RESOURCE = auto()

class Agent:
    """Represents an autonomous agent in the simulation."""

    def __init__(self,
                 position: pygame.math.Vector2,
                 speed: float,
                 grid, # Assuming Grid class type hint
                 resource_priorities: List[ResourceType],
                 inventory_capacity: int):
        """
        Initializes an Agent.

        Args:
            position (pygame.math.Vector2): The starting grid coordinates of the agent.
            speed (float): The movement speed of the agent (grid units per second).
            grid (Grid): The simulation grid object.
            resource_priorities (List[ResourceType]): Ordered list of resource types the agent prefers.
            inventory_capacity (int): Maximum number of resource units the agent can carry.
        """
        self.position = position  # Grid coordinates
        self.speed = speed
        self.grid = grid  # Store the grid object
        self.state = AgentState.IDLE
        self.target_position: Optional[pygame.math.Vector2] = None  # Grid coordinates
        self.color = (255, 255, 0)  # Default Yellow, will be overridden by state_colors

        # State visual representation
        self.state_colors = {
            AgentState.IDLE: (255, 255, 0),  # Yellow
            AgentState.MOVING_RANDOMLY: (255, 165, 0),  # Orange
            AgentState.MOVING_TO_TARGET: (0, 255, 0),  # Green (generic target)
            AgentState.MOVING_TO_RESOURCE: (0, 200, 50),  # Light Green
            AgentState.GATHERING_RESOURCE: (50, 150, 255),  # Light Blue
            AgentState.CARRYING_RESOURCE: (200, 0, 200),  # Magenta
            AgentState.MOVING_TO_STORAGE: (0, 200, 200),  # Cyan
            AgentState.DELIVERING_RESOURCE: (100, 100, 255),  # Purple-Blue
        }
        self.target_tolerance = 0.1  # Tolerance for reaching target

        # Resource Collection Attributes
        self.resource_priorities: List[ResourceType] = resource_priorities
        self.inventory_capacity: int = inventory_capacity
        self.current_inventory: Dict[str, Optional[ResourceType] | int] = {
            'resource_type': None,
            'quantity': 0
        }
        self.gathering_timer: float = 0.0
        self.delivery_timer: float = 0.0

        # Target entities for resource operations
        self.target_resource_node: Optional[ResourceNode] = None
        self.target_storage_point: Optional[StoragePoint] = None # Ensure this is using the class, not string

    def set_target(self, target_position: pygame.math.Vector2):
        """Sets the agent's target position and changes state."""
        self.target_position = target_position
        self.state = AgentState.MOVING_TO_TARGET
        print(f"DEBUG: Agent.set_target (generic): AgentGridPos={self.position}, NewTargetGridPos={self.target_position}, State={self.state.name}")

    def _move_towards_target(self, dt: float) -> bool:
        """
        Moves the agent towards its target position.

        Args:
            dt (float): Delta time.

        Returns:
            bool: True if the target was reached this frame, False otherwise.
        """
        if self.target_position is None:
            # print(f"DEBUG: Agent._move_towards_target: No target for agent at {self.position}, state {self.state.name}") # Can be noisy
            return False

        print(f"DEBUG: Agent._move_towards_target PRE-MOVE: AgentGridPos={self.position}, TargetPos={self.target_position}, State={self.state.name}")
        direction = self.target_position - self.position
        distance = direction.length()
        print(f"DEBUG: Agent._move_towards_target CALCS: DirectionVec={direction}, Distance={distance:.2f}")

        if distance < self.target_tolerance:
            print(f"DEBUG: Agent._move_towards_target: Reached target. AgentGridPos was {self.position}, TargetPos was {self.target_position}")
            self.position = pygame.math.Vector2(self.target_position) # Snap
            self.target_position = None
            return True
        elif distance > 0:
            # Normalize a copy, not in-place, to keep original direction for logging if needed
            normalized_direction = direction.normalize()
            movement = normalized_direction * self.speed * dt
            # print(f"DEBUG: Agent._move_towards_target: Moving. Speed={self.speed}, dt={dt}, MovementVec={movement}") # Potentially noisy
            if movement.length() >= distance:
                print(f"DEBUG: Agent._move_towards_target: Reached target (overshoot check). AgentGridPos was {self.position}, TargetPos was {self.target_position}")
                self.position = pygame.math.Vector2(self.target_position) # Snap
                self.target_position = None
                return True
            else:
                self.position += movement
                # print(f"DEBUG: Agent._move_towards_target POST-MOVE: New AgentGridPos={self.position}") # Potentially noisy
        return False

    def _move_randomly(self, dt: float):
        """Moves the agent randomly within the grid bounds."""
        # Simple random movement: If idle or finished random move, pick a new random target within grid bounds
        if self.target_position is None:
            # Ensure grid has positive dimensions before attempting to find a random target
            if self.grid.width_in_cells > 0 and self.grid.height_in_cells > 0:
                self.target_position = pygame.math.Vector2(
                    random.uniform(0, self.grid.width_in_cells - 1),
                    random.uniform(0, self.grid.height_in_cells - 1)
                )
                # Ensure target is valid if grid is small (though uniform should handle this if bounds are correct)
                self.target_position.x = max(0, min(self.target_position.x, self.grid.width_in_cells - 1))
                self.target_position.y = max(0, min(self.target_position.y, self.grid.height_in_cells - 1))
                print(f"Agent at {self.position} moving randomly towards {self.target_position}") # Debug
            else:
                # Cannot move randomly in a zero-sized grid, remain idle or handle error
                self.state = AgentState.IDLE # Or some other appropriate state
                return


        # Use the move_towards_target logic to handle the actual movement
        reached_random_target = self._move_towards_target(dt)

        # If we reached the random target, clear it so a new one is picked next time
        if reached_random_target:
            self.target_position = None
            # Stay in MOVING_RANDOMLY state until explicitly changed by another action
            # or if the state machine logic for MOVING_RANDOMLY decides to pick a new target immediately.
            # For now, it will pick a new target in the next call if target_position is None.
            # self.state = AgentState.MOVING_RANDOMLY # This state is already set, or will be set by update()
            pass # The state remains MOVING_RANDOMLY


    def update(self, dt: float, resource_manager): # Add resource_manager
        """Updates the agent's state and position based on delta time."""
        # print(f"Agent at {self.position} in state {self.state.name} with inventory {self.current_inventory}") # Debug

        if self.state == AgentState.IDLE:
            # Try to find a resource to collect
            if self.current_inventory['quantity'] == 0: # Only look for resources if empty
                self.target_resource_node = self._find_best_resource_target(resource_manager)
                if self.target_resource_node:
                    self.target_position = pygame.math.Vector2(self.target_resource_node.position)
                    self.state = AgentState.MOVING_TO_RESOURCE
                    print(f"DEBUG: Agent.update (IDLE -> MOVING_TO_RESOURCE): AgentGridPos={self.position}, TargetNodePos(resource)={self.target_resource_node.position}, Setting AgentTargetPos to NodePos.")
                else:
                    # No resources to collect, maybe move randomly or stay idle
                    # For now, let's make it move randomly if no resources are found and it's idle
                    self.state = AgentState.MOVING_RANDOMLY # Fallback to random movement
                    print(f"Agent {self.position} IDLE -> MOVING_RANDOMLY (no resources found)")
            else: # Has inventory, should try to store it
                self.state = AgentState.CARRYING_RESOURCE # Transition to find storage
                print(f"Agent {self.position} IDLE (has inventory) -> CARRYING_RESOURCE")


        elif self.state == AgentState.MOVING_TO_TARGET: # Generic movement, should be less used now
            if self._move_towards_target(dt):
                self.state = AgentState.IDLE # Reached generic target

        elif self.state == AgentState.MOVING_RANDOMLY:
            self._move_randomly(dt)
            # _move_randomly keeps it in MOVING_RANDOMLY or sets to IDLE if stuck.
            # If it becomes IDLE, next tick it will try to find resources.

        elif self.state == AgentState.MOVING_TO_RESOURCE:
            if not self.target_resource_node or not self.target_position:
                print(f"Agent {self.position} MOVING_TO_RESOURCE -> IDLE (target node/pos became None)")
                self.state = AgentState.IDLE
                self.target_resource_node = None # Clear target
                return

            # Check if target resource is still valid (e.g., not depleted by another agent)
            if self.target_resource_node.current_quantity <= 0:
                print(f"Agent {self.position} MOVING_TO_RESOURCE -> IDLE (target node {self.target_resource_node.position} depleted)")
                self.state = AgentState.IDLE
                self.target_resource_node = None
                self.target_position = None
                return

            if self._move_towards_target(dt):
                print(f"DEBUG: Agent.update (MOVING_TO_RESOURCE -> GATHERING_RESOURCE): AgentGridPos={self.position}, Reached TargetNodePos={self.target_resource_node.position if self.target_resource_node else 'None'}")
                self.state = AgentState.GATHERING_RESOURCE
                self.gathering_timer = config.DEFAULT_GATHERING_TIME
                self.target_position = None # Clear movement target

        elif self.state == AgentState.GATHERING_RESOURCE:
            if not self.target_resource_node:
                print(f"Agent {self.position} GATHERING_RESOURCE -> IDLE (target node became None)")
                self.state = AgentState.IDLE
                return

            if self.target_resource_node.current_quantity <= 0:
                print(f"Agent {self.position} GATHERING_RESOURCE -> CARRYING_RESOURCE (node {self.target_resource_node.position} depleted during gathering)")
                self.state = AgentState.CARRYING_RESOURCE # Move on, even if got nothing this time
                self.target_resource_node = None
                self.gathering_timer = 0
                return

            self.gathering_timer -= dt
            if self.gathering_timer <= 0:
                amount_to_gather = self.inventory_capacity - self.current_inventory['quantity']
                if amount_to_gather > 0:
                    # Ensure resource_type is known for the node
                    node_resource_type = getattr(self.target_resource_node, 'resource_type', None)
                    if node_resource_type is None:
                        print(f"Error: Target resource node {self.target_resource_node.position} has no resource_type attribute.")
                        self.state = AgentState.IDLE
                        self.target_resource_node = None
                        return

                    # If inventory is empty or matches node type
                    if self.current_inventory['resource_type'] is None or self.current_inventory['resource_type'] == node_resource_type:
                        gathered_amount = self.target_resource_node.collect_resource(amount_to_gather)
                        if gathered_amount > 0:
                            self.current_inventory['resource_type'] = node_resource_type
                            self.current_inventory['quantity'] += gathered_amount
                            print(f"Agent {self.position} gathered {gathered_amount} of {node_resource_type.name} from {self.target_resource_node.position}. Inv: {self.current_inventory['quantity']}")
                        else:
                            print(f"Agent {self.position} tried to gather from {self.target_resource_node.position} but got 0.")
                    else:
                        # Inventory has a different resource type, cannot gather this one.
                        # This case should ideally be prevented by CARRYING_RESOURCE logic or by emptying inventory first.
                        print(f"Agent {self.position} GATHERING_RESOURCE: Inventory type mismatch. Inv: {self.current_inventory['resource_type']}, Node: {node_resource_type}")

                print(f"Agent {self.position} GATHERING_RESOURCE -> CARRYING_RESOURCE (timer ended)")
                self.state = AgentState.CARRYING_RESOURCE
                self.target_resource_node = None # Done with this node

        elif self.state == AgentState.CARRYING_RESOURCE:
            if self.current_inventory['quantity'] == 0:
                print(f"Agent {self.position} CARRYING_RESOURCE -> IDLE (inventory empty)")
                self.current_inventory['resource_type'] = None # Ensure type is cleared
                self.state = AgentState.IDLE
                return

            self.target_storage_point = self._find_best_storage_target(resource_manager)
            if self.target_storage_point:
                self.target_position = pygame.math.Vector2(self.target_storage_point.position)
                self.state = AgentState.MOVING_TO_STORAGE
                print(f"DEBUG: Agent.update (CARRYING_RESOURCE -> MOVING_TO_STORAGE): AgentGridPos={self.position}, TargetStoragePos={self.target_storage_point.position}, Setting AgentTargetPos to StoragePos.")
            else:
                # No suitable storage, what to do? For now, go IDLE.
                # Could implement a waiting behavior or drop resource later.
                print(f"Agent {self.position} CARRYING_RESOURCE -> IDLE (no storage found for {self.current_inventory['quantity']} of {self.current_inventory['resource_type'].name if self.current_inventory['resource_type'] else 'None'})")
                self.state = AgentState.IDLE # Or MOVING_RANDOMLY to not get stuck

        elif self.state == AgentState.MOVING_TO_STORAGE:
            if not self.target_storage_point or not self.target_position:
                print(f"Agent {self.position} MOVING_TO_STORAGE -> CARRYING_RESOURCE (target storage/pos became None)")
                self.state = AgentState.CARRYING_RESOURCE # Re-evaluate storage
                self.target_storage_point = None
                return

            # Check if target storage is still valid (e.g., not filled by another agent)
            # This check might be complex if we need to predict space; StoragePoint.can_accept is key
            if not self.target_storage_point.can_accept(self.current_inventory['resource_type'], self.current_inventory['quantity']):
                print(f"Agent {self.position} MOVING_TO_STORAGE -> CARRYING_RESOURCE (target storage {self.target_storage_point.position} can no longer accept)")
                self.state = AgentState.CARRYING_RESOURCE
                self.target_storage_point = None
                self.target_position = None
                return

            if self._move_towards_target(dt):
                print(f"DEBUG: Agent.update (MOVING_TO_STORAGE -> DELIVERING_RESOURCE): AgentGridPos={self.position}, Reached TargetStoragePos={self.target_storage_point.position if self.target_storage_point else 'None'}")
                self.state = AgentState.DELIVERING_RESOURCE
                self.delivery_timer = config.DEFAULT_DELIVERY_TIME
                self.target_position = None # Clear movement target

        elif self.state == AgentState.DELIVERING_RESOURCE:
            if not self.target_storage_point:
                print(f"Agent {self.position} DELIVERING_RESOURCE -> CARRYING_RESOURCE (target storage became None)")
                self.state = AgentState.CARRYING_RESOURCE
                return

            self.delivery_timer -= dt
            if self.delivery_timer <= 0:
                resource_type_to_deliver = self.current_inventory['resource_type']
                quantity_to_deliver = self.current_inventory['quantity']

                if resource_type_to_deliver and quantity_to_deliver > 0:
                    delivered_amount = self.target_storage_point.add_resource(
                        resource_type_to_deliver,
                        quantity_to_deliver
                    )
                    if delivered_amount > 0:
                        self.current_inventory['quantity'] -= delivered_amount
                        print(f"Agent {self.position} delivered {delivered_amount} of {resource_type_to_deliver.name} to {self.target_storage_point.position}. Inv left: {self.current_inventory['quantity']}")
                    else:
                        # Delivery failed, storage might be full or not accepting this type anymore
                        print(f"Agent {self.position} failed to deliver {quantity_to_deliver} of {resource_type_to_deliver.name} to {self.target_storage_point.position}.")
                
                self.target_storage_point = None # Done with this storage point for now

                if self.current_inventory['quantity'] <= 0:
                    self.current_inventory['resource_type'] = None
                    self.current_inventory['quantity'] = 0
                    print(f"Agent {self.position} DELIVERING_RESOURCE -> IDLE (inventory empty)")
                    self.state = AgentState.IDLE
                else:
                    # Still has items (e.g. partial delivery or different items if multi-carry was allowed)
                    print(f"Agent {self.position} DELIVERING_RESOURCE -> CARRYING_RESOURCE (still has {self.current_inventory['quantity']} items)")
                    self.state = AgentState.CARRYING_RESOURCE

    def _find_best_resource_target(self, resource_manager) -> Optional[ResourceNode]:
        """
        Finds the best (nearest, prioritized) resource node for the agent to target.
        Assumes resource_manager has get_nodes_by_type(ResourceType) -> List[ResourceNode].
        Assumes ResourceNode has .current_quantity and .resource_type attributes.
        """
        best_node: Optional[ResourceNode] = None
        min_dist_sq = math.inf # Using squared distance to avoid sqrt

        for res_type in self.resource_priorities:
            try:
                # This method needs to be implemented in ResourceManager
                candidate_nodes = resource_manager.get_nodes_by_type(res_type)
            except AttributeError:
                print(f"Warning: resource_manager missing 'get_nodes_by_type'. Agent: {self.position}")
                return None # Or handle differently

            for node in candidate_nodes:
                # Ensure node has necessary attributes and resources
                if (hasattr(node, 'current_quantity') and node.current_quantity > 0 and
                        hasattr(node, 'resource_type') and node.resource_type == res_type and
                        hasattr(node, 'position')):
                    
                    # Using Euclidean distance squared for now.
                    # Replace with pathfinding if available:
                    # dist_sq = self.grid.calculate_path_distance_sq(self.position, node.position)
                    dist_sq = (node.position - self.position).length_squared()
                    
                    if dist_sq < min_dist_sq:
                        min_dist_sq = dist_sq
                        best_node = node
            
            if best_node: # Found a node for the current highest priority, no need to check lower priorities
                break
        
        if best_node:
            print(f"DEBUG: Agent._find_best_resource_target: AgentGridPos={self.position} found best resource: {best_node.resource_type.name} at NodePos={best_node.position} (dist_sq: {min_dist_sq:.2f})")
        else:
            print(f"Agent at {self.position} found no suitable resource target.")
        return best_node

    def _find_best_storage_target(self, resource_manager) -> Optional[StoragePoint]:
        """
        Finds the best (nearest, suitable) storage point for the agent's current inventory.
        Assumes resource_manager has a 'storage_points' list.
        """
        if not self.current_inventory['resource_type'] or self.current_inventory['quantity'] == 0:
            print(f"Agent at {self.position} has nothing to store.")
            return None

        best_storage: Optional[StoragePoint] = None
        min_dist_sq = math.inf
        
        resource_to_store: ResourceType = self.current_inventory['resource_type']
        quantity_to_store: int = self.current_inventory['quantity']

        try:
            candidate_storages = resource_manager.storage_points
        except AttributeError:
            print(f"Warning: resource_manager missing 'storage_points'. Agent: {self.position}")
            return None

        if not candidate_storages:
            print(f"Agent at {self.position}: No storage points available in resource_manager.")
            return None

        for storage_point in candidate_storages:
            if hasattr(storage_point, 'can_accept') and storage_point.can_accept(resource_to_store, quantity_to_store) and \
               hasattr(storage_point, 'position'):
                # dist_sq = self.grid.calculate_path_distance_sq(self.position, storage_point.position)
                dist_sq = (storage_point.position - self.position).length_squared()
                if dist_sq < min_dist_sq:
                    min_dist_sq = dist_sq
                    best_storage = storage_point
        
        if best_storage:
            print(f"DEBUG: Agent._find_best_storage_target: AgentGridPos={self.position} found best storage at StoragePos={best_storage.position} for {resource_to_store.name} (dist_sq: {min_dist_sq:.2f})")
        else:
            print(f"Agent at {self.position} found no suitable storage for {quantity_to_store} of {resource_to_store.name}.")
        return best_storage

    def draw(self, screen: pygame.Surface, grid): # grid parameter is already here
        """Draws the agent on the screen."""
        screen_pos = self.grid.grid_to_screen(self.position)
        agent_radius = self.grid.cell_width // 2 # Main agent radius

        # Draw main agent body
        current_agent_color = self.state_colors.get(self.state, self.color)
        pygame.draw.circle(screen, current_agent_color, screen_pos, agent_radius)

        # Visual feedback for carrying resources
        if self.current_inventory['quantity'] > 0 and self.current_inventory['resource_type'] is not None:
            carried_resource_type = self.current_inventory['resource_type']
            # Get color from config, provide a default if not found
            resource_color = config.RESOURCE_VISUAL_COLORS.get(carried_resource_type, (128, 128, 128)) # Default to grey

            # Draw a smaller circle on top/offset to indicate carried resource
            icon_radius = agent_radius // 2
            icon_offset_y = -agent_radius - icon_radius // 2 # Position above the agent
            icon_center_x = screen_pos[0]
            icon_center_y = screen_pos[1] + icon_offset_y
            
            # Simple circle icon for now
            pygame.draw.circle(screen, resource_color, (icon_center_x, icon_center_y), icon_radius)
            
            # Optional: Draw quantity text if needed, though might be too small
            # font = pygame.font.SysFont(None, 18) # Example font
            # quantity_text = font.render(str(self.current_inventory['quantity']), True, (0,0,0))
            # text_rect = quantity_text.get_rect(center=(icon_center_x, icon_center_y))
            # screen.blit(quantity_text, text_rect)