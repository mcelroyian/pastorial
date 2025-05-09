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
from ..resources.processing import ProcessingStation # For interacting with mills, bakeries, etc.
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
    MOVING_TO_PROCESSOR = auto()       # Moving to a processing station (e.g., Mill)
    DELIVERING_TO_PROCESSOR = auto() # Delivering input to a processing station
    COLLECTING_FROM_PROCESSOR = auto() # Collecting output from a processing station

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
            AgentState.MOVING_TO_PROCESSOR: (255, 140, 0), # DarkOrange
            AgentState.DELIVERING_TO_PROCESSOR: (138, 43, 226), # BlueViolet
            AgentState.COLLECTING_FROM_PROCESSOR: (0, 128, 128), # Teal
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
        self.target_processing_station: Optional[ProcessingStation] = None # For mills, bakeries, etc.

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
            print(f"DEBUG: Agent._move_randomly: Reached random target at {self.position}. Transitioning to IDLE.")
            self.state = AgentState.IDLE # Transition to IDLE to re-evaluate


    def update(self, dt: float, resource_manager): # Add resource_manager
        """Updates the agent's state and position based on delta time."""
        # print(f"Agent at {self.position} in state {self.state.name} with inventory {self.current_inventory}") # Debug

        if self.state == AgentState.IDLE:
            # Decision making:
            # 1. If carrying resources, decide where to take them.
            # 2. If inventory empty, decide what to collect (raw resource or processed good).
            if self.current_inventory['quantity'] > 0:
                self.state = AgentState.CARRYING_RESOURCE # Will decide target in CARRYING_RESOURCE
                print(f"Agent {self.position} IDLE (has inventory) -> CARRYING_RESOURCE")
            else: # Inventory is empty
                # Try to find a raw resource to collect first, based on priorities
                self.target_resource_node = self._find_best_resource_target(resource_manager)
                if self.target_resource_node:
                    self.target_position = pygame.math.Vector2(self.target_resource_node.position)
                    self.state = AgentState.MOVING_TO_RESOURCE
                    print(f"DEBUG: Agent.update (IDLE -> MOVING_TO_RESOURCE): AgentGridPos={self.position}, TargetNodePos(resource)={self.target_resource_node.position}")
                else:
                    # No raw resources found or desired. Check if we should collect processed goods.
                    # For Slice 3.1, this means checking for FLOUR_POWDER from a Mill.
                    # This logic can be expanded for other processed goods later.
                    # Let's assume for now if WHEAT is a priority, FLOUR_POWDER might also be implicitly.
                    # A more explicit task system would be better in the long run.
                    self.target_processing_station = self._find_best_station_with_output(resource_manager, ResourceType.FLOUR_POWDER)
                    if self.target_processing_station:
                        self.target_position = pygame.math.Vector2(self.target_processing_station.position)
                        self.state = AgentState.MOVING_TO_PROCESSOR # Moving to collect output
                        print(f"DEBUG: Agent.update (IDLE -> MOVING_TO_PROCESSOR to collect FLOUR_POWDER): AgentGridPos={self.position}, TargetStationPos={self.target_processing_station.position}")
                    else:
                        # No raw resources, no flour to collect, move randomly.
                        self.state = AgentState.MOVING_RANDOMLY
                        print(f"Agent {self.position} IDLE -> MOVING_RANDOMLY (no resources or flour to collect)")

        elif self.state == AgentState.MOVING_TO_TARGET: # Generic movement
            if self._move_towards_target(dt):
                self.state = AgentState.IDLE

        elif self.state == AgentState.MOVING_RANDOMLY:
            self._move_randomly(dt) # Handles its own transition to IDLE

        elif self.state == AgentState.MOVING_TO_RESOURCE:
            if not self.target_resource_node or not self.target_position:
                self.state = AgentState.IDLE; self.target_resource_node = None; return
            if self.target_resource_node.current_quantity <= 0: # Target depleted
                self.state = AgentState.IDLE; self.target_resource_node = None; self.target_position = None; return
            if self._move_towards_target(dt):
                self.state = AgentState.GATHERING_RESOURCE
                self.gathering_timer = config.DEFAULT_GATHERING_TIME
                self.target_position = None

        elif self.state == AgentState.GATHERING_RESOURCE:
            if not self.target_resource_node:
                self.state = AgentState.IDLE; return
            if self.target_resource_node.current_quantity <= 0: # Depleted during gathering
                self.state = AgentState.CARRYING_RESOURCE; self.target_resource_node = None; self.gathering_timer = 0; return
            
            self.gathering_timer -= dt
            if self.gathering_timer <= 0:
                amount_to_gather = self.inventory_capacity - self.current_inventory['quantity']
                if amount_to_gather > 0:
                    node_resource_type = getattr(self.target_resource_node, 'resource_type', None)
                    if node_resource_type and (self.current_inventory['resource_type'] is None or self.current_inventory['resource_type'] == node_resource_type):
                        gathered_amount = self.target_resource_node.collect_resource(amount_to_gather)
                        if gathered_amount > 0:
                            self.current_inventory['resource_type'] = node_resource_type
                            self.current_inventory['quantity'] += gathered_amount
                            print(f"Agent {self.position} gathered {gathered_amount} of {node_resource_type.name}")
                self.state = AgentState.CARRYING_RESOURCE
                self.target_resource_node = None

        elif self.state == AgentState.CARRYING_RESOURCE:
            # This state now decides where to go with the carried resource.
            if self.current_inventory['quantity'] == 0:
                self.state = AgentState.IDLE; self.current_inventory['resource_type'] = None; return

            carried_type = self.current_inventory['resource_type']
            if carried_type == ResourceType.WHEAT:
                # Try to find a Mill (ProcessingStation that accepts WHEAT)
                self.target_processing_station = self._find_best_processing_station_for_input(resource_manager, ResourceType.WHEAT)
                if self.target_processing_station:
                    self.target_position = pygame.math.Vector2(self.target_processing_station.position)
                    self.state = AgentState.MOVING_TO_PROCESSOR # Moving to deliver input
                    print(f"DEBUG: Agent.update (CARRYING WHEAT -> MOVING_TO_PROCESSOR): TargetStationPos={self.target_processing_station.position}")
                else:
                    # No mill found for wheat, maybe store it if general storage accepts wheat? Or move randomly.
                    # For now, let's try finding a generic storage point if no processor.
                    self.target_storage_point = self._find_best_storage_target(resource_manager)
                    if self.target_storage_point:
                        self.target_position = pygame.math.Vector2(self.target_storage_point.position)
                        self.state = AgentState.MOVING_TO_STORAGE
                        print(f"DEBUG: Agent.update (CARRYING WHEAT, no mill -> MOVING_TO_STORAGE): TargetStoragePos={self.target_storage_point.position}")
                    else:
                        self.state = AgentState.MOVING_RANDOMLY
                        print(f"Agent {self.position} CARRYING WHEAT -> MOVING_RANDOMLY (no mill or storage)")
            elif carried_type == ResourceType.FLOUR_POWDER or carried_type == ResourceType.BERRY: # Other storable goods
                self.target_storage_point = self._find_best_storage_target(resource_manager)
                if self.target_storage_point:
                    self.target_position = pygame.math.Vector2(self.target_storage_point.position)
                    self.state = AgentState.MOVING_TO_STORAGE
                    print(f"DEBUG: Agent.update (CARRYING {carried_type.name} -> MOVING_TO_STORAGE): TargetStoragePos={self.target_storage_point.position}")
                else:
                    self.state = AgentState.MOVING_RANDOMLY
                    print(f"Agent {self.position} CARRYING {carried_type.name} -> MOVING_RANDOMLY (no storage)")
            else: # Unknown carried resource type
                self.state = AgentState.MOVING_RANDOMLY
                print(f"Agent {self.position} CARRYING UNKNOWN -> MOVING_RANDOMLY")


        elif self.state == AgentState.MOVING_TO_STORAGE:
            if not self.target_storage_point or not self.target_position:
                self.state = AgentState.CARRYING_RESOURCE; self.target_storage_point = None; return
            # Check if target storage is still valid
            if not self.target_storage_point.can_accept(self.current_inventory['resource_type'], self.current_inventory['quantity']):
                self.state = AgentState.CARRYING_RESOURCE; self.target_storage_point = None; self.target_position = None; return
            if self._move_towards_target(dt):
                self.state = AgentState.DELIVERING_RESOURCE
                self.delivery_timer = config.DEFAULT_DELIVERY_TIME
                self.target_position = None

        elif self.state == AgentState.DELIVERING_RESOURCE: # Delivering to a StoragePoint
            if not self.target_storage_point:
                self.state = AgentState.CARRYING_RESOURCE; return
            self.delivery_timer -= dt
            if self.delivery_timer <= 0:
                res_type = self.current_inventory['resource_type']
                qty = self.current_inventory['quantity']
                if res_type and qty > 0:
                    delivered = self.target_storage_point.add_resource(res_type, qty)
                    if delivered > 0: self.current_inventory['quantity'] -= delivered
                self.target_storage_point = None
                if self.current_inventory['quantity'] <= 0:
                    self.state = AgentState.IDLE; self.current_inventory['resource_type'] = None; self.current_inventory['quantity'] = 0
                else:
                    self.state = AgentState.CARRYING_RESOURCE # Still has items

        # New states for processing stations
        elif self.state == AgentState.MOVING_TO_PROCESSOR:
            if not self.target_processing_station or not self.target_position:
                self.state = AgentState.IDLE; self.target_processing_station = None; return

            # If moving to deliver WHEAT, check if station can still accept it
            if self.current_inventory['resource_type'] == ResourceType.WHEAT and \
               not self.target_processing_station.can_accept_input(ResourceType.WHEAT, self.current_inventory['quantity']):
                print(f"Agent {self.position} MOVING_TO_PROCESSOR (deliver) -> IDLE (target {self.target_processing_station.position} cannot accept WHEAT)")
                self.state = AgentState.IDLE; self.target_processing_station = None; self.target_position = None; return

            # If moving to collect FLOUR_POWDER, check if station still has it
            if self.current_inventory['quantity'] == 0 and \
               self.target_processing_station.produced_output_type == ResourceType.FLOUR_POWDER and \
               not self.target_processing_station.has_output():
                print(f"Agent {self.position} MOVING_TO_PROCESSOR (collect) -> IDLE (target {self.target_processing_station.position} has no FLOUR_POWDER)")
                self.state = AgentState.IDLE; self.target_processing_station = None; self.target_position = None; return

            if self._move_towards_target(dt):
                if self.current_inventory['resource_type'] == ResourceType.WHEAT: # Was going to deliver
                    self.state = AgentState.DELIVERING_TO_PROCESSOR
                    self.delivery_timer = config.DEFAULT_DELIVERY_TIME # Use same timer as generic delivery
                elif self.current_inventory['quantity'] == 0: # Was going to collect
                    self.state = AgentState.COLLECTING_FROM_PROCESSOR
                    self.gathering_timer = config.DEFAULT_GATHERING_TIME # Use same timer
                else: # Should not happen if logic is correct
                    self.state = AgentState.IDLE
                self.target_position = None

        elif self.state == AgentState.DELIVERING_TO_PROCESSOR:
            if not self.target_processing_station:
                self.state = AgentState.CARRYING_RESOURCE; return # Re-evaluate if target lost
            
            self.delivery_timer -= dt
            if self.delivery_timer <= 0:
                res_type = self.current_inventory['resource_type']
                qty = self.current_inventory['quantity']
                if res_type == ResourceType.WHEAT and qty > 0:
                    # Attempt to deliver all wheat in inventory
                    if self.target_processing_station.receive(res_type, qty):
                        print(f"Agent {self.position} delivered {qty} of {res_type.name} to {self.target_processing_station.position}.")
                        self.current_inventory['quantity'] = 0 # Successfully delivered all
                    else:
                        # Failed to deliver, station might be full or not accepting.
                        # Agent keeps the wheat. CARRYING_RESOURCE will try to find another station or storage.
                        print(f"Agent {self.position} FAILED to deliver {qty} of {res_type.name} to {self.target_processing_station.position}.")
                
                self.target_processing_station = None # Done with this station for this delivery attempt
                if self.current_inventory['quantity'] <= 0:
                    self.state = AgentState.IDLE; self.current_inventory['resource_type'] = None
                else:
                    self.state = AgentState.CARRYING_RESOURCE # Still has wheat, try again

        elif self.state == AgentState.COLLECTING_FROM_PROCESSOR:
            if not self.target_processing_station:
                self.state = AgentState.IDLE; return

            if not self.target_processing_station.has_output() or \
               self.target_processing_station.produced_output_type != ResourceType.FLOUR_POWDER:
                # Output gone or wrong type
                self.state = AgentState.IDLE; self.target_processing_station = None; return

            self.gathering_timer -= dt
            if self.gathering_timer <= 0:
                amount_to_collect = self.inventory_capacity - self.current_inventory['quantity']
                if amount_to_collect > 0:
                    # Assuming current inventory is empty or matches FLOUR_POWDER
                    if self.current_inventory['resource_type'] is None or self.current_inventory['resource_type'] == ResourceType.FLOUR_POWDER:
                        collected_amount = self.target_processing_station.dispense(amount_to_collect)
                        if collected_amount > 0:
                            self.current_inventory['resource_type'] = ResourceType.FLOUR_POWDER
                            self.current_inventory['quantity'] += collected_amount
                            print(f"Agent {self.position} collected {collected_amount} of FLOUR_POWDER from {self.target_processing_station.position}.")
                
                self.state = AgentState.CARRYING_RESOURCE # Now carrying flour (or tried to)
                self.target_processing_station = None

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
                print(f"DEBUG: Agent._find_best_resource_target: Checking node at {getattr(node, 'position', 'N/A')} for type {res_type.name if hasattr(res_type, 'name') else 'N/A'}. Quantity: {getattr(node, 'current_quantity', 'N/A')}, Node Type: {getattr(node, 'resource_type', 'N/A').name if hasattr(node, 'resource_type') else 'N/A'}")
                # Ensure node has necessary attributes and resources
                # Agent should only target if there's at least 1 collectable unit
                if (hasattr(node, 'current_quantity') and int(node.current_quantity) >= 1 and
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

    def _find_best_processing_station_for_input(self, resource_manager, input_resource_type: ResourceType) -> Optional[ProcessingStation]:
        """
        Finds the best (nearest) processing station that accepts the given input resource type.
        """
        try:
            # ResourceManager's method already finds the nearest one that can accept.
            station = resource_manager.get_nearest_station_accepting(self.position, input_resource_type)
            if station:
                print(f"DEBUG: Agent._find_best_processing_station_for_input: AgentGridPos={self.position} found station {station.__class__.__name__} at {station.position} for {input_resource_type.name}")
                return station
            else:
                print(f"Agent at {self.position} found no station accepting {input_resource_type.name}.")
                return None
        except AttributeError:
            print(f"Warning: resource_manager missing 'get_nearest_station_accepting'. Agent: {self.position}")
            return None
        except Exception as e:
            print(f"Error in _find_best_processing_station_for_input: {e}")
            return None

    def _find_best_station_with_output(self, resource_manager, output_resource_type: ResourceType) -> Optional[ProcessingStation]:
        """
        Finds the best (nearest) processing station that has the specified output resource type available.
        """
        best_station: Optional[ProcessingStation] = None
        min_dist_sq = math.inf

        try:
            candidate_stations = resource_manager.get_stations_with_output(output_resource_type)
        except AttributeError:
            print(f"Warning: resource_manager missing 'get_stations_with_output'. Agent: {self.position}")
            return None
        except Exception as e:
            print(f"Error in _find_best_station_with_output (get_stations_with_output): {e}")
            return None

        if not candidate_stations:
            print(f"Agent at {self.position} found no stations with output {output_resource_type.name}.")
            return None

        for station in candidate_stations:
            if hasattr(station, 'position'):
                dist_sq = (station.position - self.position).length_squared()
                if dist_sq < min_dist_sq:
                    min_dist_sq = dist_sq
                    best_station = station
        
        if best_station:
            print(f"DEBUG: Agent._find_best_station_with_output: AgentGridPos={self.position} found best station {best_station.__class__.__name__} at {best_station.position} with output {output_resource_type.name} (dist_sq: {min_dist_sq:.2f})")
        else:
            # This case should ideally not be reached if candidate_stations was not empty,
            # unless all candidates lacked a position attribute (which would be an issue).
            print(f"Agent at {self.position} found no suitable station with output {output_resource_type.name} after filtering.")
        return best_station

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