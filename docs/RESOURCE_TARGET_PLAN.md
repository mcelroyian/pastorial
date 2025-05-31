Problem 1: Agents Gather Resources Even if Storage is Full
Recommended Solution: Pre-Gathering Storage Check

This involves modifying the agent's decision-making process to ensure a valid drop-off location exists before committing to gather a resource.

1. Modify Agent class (agents/agent.py)
1.1. New Helper Method: _can_find_dropoff_for_resource(self, resource_type: ResourceType, quantity_to_check: int, resource_manager) -> bool
This method will check if there's any suitable storage or processing station that can accept the given resource type.

Python

# Add this method to the Agent class in agents/agent.py

    def _can_find_dropoff_for_resource(self, resource_type: ResourceType, quantity_to_check: int, resource_manager) -> bool:
        """
        Checks if a suitable drop-off (StoragePoint or ProcessingStation) exists
        for the given resource type and quantity without assigning it as a target.
        """
        # Check for StoragePoints
        try:
            candidate_storages = resource_manager.storage_points
            for storage_point in candidate_storages:
                if hasattr(storage_point, 'can_accept') and \
                   storage_point.can_accept(resource_type, quantity_to_check):
                    # print(f"DEBUG: Agent {self.position} found potential storage for {resource_type.name} at {storage_point.position}")
                    return True
        except AttributeError:
            print(f"Warning: resource_manager missing 'storage_points' during dropoff check. Agent: {self.position}")
            # Fall through to check processing stations if applicable

        # Check for ProcessingStations (if the resource is an input for any)
        # This logic assumes raw resources might go to processing stations.
        # If only specific resources (e.g., WHEAT to Mill) are processed, this check needs to be more specific.
        if resource_type == ResourceType.WHEAT: # Example: Only WHEAT is processed
            try:
                # Check if any station accepts this input type and has capacity
                # We don't need the *nearest* here, just *any* station.
                for station in resource_manager.processing_stations:
                    if station.accepted_input_type == resource_type and \
                       station.can_accept_input(resource_type, quantity_to_check):
                        # print(f"DEBUG: Agent {self.position} found potential processing for {resource_type.name} at {station.position}")
                        return True
            except AttributeError:
                print(f"Warning: resource_manager missing 'processing_stations' during dropoff check. Agent: {self.position}")

        # print(f"DEBUG: Agent {self.position} could NOT find dropoff for {resource_type.name}")
        return False
1.2. Modify Agent.update method (IDLE state logic)
The IDLE state logic needs to incorporate the _can_find_dropoff_for_resource check.

Python

# In agents/agent.py, within the Agent class:
# Modify the 'update' method, specifically the 'AgentState.IDLE' block:

    def update(self, dt: float, resource_manager):
        # ... (other parts of the update method remain the same) ...

        if self.state == AgentState.IDLE:
            if self.current_inventory['quantity'] > 0:
                self.state = AgentState.CARRYING_RESOURCE
                print(f"Agent {self.position} IDLE (has inventory) -> CARRYING_RESOURCE")
            else: # Inventory is empty
                # Find the best resource node *that also has a valid drop-off point*
                best_node_with_dropoff: Optional[ResourceNode] = None
                min_dist_sq_for_best_node = math.inf

                # Iterate through resource priorities to find a suitable task
                for res_type_priority in self.resource_priorities:
                    try:
                        candidate_nodes = resource_manager.get_nodes_by_type(res_type_priority)
                    except AttributeError:
                        print(f"Warning: resource_manager missing 'get_nodes_by_type'. Agent: {self.position}")
                        continue # Try next priority

                    potential_target_node_for_priority: Optional[ResourceNode] = None
                    min_dist_sq_for_priority_node = math.inf

                    for node in candidate_nodes:
                        if (hasattr(node, 'current_quantity') and int(node.current_quantity) >= 1 and
                            hasattr(node, 'resource_type') and node.resource_type == res_type_priority and
                            hasattr(node, 'position')):
                            
                            # --- MODIFICATION START: Check for drop-off feasibility ---
                            # Assume agent will try to gather at least 1 unit, or up to capacity
                            # For a simpler check, we can assume they'll gather 1 unit.
                            # A more complex check could estimate potential gather amount.
                            # For now, let's check if a drop-off exists for this resource type for a nominal quantity (e.g., 1)
                            if self._can_find_dropoff_for_resource(node.resource_type, 1, resource_manager):
                                dist_sq = (node.position - self.position).length_squared()
                                if dist_sq < min_dist_sq_for_priority_node:
                                    min_dist_sq_for_priority_node = dist_sq
                                    potential_target_node_for_priority = node
                            # --- MODIFICATION END ---
                    
                    if potential_target_node_for_priority:
                        # Found the best node for this priority that has a drop-off
                        # Now compare if this is better than a node from a higher priority (if any was found)
                        # Since we iterate through priorities, the first one found is the highest priority
                        best_node_with_dropoff = potential_target_node_for_priority
                        break # Found a suitable node for the current highest feasible priority

                if best_node_with_dropoff:
                    self.target_resource_node = best_node_with_dropoff
                    self.target_position = pygame.math.Vector2(self.target_resource_node.position)
                    self.state = AgentState.MOVING_TO_RESOURCE
                    print(f"DEBUG: Agent.update (IDLE -> MOVING_TO_RESOURCE): AgentGridPos={self.position}, TargetNodePos(resource)={self.target_resource_node.position} (Dropoff exists for {self.target_resource_node.resource_type.name})")
                else:
                    # No raw resources found with valid drop-offs.
                    # Check if we should collect processed goods (existing logic).
                    self.target_processing_station = self._find_best_station_with_output(resource_manager, ResourceType.FLOUR_POWDER)
                    if self.target_processing_station:
                        # Before moving to collect, ensure there's storage for what we are about to collect
                        if self._can_find_dropoff_for_resource(ResourceType.FLOUR_POWDER, 1, resource_manager):
                            self.target_position = pygame.math.Vector2(self.target_processing_station.position)
                            self.state = AgentState.MOVING_TO_PROCESSOR # Moving to collect output
                            print(f"DEBUG: Agent.update (IDLE -> MOVING_TO_PROCESSOR to collect FLOUR_POWDER): AgentGridPos={self.position}, TargetStationPos={self.target_processing_station.position} (Dropoff exists for FLOUR_POWDER)")
                        else:
                            print(f"Agent {self.position} found FLOUR_POWDER to collect but no place to store it. Moving randomly.")
                            self.state = AgentState.MOVING_RANDOMLY
                    else:
                        self.state = AgentState.MOVING_RANDOMLY
                        print(f"Agent {self.position} IDLE -> MOVING_RANDOMLY (no resources with dropoffs or flour to collect with dropoff)")
        
        # ... (rest of the update method logic for other states) ...
Explanation of Changes for Problem 1:

The _can_find_dropoff_for_resource method is introduced to encapsulate the logic of checking StoragePoints and relevant ProcessingStations for their can_accept capability for a given resource type.
In the IDLE state of Agent.update:
When an agent is looking for a raw resource node, it iterates through its resource_priorities.
For each candidate ResourceNode, it now calls self._can_find_dropoff_for_resource(node.resource_type, 1, resource_manager) to verify that a drop-off exists for the type of resource the node provides.
Only if such a drop-off exists will the node be considered a valid target.
A similar check is added before deciding to collect processed goods (e.g., FLOUR_POWDER from a Mill).
Problem 2: Multiple Agents Target the Same Resource Node
Recommended Solution: Resource Node Reservation/Targeting Flags

This involves adding a way for agents to "claim" a resource node they are targeting, so other agents will ignore it.

1. Modify ResourceNode class (resources/node.py)
1.1. Add New Attributes and Methods
Python

# In resources/node.py, within the ResourceNode class:

from abc import ABC, abstractmethod
import pygame # Ensure pygame is imported if not already for Vector2
from ..resources.resource_types import ResourceType # Import ResourceType

class ResourceNode(ABC):
    def __init__(self, position: pygame.Vector2, capacity: int, generation_rate: float, resource_type: ResourceType):
        if not isinstance(position, pygame.Vector2):
            raise TypeError("Position must be a pygame.Vector2")
        self.position = position
        self.capacity = int(capacity)
        self.generation_rate = generation_rate
        self.resource_type = resource_type
        self.current_quantity = 0.0
        
        # --- NEW ATTRIBUTE for reservation ---
        self.is_targeted: bool = False 
        # self.targeted_by_agent_id: Optional[int] = None # Alternative if you have agent IDs

    # ... (update method remains the same) ...

    # --- NEW METHODS for reservation ---
    def claim(self) -> bool:
        """Attempts to claim this resource node. Returns True if successful, False otherwise."""
        if not self.is_targeted:
            self.is_targeted = True
            # print(f"DEBUG: Node {self.position} claimed.")
            return True
        # print(f"DEBUG: Node {self.position} FAILED to claim (already targeted).")
        return False

    def release(self):
        """Releases the claim on this resource node."""
        if self.is_targeted:
            self.is_targeted = False
            # print(f"DEBUG: Node {self.position} released.")
        # else:
            # print(f"DEBUG: Node {self.position} release called but was not targeted.")


    @abstractmethod
    def draw(self, surface: pygame.Surface, font: pygame.font.Font, grid):
        pass

    def collect_resource(self, amount_to_collect: int) -> int:
        # ... (existing collect_resource logic) ...
2. Modify Agent class (agents/agent.py)
2.1. Modify _find_best_resource_target method
This method needs to check the is_targeted flag and claim the node.

Python

# In agents/agent.py, within the Agent class:
# Modify the '_find_best_resource_target' method:

    def _find_best_resource_target(self, resource_manager) -> Optional[ResourceNode]:
        best_node_choice: Optional[ResourceNode] = None
        min_dist_sq = math.inf

        for res_type in self.resource_priorities:
            try:
                candidate_nodes = resource_manager.get_nodes_by_type(res_type)
            except AttributeError:
                print(f"Warning: resource_manager missing 'get_nodes_by_type'. Agent: {self.position}")
                return None

            for node in candidate_nodes:
                # --- MODIFICATION START: Check if node is targeted and has quantity ---
                if (hasattr(node, 'current_quantity') and int(node.current_quantity) >= 1 and
                    hasattr(node, 'resource_type') and node.resource_type == res_type and
                    hasattr(node, 'position') and
                    hasattr(node, 'is_targeted') and not node.is_targeted): # Check if not already targeted
                    # --- MODIFICATION END ---
                    
                    # This is where the Pre-Gathering Storage Check (from Problem 1) should also be integrated
                    # if you want _find_best_resource_target to be the sole decision point.
                    # For clarity, the solution for Problem 1 was placed in the Agent.update's IDLE state directly.
                    # If you prefer it here, you'd call self._can_find_dropoff_for_resource here.
                    # For now, assuming the IDLE state handles the dropoff check before calling this.
                    # OR, if this method is called by the IDLE state's new logic, this check here is fine.

                    dist_sq = (node.position - self.position).length_squared()
                    if dist_sq < min_dist_sq:
                        min_dist_sq = dist_sq
                        best_node_choice = node
            
            if best_node_choice: # Found a suitable node for this priority
                # --- MODIFICATION: Attempt to claim the chosen node ---
                if best_node_choice.claim():
                    print(f"DEBUG: Agent._find_best_resource_target: AgentGridPos={self.position} found and CLAIMED best resource: {best_node_choice.resource_type.name} at NodePos={best_node_choice.position}")
                    return best_node_choice
                else:
                    # Claim failed (race condition, another agent claimed it just now)
                    print(f"DEBUG: Agent._find_best_resource_target: AgentGridPos={self.position} found resource {best_node_choice.position} but FAILED to claim. Re-evaluating.")
                    best_node_choice = None # Reset and continue search for other nodes or lower priorities
                    min_dist_sq = math.inf # Reset min_dist for this priority to re-evaluate other nodes
                    # Potentially restart search for this res_type or continue to next node in this res_type list
                    # For simplicity, let's just nullify and let the outer loop continue,
                    # or the next priority be checked.
                    # A more robust solution might re-scan nodes of the current priority.
                    # However, with the current loop structure, it will naturally look at other nodes for this priority
                    # or move to the next priority if this was the last suitable one.
        
        if not best_node_choice: # Fallback if loop completed without claiming a node
            print(f"Agent at {self.position} found no suitable AND claimable resource target.")
        return best_node_choice # Returns None if no claimable node was found
2.2. Modify Agent.update method for state transitions (releasing claims)
Ensure nodes are released when the agent is done with them or changes its mind.

Python

# In agents/agent.py, within the Agent class:
# Modify the 'update' method in various states:

    def update(self, dt: float, resource_manager):
        # ...
        if self.state == AgentState.IDLE:
            # ... (logic as modified for Problem 1) ...
            # Ensure any previous target_resource_node is released if an agent becomes IDLE unexpectedly
            if self.target_resource_node and hasattr(self.target_resource_node, 'release'):
                print(f"DEBUG: Agent {self.position} becoming IDLE, releasing previous target {self.target_resource_node.position}")
                self.target_resource_node.release()
                self.target_resource_node = None # Clear it
            
            # ... (rest of IDLE logic to find new target) ...
            # If after all checks, a new target_resource_node is set in IDLE (e.g., by _find_best_resource_target called within IDLE's new logic)
            # it should have already been claimed by _find_best_resource_target.
            # The assignment of self.target_resource_node happens in the IDLE state based on the output of _find_best_resource_target
            # (or similar logic as shown in Problem 1's solution).

            # The original line: self.target_resource_node = self._find_best_resource_target(resource_manager)
            # is now integrated into the more complex decision logic in IDLE for Problem 1.
            # Let's assume `best_node_with_dropoff` from Problem 1's solution IS the result of a find-and-claim attempt.
            # If `best_node_with_dropoff` is set:
            #   self.target_resource_node = best_node_with_dropoff # It was already claimed if found
            #   ... set state to MOVING_TO_RESOURCE ...

        # ...

        elif self.state == AgentState.MOVING_TO_RESOURCE:
            if not self.target_resource_node or not self.target_position:
                # --- MODIFICATION: Release if target becomes invalid ---
                if self.target_resource_node and hasattr(self.target_resource_node, 'release'):
                    self.target_resource_node.release()
                self.state = AgentState.IDLE; self.target_resource_node = None; return

            if self.target_resource_node.current_quantity <= 0: # Target depleted
                # --- MODIFICATION: Release if target depleted ---
                if hasattr(self.target_resource_node, 'release'):
                    self.target_resource_node.release()
                self.state = AgentState.IDLE; self.target_resource_node = None; self.target_position = None; return
            
            if self._move_towards_target(dt):
                self.state = AgentState.GATHERING_RESOURCE
                self.gathering_timer = config.DEFAULT_GATHERING_TIME
                self.target_position = None
                # Node remains claimed while gathering

        elif self.state == AgentState.GATHERING_RESOURCE:
            if not self.target_resource_node:
                # --- MODIFICATION: Release if target lost (should ideally not happen if claimed) ---
                # This implies an external change or an issue. If it had a target, it should be released.
                # However, target_resource_node should still be set here from MOVING_TO_RESOURCE.
                # For safety, we could add a check and release, but let's assume it's set.
                self.state = AgentState.IDLE; return # Go to IDLE to re-evaluate

            if self.target_resource_node.current_quantity <= 0: # Depleted during gathering
                # --- MODIFICATION: Release after attempting to gather from depleted node ---
                if hasattr(self.target_resource_node, 'release'):
                    self.target_resource_node.release()
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
                
                # --- MODIFICATION: Release node after gathering is complete (or attempted) ---
                if hasattr(self.target_resource_node, 'release'):
                    self.target_resource_node.release()
                self.state = AgentState.CARRYING_RESOURCE
                self.target_resource_node = None # Clear the reference

        # ... (other states) ...

        # IMPORTANT: Ensure that if an agent is "reset" or "dies" (if such mechanics exist or are planned),
        # any claimed resource node is released. This might require a cleanup method on the agent
        # or the AgentManager handling such events.
Explanation of Changes for Problem 2:

ResourceNode:
Gains an is_targeted boolean attribute (default False).
claim(): Sets is_targeted to True if it wasn't already. Returns success/failure.
release(): Sets is_targeted to False.
Agent:
_find_best_resource_target:
Filters out nodes where node.is_targeted is True.
If a suitable, untargeted node is found, it calls node.claim(). Only if the claim is successful does the agent select this node. This handles potential race conditions where two agents might see the same node as free almost simultaneously.
update method (State Transitions):
IDLE: If an agent becomes IDLE and previously had a target_resource_node (e.g., task interrupted), that node is released. The process of finding a new target resource node (as detailed in Problem 1 solution) should incorporate the claim mechanism (e.g., the _find_best_resource_target called from IDLE's logic will attempt the claim).
MOVING_TO_RESOURCE: If the target node becomes invalid (e.g., disappears or is depleted before arrival), it's released.
GATHERING_RESOURCE: The node is released once gathering is finished (or if it's found to be depleted upon starting to gather, or if inventory fills up).
The agent no longer holds a claim on the target_resource_node once it transitions to CARRYING_RESOURCE.
Integration Note for Problem 1 & 2:

The solution for Problem 1 (Pre-Gathering Storage Check) modifies the agent's decision process in the IDLE state before it even calls _find_best_resource_target (or, _find_best_resource_target could be adapted to include this check). The solution for Problem 2 (Reservation) modifies _find_best_resource_target itself to handle claiming.

You'll need to ensure these two pieces of logic work together smoothly. The IDLE state logic from Problem 1's solution should now call the modified _find_best_resource_target (from Problem 2's solution) which handles both finding a non-targeted node AND attempting to claim it.

Refined Agent.update IDLE state (combining concepts):

Python

# In agents/agent.py, Agent.update, IDLE state:
        if self.state == AgentState.IDLE:
            # Release any previous target if unexpectedly returning to IDLE
            if self.target_resource_node and hasattr(self.target_resource_node, 'release'):
                print(f"DEBUG: Agent {self.position} becoming IDLE, releasing previous target {self.target_resource_node.position if self.target_resource_node else 'None'}")
                self.target_resource_node.release()
                self.target_resource_node = None

            if self.current_inventory['quantity'] > 0:
                self.state = AgentState.CARRYING_RESOURCE
                print(f"Agent {self.position} IDLE (has inventory) -> CARRYING_RESOURCE")
            else: # Inventory is empty
                # Try to find a raw resource to collect first
                # _find_best_resource_target now handles checking 'is_targeted' and claiming.
                # We also need to ensure _can_find_dropoff_for_resource is checked for its type.

                # New approach for IDLE: Iterate priorities, for each find node, check dropoff, then try to claim.
                chosen_node_to_gather: Optional[ResourceNode] = None
                for res_type_priority in self.resource_priorities:
                    # Get all nodes of this type (that are not already targeted and have quantity)
                    # This part of logic is somewhat duplicated from _find_best_resource_target,
                    # suggesting _find_best_resource_target could be refactored or called differently.
                    # For this guide, let's keep it explicit here for clarity of the combined logic.
                    
                    candidate_nodes_for_priority = []
                    try:
                        all_nodes_of_type = resource_manager.get_nodes_by_type(res_type_priority)
                        for node in all_nodes_of_type:
                            if (hasattr(node, 'current_quantity') and int(node.current_quantity) >= 1 and
                                hasattr(node, 'is_targeted') and not node.is_targeted):
                                candidate_nodes_for_priority.append(node)
                    except AttributeError:
                        continue # Next priority

                    # Sort them by distance (optional, but good for "best")
                    candidate_nodes_for_priority.sort(key=lambda n: (n.position - self.position).length_squared())

                    for potential_node in candidate_nodes_for_priority:
                        if self._can_find_dropoff_for_resource(potential_node.resource_type, 1, resource_manager):
                            # Now, try to claim this node
                            if potential_node.claim():
                                chosen_node_to_gather = potential_node
                                break # Found and claimed a node
                            # Else: claim failed, try next potential_node
                    if chosen_node_to_gather:
                        break # Found and claimed a node for this priority, move on

                if chosen_node_to_gather:
                    self.target_resource_node = chosen_node_to_gather
                    self.target_position = pygame.math.Vector2(self.target_resource_node.position)
                    self.state = AgentState.MOVING_TO_RESOURCE
                    print(f"DEBUG: Agent.update (IDLE -> MOVING_TO_RESOURCE): AgentGridPos={self.position}, Claimed TargetNodePos={self.target_resource_node.position} (Dropoff exists for {self.target_resource_node.resource_type.name})")
                else:
                    # No raw resources found that meet all criteria (available, not targeted, has dropoff, claimable)
                    # Fallback to existing logic for collecting processed goods (which also needs dropoff check)
                    self.target_processing_station = self._find_best_station_with_output(resource_manager, ResourceType.FLOUR_POWDER)
                    if self.target_processing_station:
                        if self._can_find_dropoff_for_resource(ResourceType.FLOUR_POWDER, 1, resource_manager): # Check dropoff for flour
                             # Note: Processing stations do not have a claim mechanism in this example.
                             # If multiple agents target the same station output, it's first-come, first-served.
                            self.target_position = pygame.math.Vector2(self.target_processing_station.position)
                            self.state = AgentState.MOVING_TO_PROCESSOR 
                            print(f"DEBUG: Agent.update (IDLE -> MOVING_TO_PROCESSOR to collect FLOUR_POWDER): TargetStationPos={self.target_processing_station.position}")
                        else:
                            self.state = AgentState.MOVING_RANDOMLY
                            print(f"Agent {self.position} IDLE -> MOVING_RANDOMLY (found flour but no dropoff)")
                    else:
                        self.state = AgentState.MOVING_RANDOMLY
                        print(f"Agent {self.position} IDLE -> MOVING_RANDOMLY (no suitable tasks)")

This refined IDLE state logic is more complex but integrates both checks: ensuring a drop-off exists AND successfully claiming an un-targeted resource node. You might consider further refactoring _find_best_resource_target to better fit into this flow or to encapsulate more of this combined logic. For instance, _find_best_resource_target could take resource_manager and the resource_type as arguments and return the best claimable node of that type, or None. The IDLE state would then loop priorities, call this refined finder, and then do the drop-off check.

This detailed guide should provide a solid foundation for implementing these improvements. Remember to test thoroughly after each set of changes.