import uuid
import time
from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

from .task_types import TaskType, TaskStatus
from ..resources.resource_types import ResourceType # Assuming this path is correct

# Forward references to avoid circular imports
if TYPE_CHECKING:
    from ..agents.agent import Agent # Assuming agent.py is in src/agents/
    from ..resources.manager import ResourceManager # Assuming manager.py is in src/resources/
    from ..resources.node import ResourceNode
    from ..resources.storage_point import StoragePoint
    # Add ..resources.processing.ProcessingStation if needed for other task types

class Task(ABC):
    """Base class for all tasks an agent can perform."""

    def __init__(self, task_type: TaskType, priority: int):
        self.task_id: uuid.UUID = uuid.uuid4()
        self.task_type: TaskType = task_type
        self.status: TaskStatus = TaskStatus.PENDING
        self.priority: int = priority
        self.agent_id: Optional[uuid.UUID] = None # Will be set when an agent is assigned
        self.creation_time: float = time.time()
        self.last_update_time: float = self.creation_time
        self.error_message: Optional[str] = None

    @abstractmethod
    def prepare(self, agent: 'Agent', resource_manager: 'ResourceManager') -> bool:
        """
        Handles initial claims, reservations, and any other setup required before
        the task can be executed.
        Sets the task status to PREPARING during its execution.
        Returns True if preparation was successful and the task can proceed, False otherwise.
        If successful, should set the task's status to an appropriate IN_PROGRESS state
        and potentially the agent's initial state.
        """
        pass

    @abstractmethod
    def execute_step(self, agent: 'Agent', dt: float, resource_manager: 'ResourceManager') -> TaskStatus:
        """
        Advances the task logic by one step or time delta.
        This method is called repeatedly by the assigned agent.
        It should update the task's status and return it.
        The task itself is responsible for changing the agent's state (e.g., agent.state = AgentState.MOVING_TO_RESOURCE).
        """
        pass

    @abstractmethod
    def cleanup(self, agent: 'Agent', resource_manager: 'ResourceManager', success: bool):
        """
        Called when the task is completed, failed, or cancelled.
        Releases any claims or reservations held by this task.
        Notifies the TaskManager of the outcome.
        """
        pass

    @abstractmethod
    def get_target_description(self) -> str:
        """Returns a string description of the current target or goal of the task for debugging/UI."""
        pass

    def _update_timestamp(self):
        self.last_update_time = time.time()


class GatherAndDeliverTask(Task):
    """A task for an agent to gather a specific resource and deliver it to a dropoff point."""

    def __init__(self,
                 priority: int,
                 resource_type_to_gather: ResourceType,
                 quantity_to_gather: int,
                 target_resource_node_id: Optional[uuid.UUID] = None, # Can be pre-assigned or found in prepare
                 target_dropoff_id: Optional[uuid.UUID] = None): # Can be pre-assigned or found in prepare
        super().__init__(TaskType.GATHER_AND_DELIVER, priority)
        self.resource_type_to_gather: ResourceType = resource_type_to_gather
        self.quantity_to_gather: int = quantity_to_gather # Target amount for this task instance
        
        # These will be populated during prepare() or if pre-assigned
        self.target_resource_node_ref: Optional['ResourceNode'] = None
        self.target_dropoff_ref: Optional['StoragePoint'] = None # Or ProcessingStation

        self.quantity_gathered: int = 0
        self.quantity_delivered: int = 0
        
        self.reserved_at_node: bool = False # More specific: store task_id in node
        self.reserved_at_dropoff_quantity: int = 0
        
        # Internal state machine for the task's progression
        # This could map to more detailed TaskStatus enum values or AgentState values
        self._current_step_key: str = "find_resource_and_dropoff" # Initial step

    def prepare(self, agent: 'Agent', resource_manager: 'ResourceManager') -> bool:
        # from ..agents.agent import AgentState # REMOVED
        self._update_timestamp()
        self.status = TaskStatus.PREPARING
        # agent.target_position = None # Agent's objective methods will handle target

        # 1. Find and Claim Resource Node
        if not self.target_resource_node_ref:
            # Simplified finding logic for now. TaskManager might do this or provide candidates.
            # Agent's current position: agent.position
            # ResourceManager: resource_manager.get_nodes_by_type(self.resource_type_to_gather)
            # TODO: Implement more sophisticated node finding (nearest, available, etc.)
            # For now, assume resource_manager can provide a suitable node or this task was created with one.
            # This part needs robust implementation based on how TaskManager generates tasks.
            
            # Placeholder: Find the first available node of the correct type
            candidate_nodes = resource_manager.get_nodes_by_type(self.resource_type_to_gather)
            for node in sorted(candidate_nodes, key=lambda n: (n.position - agent.position).length_squared()):
                if node.current_quantity >= 1 and node.claim(agent.id, self.task_id): # Using new claim
                    self.target_resource_node_ref = node
                    self.reserved_at_node = True # Or check node.claimed_by_task_id
                    break
            
        if not self.target_resource_node_ref:
            self.error_message = f"Could not find or claim resource node for {self.resource_type_to_gather.name}."
            self.status = TaskStatus.FAILED
            return False

        # 2. Find and Reserve Space at Dropoff
        if not self.target_dropoff_ref:
            # Simplified finding logic.
            # TODO: Implement sophisticated dropoff finding (accepts type, has space, nearest)
            # For now, assume resource_manager can provide a suitable storage point.
            # This part needs robust implementation.
            
            # Placeholder: Find the first storage point that can accept the resource
            # This should ideally consider the quantity we intend to gather.
            # The quantity to reserve should be min(self.quantity_to_gather, agent.inventory_capacity)
            qty_to_reserve_for_delivery = min(self.quantity_to_gather, agent.inventory_capacity)
            qty_to_reserve_for_delivery = min(self.target_resource_node_ref.current_quantity, qty_to_reserve_for_delivery) # Don't reserve more than available

            all_storage_points = resource_manager.storage_points # Assuming direct access
            for sp in sorted(all_storage_points, key=lambda s: (s.position - agent.position).length_squared()):
                # reserve_space should check accepted types and available capacity
                reserved_amount = sp.reserve_space(self.task_id, self.resource_type_to_gather, qty_to_reserve_for_delivery)
                if reserved_amount > 0:
                    self.target_dropoff_ref = sp
                    self.reserved_at_dropoff_quantity = reserved_amount
                    break
        
        if not self.target_dropoff_ref or self.reserved_at_dropoff_quantity == 0:
            self.error_message = f"Could not find or reserve space at dropoff for {self.resource_type_to_gather.name} (wanted to reserve {qty_to_reserve_for_delivery})."
            # Release claimed node if dropoff reservation fails
            if self.target_resource_node_ref and self.reserved_at_node:
                self.target_resource_node_ref.release(agent.id, self.task_id)
                self.reserved_at_node = False
            self.status = TaskStatus.FAILED
            return False

        # If all preparations are successful:
        self.status = TaskStatus.IN_PROGRESS_MOVE_TO_RESOURCE # First active step
        self._current_step_key = "move_to_resource"
        agent.set_objective_move_to_resource(self.target_resource_node_ref.position) # MODIFIED
        print(f"Task {self.task_id} PREPARED for agent {agent.id}. Target Node: {self.target_resource_node_ref.position}, Target Dropoff: {self.target_dropoff_ref.position}, Reserved Dropoff Qty: {self.reserved_at_dropoff_quantity}")
        return True

    def execute_step(self, agent: 'Agent', dt: float, resource_manager: 'ResourceManager') -> TaskStatus:
        self._update_timestamp()
        # from ..agents.agent import AgentState # REMOVED

        if not self.target_resource_node_ref or not self.target_dropoff_ref:
            self.error_message = "Target resource or dropoff became invalid during execution."
            self.status = TaskStatus.FAILED
            return self.status

        # --- Step: Move to Resource Node ---
        if self._current_step_key == "move_to_resource":
            # Task directs the agent to move to the resource.
            # The agent's set_objective_move_to_resource method handles setting the state and target.
            # No need to check agent.state here as the task is dictating the current objective.
            agent.set_objective_move_to_resource(self.target_resource_node_ref.position)

            if agent.move_towards_current_target(dt): # Agent reached the resource node
                self._current_step_key = "gather_resource"
                self.status = TaskStatus.IN_PROGRESS_GATHERING
                agent.set_objective_gather_resource(agent.config.DEFAULT_GATHERING_TIME)
            return self.status

        # --- Step: Gather Resource ---
        elif self._current_step_key == "gather_resource":
            # Objective to gather is set when transitioning to this step.
            # Here, we just check the timer and node status.
            # agent.set_objective_gather_resource(agent.config.DEFAULT_GATHERING_TIME) # REMOVED: Objective set on transition

            # Check if node still has resources / is still claimed by this task
            if self.target_resource_node_ref.current_quantity <= 0 or \
               self.target_resource_node_ref.claimed_by_task_id != self.task_id:
                self.error_message = "Resource node depleted or claim lost during gathering."
                # Potentially try to re-claim or find new node, or just fail
                self.status = TaskStatus.FAILED
                return self.status

            agent.gathering_timer -= dt
            if agent.gathering_timer <= 0:
                # Determine how much to gather:
                # Max agent can carry = agent.inventory_capacity - agent.current_inventory['quantity']
                # Max task wants = self.quantity_to_gather - self.quantity_gathered
                # Max can be dropped off = self.reserved_at_dropoff_quantity - self.quantity_delivered (assuming we deliver all gathered in one go)
                # Max available at node = self.target_resource_node_ref.current_quantity
                
                # Agent should only gather what it can carry AND what is reserved at dropoff for this trip
                # (assuming one gather -> one deliver cycle for simplicity here)
                can_carry_more = agent.inventory_capacity - agent.current_inventory['quantity']
                
                # Amount to gather for this specific trip, limited by what's reserved at dropoff and what agent can carry
                amount_to_attempt_gather = min(
                    can_carry_more,
                    self.reserved_at_dropoff_quantity, # This is the crucial link to prevent over-collection for storage
                    self.quantity_to_gather - self.quantity_gathered # Overall task goal
                )
                
                if amount_to_attempt_gather > 0:
                    gathered = self.target_resource_node_ref.collect_resource(amount_to_attempt_gather)
                    if gathered > 0:
                        # Assume agent inventory handles mixed types or is cleared for new task type
                        if agent.current_inventory['resource_type'] is None or agent.current_inventory['resource_type'] == self.resource_type_to_gather:
                            agent.current_inventory['resource_type'] = self.resource_type_to_gather
                            agent.current_inventory['quantity'] += gathered
                            self.quantity_gathered += gathered
                            print(f"Task {self.task_id}: Agent {agent.id} gathered {gathered} {self.resource_type_to_gather.name}. Total gathered for task: {self.quantity_gathered}")
                        else:
                            self.error_message = "Agent inventory has different resource type."
                            self.status = TaskStatus.FAILED # Or handle this more gracefully
                            return self.status
                
                # Transition to moving to dropoff
                self._current_step_key = "move_to_dropoff"
                self.status = TaskStatus.IN_PROGRESS_MOVE_TO_DROPOFF
                agent.set_objective_move_to_storage(self.target_dropoff_ref.position) # MODIFIED
                
                # Release node claim if we are done with it for this task
                # (e.g. if quantity_to_gather is met or node is empty)
                # For simplicity, if task is to gather X, and we gathered X, or node is empty, release.
                if self.quantity_gathered >= self.quantity_to_gather or self.target_resource_node_ref.current_quantity < 1:
                    if self.reserved_at_node: # Check if it was claimed by this task
                         self.target_resource_node_ref.release(agent.id, self.task_id)
                         self.reserved_at_node = False # Update task's view of claim
            return self.status

        # --- Step: Move to Dropoff ---
        elif self._current_step_key == "move_to_dropoff":
            # Task directs the agent to move to storage.
            agent.set_objective_move_to_storage(self.target_dropoff_ref.position)
            
            if agent.move_towards_current_target(dt):
                self._current_step_key = "deliver_resource"
                self.status = TaskStatus.IN_PROGRESS_DELIVERING
                agent.set_objective_deliver_resource(agent.config.DEFAULT_DELIVERY_TIME)
            return self.status

        # --- Step: Deliver Resource ---
        elif self._current_step_key == "deliver_resource":
            # Objective to deliver is set when transitioning to this step.
            # Here, we just check the timer.
            # agent.set_objective_deliver_resource(agent.config.DEFAULT_DELIVERY_TIME) # REMOVED: Objective set on transition

            agent.delivery_timer -= dt
            if agent.delivery_timer <= 0:
                amount_to_deliver = agent.current_inventory['quantity'] # Deliver whatever is in inventory for this resource type
                if amount_to_deliver > 0 and agent.current_inventory['resource_type'] == self.resource_type_to_gather:
                    # Use commit_reservation_to_storage
                    delivered_qty = self.target_dropoff_ref.commit_reservation_to_storage(
                        self.task_id,
                        self.resource_type_to_gather,
                        amount_to_deliver
                    )
                    
                    if delivered_qty > 0:
                        agent.current_inventory['quantity'] -= delivered_qty
                        self.quantity_delivered += delivered_qty
                        self.reserved_at_dropoff_quantity -= delivered_qty # Reduce active reservation
                        print(f"Task {self.task_id}: Agent {agent.id} delivered {delivered_qty} {self.resource_type_to_gather.name}. Total delivered for task: {self.quantity_delivered}")
                        if agent.current_inventory['quantity'] == 0:
                            agent.current_inventory['resource_type'] = None
                    else:
                        self.error_message = f"Failed to deliver {amount_to_deliver} to {self.target_dropoff_ref.position} despite reservation."
                        # This is a critical error if reservation was in place.
                        self.status = TaskStatus.FAILED
                        return self.status
                
                # Check if task is complete
                if self.quantity_delivered >= self.quantity_to_gather:
                    self.status = TaskStatus.COMPLETED
                elif agent.inventory_capacity == 0 and self.quantity_gathered < self.quantity_to_gather : # Agent delivered all it could carry, but task needs more
                    # Go back to gather more if task not complete and agent has capacity
                    # This requires re-claiming node if released, re-reserving space if needed.
                    # For simplicity now, if one cycle doesn't complete, it might need a new task or more complex logic.
                    # Current logic: one gather -> one deliver. If more is needed, this task might end and a new one created.
                    # Or, _current_step_key goes back to "move_to_resource" if node still valid and space can be reserved.
                    # This part needs careful design for multi-trip tasks.
                    # For now, let's assume if what was gathered is delivered, and task not met, it's a FAILED or needs more complex state.
                    # A simpler model: a task is for ONE trip. TaskManager makes more tasks.
                    # If we assume task is for ONE trip up to agent capacity or reservation:
                    self.status = TaskStatus.COMPLETED # Completed this trip. TaskManager can check if overall goal met.
                else:
                    # Still items in inventory but task not complete (should not happen if delivered all)
                    # Or, task requires more but agent is empty (handled above)
                    # If task is not complete, but agent is empty, it means this "trip" is done.
                    self.status = TaskStatus.COMPLETED # This specific gather-deliver cycle is done.
                                                     # TaskManager might need to issue a new task if overall goal not met.

            return self.status
        
        return self.status # Should not be reached if steps are exhaustive

    def cleanup(self, agent: 'Agent', resource_manager: 'ResourceManager', success: bool):
        self._update_timestamp()
        print(f"Task {self.task_id} cleanup. Success: {success}. Agent: {agent.id}")
        # Release resource node claim
        if self.target_resource_node_ref and self.reserved_at_node: # self.target_resource_node_ref.claimed_by_task_id == self.task_id:
            self.target_resource_node_ref.release(agent.id, self.task_id)
            self.reserved_at_node = False
            print(f"Task {self.task_id}: Released node {self.target_resource_node_ref.position}")

        # Release any remaining storage reservation
        if self.target_dropoff_ref and self.reserved_at_dropoff_quantity > 0:
            # release_reservation should take task_id and the amount to release (which is current remaining reservation)
            self.target_dropoff_ref.release_reservation(self.task_id, self.reserved_at_dropoff_quantity)
            print(f"Task {self.task_id}: Released {self.reserved_at_dropoff_quantity} from storage {self.target_dropoff_ref.position}")
            self.reserved_at_dropoff_quantity = 0
        
        # Agent's current_task will be set to None by the Agent class after this.
        # TaskManager will be notified by the Agent class.

    def get_target_description(self) -> str:
        if self._current_step_key == "move_to_resource" and self.target_resource_node_ref:
            return f"Moving to resource {self.resource_type_to_gather.name} at {self.target_resource_node_ref.position}"
        elif self._current_step_key == "gather_resource" and self.target_resource_node_ref:
            return f"Gathering {self.resource_type_to_gather.name} at {self.target_resource_node_ref.position}"
        elif self._current_step_key == "move_to_dropoff" and self.target_dropoff_ref:
            return f"Moving to dropoff at {self.target_dropoff_ref.position}"
        elif self._current_step_key == "deliver_resource" and self.target_dropoff_ref:
            return f"Delivering {self.resource_type_to_gather.name} to {self.target_dropoff_ref.position}"
        elif self.status == TaskStatus.PREPARING:
            return f"Preparing to gather {self.resource_type_to_gather.name}"
        return f"Gather/Deliver {self.resource_type_to_gather.name} (Status: {self.status.name})"
# TaskType.PROCESS_RESOURCE will be used for this.
class DeliverWheatToMillTask(Task):
    """
    A task for an agent to retrieve Wheat from a StoragePoint and deliver it to a Mill.
    The agent's inventory must be empty at the start.
    The agent is free after delivering the Wheat to the Mill.
    """

    def __init__(self,
                 priority: int,
                 quantity_to_retrieve: int,
                 target_storage_id: Optional[uuid.UUID] = None, # Optional: specific storage
                 target_processor_id: Optional[uuid.UUID] = None): # Optional: specific mill
        super().__init__(TaskType.PROCESS_RESOURCE, priority)
        self.resource_to_retrieve: ResourceType = ResourceType.WHEAT
        self.quantity_to_retrieve: int = quantity_to_retrieve # Target amount for this task

        # These will be populated during prepare() or if pre-assigned
        self.target_storage_ref: Optional['StoragePoint'] = None
        self.target_processor_ref: Optional['ProcessingStation'] = None # Specifically a Mill

        self.quantity_retrieved: int = 0 # From storage to agent inventory
        self.quantity_delivered_to_processor: int = 0 # From agent inventory to mill

        self.reserved_at_storage_for_pickup_quantity: int = 0
        
        self._current_step_key: str = "initial" # Initial step

    def prepare(self, agent: 'Agent', resource_manager: 'ResourceManager') -> bool:
        from ..resources.mill import Mill # Specific check for Mill

        self._update_timestamp()
        self.status = TaskStatus.PREPARING
        agent.target_position = None

        if agent.current_inventory['quantity'] > 0:
            self.error_message = f"Agent {agent.id} inventory is not empty (has {agent.current_inventory['quantity']} of {agent.current_inventory['resource_type']}). Cannot start DeliverWheatToMillTask."
            self.status = TaskStatus.FAILED
            return False

        # 1. Find and Reserve Wheat at StoragePoint
        if not self.target_storage_ref:
            # Find nearest StoragePoint that has WHEAT and allows pickup
            candidate_storages = [
                sp for sp in resource_manager.storage_points 
                if sp.has_resource(self.resource_to_retrieve, 1) # Check if at least 1 unit is present
            ]
            # Sort by distance to agent
            candidate_storages.sort(key=lambda s: (s.position - agent.position).length_squared())

            for sp in candidate_storages:
                # How much to try to reserve: min of task goal, agent capacity
                qty_to_attempt_reserve_pickup = min(self.quantity_to_retrieve - self.quantity_retrieved, agent.inventory_capacity)
                if qty_to_attempt_reserve_pickup <= 0: continue # Should not happen if quantity_to_retrieve > 0

                reserved_amount = sp.reserve_for_pickup(self.task_id, self.resource_to_retrieve, qty_to_attempt_reserve_pickup)
                if reserved_amount > 0:
                    self.target_storage_ref = sp
                    self.reserved_at_storage_for_pickup_quantity = reserved_amount
                    break
        
        if not self.target_storage_ref or self.reserved_at_storage_for_pickup_quantity == 0:
            self.error_message = f"Could not find or reserve {self.resource_to_retrieve.name} at any StoragePoint for pickup."
            self.status = TaskStatus.FAILED
            return False

        # 2. Find Mill
        if not self.target_processor_ref:
            candidate_processors = [
                p for p in resource_manager.processing_stations
                if isinstance(p, Mill) and p.can_accept_input(self.resource_to_retrieve, 1) # Mill accepts Wheat and has space for at least 1
            ]
            # Sort by distance to the storage point (or agent, depending on strategy)
            candidate_processors.sort(key=lambda p: (p.position - self.target_storage_ref.position).length_squared())
            
            if candidate_processors:
                self.target_processor_ref = candidate_processors[0]
            
        if not self.target_processor_ref:
            self.error_message = f"Could not find a suitable Mill that accepts {self.resource_to_retrieve.name}."
            # Release pickup reservation if mill not found
            if self.target_storage_ref and self.reserved_at_storage_for_pickup_quantity > 0:
                self.target_storage_ref.release_pickup_reservation(self.task_id, self.resource_to_retrieve, self.reserved_at_storage_for_pickup_quantity)
                self.reserved_at_storage_for_pickup_quantity = 0
            self.status = TaskStatus.FAILED
            return False

        # If all preparations are successful:
        self.status = TaskStatus.IN_PROGRESS_MOVE_TO_STORAGE
        self._current_step_key = "move_to_storage"
        agent.set_objective_move_to_storage(self.target_storage_ref.position)
        print(f"Task {self.task_id} (DeliverWheatToMill) PREPARED for agent {agent.id}. Target Storage: {self.target_storage_ref.position}, Target Mill: {self.target_processor_ref.position}, Reserved Pickup Qty: {self.reserved_at_storage_for_pickup_quantity}")
        return True

    def execute_step(self, agent: 'Agent', dt: float, resource_manager: 'ResourceManager') -> TaskStatus:
        self._update_timestamp()

        if not self.target_storage_ref or not self.target_processor_ref:
            self.error_message = "Target storage or processor became invalid during execution."
            self.status = TaskStatus.FAILED
            return self.status

        # --- Step: Move to StoragePoint ---
        if self._current_step_key == "move_to_storage":
            agent.set_objective_move_to_storage(self.target_storage_ref.position)
            if agent.move_towards_current_target(dt): # Agent reached storage
                self._current_step_key = "collect_from_storage"
                self.status = TaskStatus.IN_PROGRESS_COLLECTING_FROM_STORAGE
                # Use a config for collection time, e.g., agent.config.DEFAULT_COLLECTION_TIME_FROM_STORAGE
                # For now, using existing DEFAULT_GATHERING_TIME
                agent.set_objective_collect_from_storage(getattr(agent.config, "DEFAULT_COLLECTION_TIME_FROM_STORAGE", agent.config.DEFAULT_GATHERING_TIME))
            return self.status

        # --- Step: Collect from StoragePoint ---
        elif self._current_step_key == "collect_from_storage":
            # Agent's gathering_timer (reused for collection) ticks down in agent.update()
            if agent.gathering_timer <= 0:
                can_carry_more = agent.inventory_capacity - agent.current_inventory['quantity']
                
                # Amount to collect is what was reserved for pickup for this task, up to what agent can carry
                amount_to_attempt_collect = min(
                    can_carry_more,
                    self.reserved_at_storage_for_pickup_quantity - self.quantity_retrieved # what's left of our reservation
                )

                if amount_to_attempt_collect > 0:
                    collected_qty = self.target_storage_ref.collect_reserved_pickup(
                        self.task_id, 
                        self.resource_to_retrieve, 
                        amount_to_attempt_collect
                    )
                    
                    if collected_qty > 0:
                        if agent.current_inventory['resource_type'] is None or agent.current_inventory['resource_type'] == self.resource_to_retrieve:
                            agent.current_inventory['resource_type'] = self.resource_to_retrieve
                            agent.current_inventory['quantity'] += collected_qty
                            self.quantity_retrieved += collected_qty
                            # self.reserved_at_storage_for_pickup_quantity -= collected_qty # This is handled by collect_reserved_pickup
                            print(f"Task {self.task_id}: Agent {agent.id} collected {collected_qty} {self.resource_to_retrieve.name} from storage. Total retrieved for task: {self.quantity_retrieved}")
                        else:
                            self.error_message = "Agent inventory has different resource type during collection from storage."
                            self.status = TaskStatus.FAILED
                            return self.status
                    elif collected_qty == 0 and amount_to_attempt_collect > 0 : # Attempted to collect but got nothing
                         self.error_message = f"Failed to collect reserved {self.resource_to_retrieve.name} from storage {self.target_storage_ref.position}."
                         self.status = TaskStatus.FAILED # Or retry logic
                         return self.status

                # Transition to moving to mill if enough retrieved or agent full
                # This task assumes one trip from storage to mill.
                if self.quantity_retrieved > 0: # If anything was collected
                    self._current_step_key = "move_to_mill"
                    self.status = TaskStatus.IN_PROGRESS_MOVE_TO_PROCESSOR
                    agent.set_objective_move_to_processor(self.target_processor_ref.position)
                elif self.reserved_at_storage_for_pickup_quantity <= self.quantity_retrieved : # Reservation exhausted or met
                     self.error_message = f"Reservation for {self.resource_to_retrieve.name} at storage {self.target_storage_ref.position} exhausted before collecting anything for agent."
                     self.status = TaskStatus.FAILED # Failed to get anything useful
                     return self.status

            return self.status

        # --- Step: Move to Mill ---
        elif self._current_step_key == "move_to_mill":
            agent.set_objective_move_to_processor(self.target_processor_ref.position)
            if agent.move_towards_current_target(dt): # Agent reached mill
                self._current_step_key = "deliver_to_mill"
                self.status = TaskStatus.IN_PROGRESS_DELIVERING_TO_PROCESSOR
                agent.set_objective_deliver_to_processor(agent.config.DEFAULT_DELIVERY_TIME)
            return self.status

        # --- Step: Deliver to Mill ---
        elif self._current_step_key == "deliver_to_mill":
            # Agent's delivery_timer ticks down in agent.update()
            if agent.delivery_timer <= 0:
                amount_to_deliver = agent.current_inventory['quantity']
                if amount_to_deliver > 0 and agent.current_inventory['resource_type'] == self.resource_to_retrieve:
                    # Mill's receive method
                    delivered_qty = self.target_processor_ref.receive(self.resource_to_retrieve, amount_to_deliver)
                    
                    if delivered_qty > 0:
                        agent.current_inventory['quantity'] -= delivered_qty
                        self.quantity_delivered_to_processor += delivered_qty
                        print(f"Task {self.task_id}: Agent {agent.id} delivered {delivered_qty} {self.resource_to_retrieve.name} to Mill. Total delivered: {self.quantity_delivered_to_processor}")
                        if agent.current_inventory['quantity'] == 0:
                            agent.current_inventory['resource_type'] = None
                        
                        # Task is complete once all retrieved items are delivered
                        if self.quantity_delivered_to_processor >= self.quantity_retrieved:
                            self.status = TaskStatus.COMPLETED
                        # If agent delivered some but still has more (shouldn't happen if mill takes all),
                        # or if mill couldn't take all, this task might need more complex logic or fail.
                        # For now, assume mill takes what it can, and task completes if agent is empty.
                        elif agent.current_inventory['quantity'] == 0 :
                             self.status = TaskStatus.COMPLETED # Agent delivered all it had from this trip.
                    else: # Mill did not accept anything
                        self.error_message = f"Mill {self.target_processor_ref.position} failed to receive {amount_to_deliver} of {self.resource_to_retrieve.name}."
                        self.status = TaskStatus.FAILED
                        return self.status
                elif amount_to_deliver == 0 : # Agent arrived at mill with nothing
                     self.error_message = f"Agent arrived at mill with no {self.resource_to_retrieve.name} to deliver."
                     self.status = TaskStatus.FAILED # Should have been caught earlier
                     return self.status
            return self.status
        
        return self.status

    def cleanup(self, agent: 'Agent', resource_manager: 'ResourceManager', success: bool):
        self._update_timestamp()
        print(f"Task {self.task_id} (DeliverWheatToMill) cleanup. Success: {success}. Agent: {agent.id}")
        
        # Release any remaining pickup reservation at the storage point
        if self.target_storage_ref and self.task_id in self.target_storage_ref.pickup_reservations:
            # Check if there's still a reservation for the specific resource type
            if self.resource_to_retrieve in self.target_storage_ref.pickup_reservations[self.task_id]:
                amount_still_reserved = self.target_storage_ref.pickup_reservations[self.task_id][self.resource_to_retrieve]
                if amount_still_reserved > 0:
                    self.target_storage_ref.release_pickup_reservation(self.task_id, self.resource_to_retrieve, amount_still_reserved)
                    print(f"Task {self.task_id}: Released remaining pickup reservation of {amount_still_reserved} {self.resource_to_retrieve.name} from storage {self.target_storage_ref.position}")
            # Clean up task entry if empty
            if not self.target_storage_ref.pickup_reservations.get(self.task_id):
                 self.target_storage_ref.pickup_reservations.pop(self.task_id, None)


    def get_target_description(self) -> str:
        if self.status == TaskStatus.PREPARING:
            return f"Preparing to retrieve {self.resource_to_retrieve.name} for Mill"
        if self._current_step_key == "move_to_storage" and self.target_storage_ref:
            return f"Moving to Storage at {self.target_storage_ref.position} for {self.resource_to_retrieve.name}"
        elif self._current_step_key == "collect_from_storage" and self.target_storage_ref:
            return f"Collecting {self.resource_to_retrieve.name} from Storage at {self.target_storage_ref.position}"
        elif self._current_step_key == "move_to_mill" and self.target_processor_ref:
            return f"Moving {self.resource_to_retrieve.name} to Mill at {self.target_processor_ref.position}"
        elif self._current_step_key == "deliver_to_mill" and self.target_processor_ref:
            return f"Delivering {self.resource_to_retrieve.name} to Mill at {self.target_processor_ref.position}"
        return f"Process {self.resource_to_retrieve.name} (Status: {self.status.name})"