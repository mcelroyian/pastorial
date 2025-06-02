import uuid
import time
from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING, List

from .task_types import TaskType, TaskStatus
from ..resources.resource_types import ResourceType # Assuming this path is correct
from ..agents.intents import Intent, IntentStatus, MoveIntent, InteractAtTargetIntent # New import

# Forward references to avoid circular imports
if TYPE_CHECKING:
    from ..agents.agent import Agent
    from ..resources.manager import ResourceManager # Assuming manager.py is in src/resources/
    from ..resources.node import ResourceNode
    from ..resources.storage_point import StoragePoint
    # from ..agents.intents import Intent # Already imported

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
        self.active_intents: List[uuid.UUID] = [] # To track intents submitted by this task

    @abstractmethod
    def prepare(self, agent: 'Agent', resource_manager: 'ResourceManager') -> bool:
        """
        Handles initial claims, reservations, and any other setup required before
        the task can be executed.
        Sets the task status to PREPARING during its execution.
        Returns True if preparation was successful and the task can proceed, False otherwise.
        If successful, should set the task's status to an appropriate IN_PROGRESS state
        and submit the first intent to the agent.
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

    @abstractmethod
    def on_intent_outcome(self, agent: 'Agent', intent_id: uuid.UUID, intent_status: IntentStatus, resource_manager: 'ResourceManager'):
        """
        Called by the Agent when an Intent submitted by this task has an outcome.
        The task should update its internal state based on the intent's success or failure
        and potentially submit new intents or change its overall status.
        """
        pass

    def _update_timestamp(self):
        self.last_update_time = time.time()

    def _submit_intent_to_agent(self, agent: 'Agent', intent: 'Intent'):
        """Helper to submit an intent and track it."""
        # Ensure agent has the submit_intent method
        if hasattr(agent, 'submit_intent') and callable(getattr(agent, 'submit_intent')):
            agent.submit_intent(intent) # type: ignore
            self.active_intents.append(intent.intent_id)
            print(f"Task {self.task_id} submitted intent {intent.intent_id} ({intent.get_description()}) to agent {agent.id}")
        else:
            print(f"ERROR: Task {self.task_id} tried to submit intent, but agent {agent.id} does not have submit_intent method.")
            # This would be a critical error, potentially fail the task.
            self.status = TaskStatus.FAILED
            self.error_message = "Agent does not support intent submission."


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
        # Reset fields that might be stale from a previous failed attempt
        self.target_resource_node_ref = None
        self.target_dropoff_ref = None
        self.reserved_at_node = False
        self.reserved_at_dropoff_quantity = 0
        self.error_message = None # Clear any previous error messages

        # from ..agents.agent import AgentState # REMOVED
        self._update_timestamp()
        self.status = TaskStatus.PREPARING

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

        # Determine the quantity to aim to reserve for delivery
        # This needs to be calculated regardless of whether we are finding a new dropoff or using an existing one.
        qty_to_reserve_for_delivery = min(self.quantity_to_gather, agent.inventory_capacity)
        if self.target_resource_node_ref: # Should always be true here, but good practice
            qty_to_reserve_for_delivery = min(self.target_resource_node_ref.current_quantity, qty_to_reserve_for_delivery)
        else: # Should not happen if node check above passed
            qty_to_reserve_for_delivery = 0


        # 2. Find and Reserve Space at Dropoff
        if not self.target_dropoff_ref:
            # Simplified finding logic.
            # TODO: Implement sophisticated dropoff finding (accepts type, has space, nearest)
            # For now, assume resource_manager can provide a suitable storage point.
            # This part needs robust implementation.
            
            # Placeholder: Find the first storage point that can accept the resource
            # This should ideally consider the quantity we intend to gather.
            # The quantity to reserve was calculated above.

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
        # Submit the first intent to the agent
        if not self.target_resource_node_ref: # Should have been caught earlier
            self.status = TaskStatus.FAILED
            self.error_message = "Target resource node ref is None in prepare, cannot create MoveIntent."
            return False

        # Find a walkable tile adjacent to the resource node
        interaction_pos_node = agent.grid.find_walkable_adjacent_tile(self.target_resource_node_ref.position) # type: ignore
        if not interaction_pos_node:
            self.error_message = f"Could not find walkable adjacent tile for resource node {self.target_resource_node_ref.position}."
            # Release claimed node and dropoff reservation if interaction spot not found
            if self.target_resource_node_ref and self.reserved_at_node:
                self.target_resource_node_ref.release(agent.id, self.task_id) # type: ignore
                self.reserved_at_node = False
            if self.target_dropoff_ref and self.reserved_at_dropoff_quantity > 0:
                self.target_dropoff_ref.release_reservation(self.task_id, self.reserved_at_dropoff_quantity) # type: ignore
                self.reserved_at_dropoff_quantity = 0
            self.status = TaskStatus.FAILED
            return False

        move_intent = MoveIntent(interaction_pos_node, task_id=self.task_id)
        self._submit_intent_to_agent(agent, move_intent)
        
        self.status = TaskStatus.IN_PROGRESS_MOVE_TO_RESOURCE # Initial task status
        self._current_step_key = "move_to_resource" # Task's internal tracking of its current phase
        
        # Pathfinding success/failure will be handled by on_intent_outcome.
        # No need to check agent.current_path here anymore.
        print(f"Task {self.task_id} PREPARED for agent {agent.id}. Submitted MoveIntent to Node: {self.target_resource_node_ref.position}. Reserved Dropoff Qty: {self.reserved_at_dropoff_quantity}")
        return True

    # execute_step is no longer needed as task progression is driven by on_intent_outcome
    # def execute_step(self, agent: 'Agent', dt: float, resource_manager: 'ResourceManager') -> TaskStatus:
    #     self._update_timestamp()
    #     return self.status

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

    def on_intent_outcome(self, agent: 'Agent', intent_id: uuid.UUID, intent_status: IntentStatus, resource_manager: 'ResourceManager'):
        self._update_timestamp()
        print(f"Task {self.task_id} (GatherAndDeliverTask) received outcome for intent {intent_id} ({agent.current_intent.get_description() if agent.current_intent and agent.current_intent.intent_id == intent_id else 'Intent Mismatch or Cleared'}): {intent_status.name}") # type: ignore
        
        original_intent_description = "Unknown Intent"
        if agent.current_intent and agent.current_intent.intent_id == intent_id: # Should be the case
            original_intent_description = agent.current_intent.get_description()

        if intent_id in self.active_intents:
            self.active_intents.remove(intent_id)
        else:
            print(f"Warning: Task {self.task_id} received outcome for an untracked or already removed intent {intent_id}.")
            # Potentially an issue if an intent completes/fails after task already moved on or failed for other reasons.

        if self.status in [TaskStatus.FAILED, TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
            print(f"Task {self.task_id} is already in a terminal state ({self.status.name}). Ignoring intent outcome for {intent_id}.")
            return

        if intent_status == IntentStatus.FAILED:
            self.status = TaskStatus.FAILED
            self.error_message = f"Intent {intent_id} ({original_intent_description}) failed. Task Error: {agent.current_intent.error_message if agent.current_intent and agent.current_intent.intent_id == intent_id else 'N/A'}" # type: ignore
            print(f"Task {self.task_id} FAILED due to failed intent {intent_id}. Error: {self.error_message}")
            return

        if intent_status == IntentStatus.CANCELLED:
            self.status = TaskStatus.FAILED # Or CANCELLED if we want to distinguish
            self.error_message = f"Intent {intent_id} ({original_intent_description}) was cancelled."
            print(f"Task {self.task_id} FAILED due to cancelled intent {intent_id}.")
            return

        # --- Intent COMPLETED Logic ---
        if intent_status == IntentStatus.COMPLETED:
            if self._current_step_key == "move_to_resource":
                print(f"Task {self.task_id}: MoveIntent to resource node completed.")
                self._current_step_key = "gather_resource"
                self.status = TaskStatus.IN_PROGRESS_GATHERING
                if not self.target_resource_node_ref: # Should not happen
                    self.status = TaskStatus.FAILED; self.error_message = "target_resource_node_ref is None before gather intent"; return
                
                gather_intent = InteractAtTargetIntent(
                    target_id=self.target_resource_node_ref.id, # type: ignore
                    interaction_type="GATHER_RESOURCE",
                    duration=agent.config.DEFAULT_GATHERING_TIME,
                    task_id=self.task_id
                )
                self._submit_intent_to_agent(agent, gather_intent)

            elif self._current_step_key == "gather_resource":
                print(f"Task {self.task_id}: InteractAtTargetIntent (GATHER_RESOURCE) completed.")
                # Perform actual resource collection logic here
                if not self.target_resource_node_ref or not self.target_dropoff_ref: # Should not happen
                     self.status = TaskStatus.FAILED; self.error_message = "target_resource_node_ref or target_dropoff_ref is None after gather intent"; return

                can_carry_more = agent.inventory_capacity - agent.current_inventory.get('quantity', 0)
                amount_to_attempt_gather = min(
                    can_carry_more,
                    self.reserved_at_dropoff_quantity,
                    self.quantity_to_gather - self.quantity_gathered
                )
                if amount_to_attempt_gather > 0:
                    gathered = self.target_resource_node_ref.collect_resource(amount_to_attempt_gather)
                    if gathered > 0:
                        if agent.current_inventory.get('resource_type') is None or agent.current_inventory.get('resource_type') == self.resource_type_to_gather:
                            agent.current_inventory['resource_type'] = self.resource_type_to_gather
                            agent.current_inventory['quantity'] = agent.current_inventory.get('quantity', 0) + gathered # type: ignore
                            self.quantity_gathered += gathered
                            print(f"Task {self.task_id}: Agent {agent.id} inventory: {agent.current_inventory['quantity']} of {self.resource_type_to_gather.name}. Task gathered: {self.quantity_gathered}")
                        else:
                            self.status = TaskStatus.FAILED; self.error_message = "Agent inventory type mismatch during gather."; return
                    # else: Node might be empty, or couldn't collect. This might be an error or just 0 gathered.
                
                # Transition to moving to dropoff
                self._current_step_key = "move_to_dropoff"
                self.status = TaskStatus.IN_PROGRESS_MOVE_TO_DROPOFF
                
                # Find a walkable tile adjacent to the dropoff
                interaction_pos_dropoff = agent.grid.find_walkable_adjacent_tile(self.target_dropoff_ref.position) # type: ignore
                if not interaction_pos_dropoff:
                    self.error_message = f"Could not find walkable adjacent tile for dropoff {self.target_dropoff_ref.position}."
                    self.status = TaskStatus.FAILED
                    # Note: Resources are in agent's inventory. Cleanup will handle node/storage reservations if any are left.
                    return

                move_to_dropoff_intent = MoveIntent(interaction_pos_dropoff, task_id=self.task_id)
                self._submit_intent_to_agent(agent, move_to_dropoff_intent)

                if self.target_resource_node_ref and (self.quantity_gathered >= self.quantity_to_gather or self.target_resource_node_ref.current_quantity < 1): # type: ignore
                    if self.reserved_at_node:
                         self.target_resource_node_ref.release(agent.id, self.task_id) # type: ignore
                         self.reserved_at_node = False

            elif self._current_step_key == "move_to_dropoff":
                print(f"Task {self.task_id}: MoveIntent to dropoff completed.")
                self._current_step_key = "deliver_resource"
                self.status = TaskStatus.IN_PROGRESS_DELIVERING
                if not self.target_dropoff_ref: # Should not happen
                    self.status = TaskStatus.FAILED; self.error_message = "target_dropoff_ref is None before deliver intent"; return

                deliver_intent = InteractAtTargetIntent(
                    target_id=self.target_dropoff_ref.id, # type: ignore
                    interaction_type="DELIVER_RESOURCE",
                    duration=agent.config.DEFAULT_DELIVERY_TIME,
                    task_id=self.task_id
                )
                self._submit_intent_to_agent(agent, deliver_intent)

            elif self._current_step_key == "deliver_resource":
                print(f"Task {self.task_id}: InteractAtTargetIntent (DELIVER_RESOURCE) completed.")
                if not self.target_dropoff_ref: # Should not happen
                     self.status = TaskStatus.FAILED; self.error_message = "target_dropoff_ref is None after deliver intent"; return

                amount_to_deliver = agent.current_inventory.get('quantity', 0)
                if amount_to_deliver > 0 and agent.current_inventory.get('resource_type') == self.resource_type_to_gather:
                    delivered_qty = self.target_dropoff_ref.commit_reservation_to_storage(
                        self.task_id, self.resource_type_to_gather, amount_to_deliver
                    )
                    if delivered_qty > 0:
                        agent.current_inventory['quantity'] = agent.current_inventory.get('quantity', 0) - delivered_qty # type: ignore
                        self.quantity_delivered += delivered_qty
                        self.reserved_at_dropoff_quantity -= delivered_qty
                        print(f"Task {self.task_id}: Agent {agent.id} delivered {delivered_qty}. Task delivered: {self.quantity_delivered}. Agent inv: {agent.current_inventory['quantity']}")
                        if agent.current_inventory.get('quantity', 0) == 0:
                            agent.current_inventory['resource_type'] = None
                    else:
                        self.status = TaskStatus.FAILED; self.error_message = "Failed to commit delivery to storage despite reservation."; return
                
                if self.quantity_delivered >= self.quantity_to_gather:
                    self.status = TaskStatus.COMPLETED
                    print(f"Task {self.task_id} COMPLETED.")
                else:
                    # For a single-trip task, if delivery happened but goal not met, it's effectively done for this cycle.
                    # More complex logic for multi-trip would go here (e.g., loop back to move_to_resource if possible)
                    self.status = TaskStatus.COMPLETED # Assuming one-trip completion for now
                    print(f"Task {self.task_id} COMPLETED (one-trip assumption, delivered {self.quantity_delivered}/{self.quantity_to_gather}).")
            else:
                print(f"Warning: Task {self.task_id} completed intent {intent_id} in unhandled step: {self._current_step_key}")
        
        # If no active intents and task not yet terminal, something might be wrong or it's a task that completes without intents.
        if not self.active_intents and self.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            # This might indicate the task logic in on_intent_outcome needs to set a final status
            # or that it's a type of task that doesn't use intents after a certain point.
            # For GatherAndDeliver, it should always end up in COMPLETED or FAILED via the above paths.
            print(f"Task {self.task_id} has no active intents but not in terminal state. Current step: {self._current_step_key}, Status: {self.status.name}")


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
        if not self.target_storage_ref: # Should have been caught
            self.status = TaskStatus.FAILED
            self.error_message = "target_storage_ref is None in prepare for DeliverWheatToMillTask."
            return False
        
        # Find a walkable tile adjacent to the storage point for pickup
        interaction_pos_storage = agent.grid.find_walkable_adjacent_tile(self.target_storage_ref.position) # type: ignore
        if not interaction_pos_storage:
            self.error_message = f"Could not find walkable adjacent tile for storage {self.target_storage_ref.position}."
            # Release reservations if interaction spot not found
            if self.target_storage_ref and self.reserved_at_storage_for_pickup_quantity > 0:
                self.target_storage_ref.release_pickup_reservation(self.task_id, self.resource_to_retrieve, self.reserved_at_storage_for_pickup_quantity) # type: ignore
                self.reserved_at_storage_for_pickup_quantity = 0
            self.status = TaskStatus.FAILED
            return False

        move_to_storage_intent = MoveIntent(interaction_pos_storage, task_id=self.task_id)
        self._submit_intent_to_agent(agent, move_to_storage_intent)

        self.status = TaskStatus.IN_PROGRESS_MOVE_TO_STORAGE
        self._current_step_key = "move_to_storage"
        
        print(f"Task {self.task_id} (DeliverWheatToMill) PREPARED for agent {agent.id}. Submitted MoveIntent to Storage: {self.target_storage_ref.position}. Reserved Pickup Qty: {self.reserved_at_storage_for_pickup_quantity}")
        return True

    # execute_step is no longer needed
    # def execute_step(self, agent: 'Agent', dt: float, resource_manager: 'ResourceManager') -> TaskStatus:
    #     self._update_timestamp()
    #     return self.status

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

    def on_intent_outcome(self, agent: 'Agent', intent_id: uuid.UUID, intent_status: IntentStatus, resource_manager: 'ResourceManager'):
        self._update_timestamp()
        original_intent_description = "Unknown Intent (DeliverWheat)"
        # Try to get original intent description if agent still holds it, for logging
        current_agent_intent = agent.current_intent
        if current_agent_intent and current_agent_intent.intent_id == intent_id:
            original_intent_description = current_agent_intent.get_description()

        print(f"Task {self.task_id} (DeliverWheatToMillTask) received outcome for intent {intent_id} ({original_intent_description}): {intent_status.name}")
        
        if intent_id in self.active_intents:
            self.active_intents.remove(intent_id)
        else:
            print(f"Warning: Task {self.task_id} (DeliverWheatToMillTask) received outcome for an untracked intent {intent_id}.")

        if self.status in [TaskStatus.FAILED, TaskStatus.COMPLETED, TaskStatus.CANCELLED]:
            print(f"Task {self.task_id} (DeliverWheatToMillTask) is already terminal ({self.status.name}). Ignoring outcome for {intent_id}.")
            return

        if intent_status == IntentStatus.FAILED:
            self.status = TaskStatus.FAILED
            err_msg = "N/A"
            if current_agent_intent and current_agent_intent.intent_id == intent_id and current_agent_intent.error_message:
                err_msg = current_agent_intent.error_message
            self.error_message = f"Intent {intent_id} ({original_intent_description}) failed for DeliverWheatToMillTask. Agent Error: {err_msg}"
            print(f"Task {self.task_id} FAILED due to failed intent {intent_id}. Error: {self.error_message}")
            return

        if intent_status == IntentStatus.CANCELLED:
            self.status = TaskStatus.FAILED
            self.error_message = f"Intent {intent_id} ({original_intent_description}) was cancelled for DeliverWheatToMillTask."
            print(f"Task {self.task_id} FAILED due to cancelled intent {intent_id}.")
            return

        # --- Intent COMPLETED Logic for DeliverWheatToMillTask ---
        if intent_status == IntentStatus.COMPLETED:
            if not self.target_storage_ref or not self.target_processor_ref:
                 self.status = TaskStatus.FAILED; self.error_message = "Target refs are None in on_intent_outcome."; return

            if self._current_step_key == "move_to_storage":
                print(f"Task {self.task_id}: MoveIntent to storage completed.")
                self._current_step_key = "collect_from_storage"
                self.status = TaskStatus.IN_PROGRESS_COLLECTING_FROM_STORAGE
                collection_time = getattr(agent.config, "DEFAULT_COLLECTION_TIME_FROM_STORAGE", agent.config.DEFAULT_GATHERING_TIME)
                collect_intent = InteractAtTargetIntent(
                    target_id=self.target_storage_ref.id, # type: ignore
                    interaction_type="COLLECT_FROM_STORAGE",
                    duration=collection_time,
                    task_id=self.task_id
                )
                self._submit_intent_to_agent(agent, collect_intent)

            elif self._current_step_key == "collect_from_storage":
                print(f"Task {self.task_id}: InteractAtTargetIntent (COLLECT_FROM_STORAGE) completed.")
                can_carry_more = agent.inventory_capacity - agent.current_inventory.get('quantity', 0)
                amount_to_attempt_collect = min(
                    can_carry_more,
                    self.reserved_at_storage_for_pickup_quantity - self.quantity_retrieved
                )
                if amount_to_attempt_collect > 0:
                    collected_qty = self.target_storage_ref.collect_reserved_pickup(
                        self.task_id, self.resource_to_retrieve, amount_to_attempt_collect
                    )
                    if collected_qty > 0:
                        if agent.current_inventory.get('resource_type') is None or agent.current_inventory.get('resource_type') == self.resource_to_retrieve:
                            agent.current_inventory['resource_type'] = self.resource_to_retrieve
                            agent.current_inventory['quantity'] = agent.current_inventory.get('quantity', 0) + collected_qty # type: ignore
                            self.quantity_retrieved += collected_qty
                            print(f"Task {self.task_id}: Agent collected {collected_qty} {self.resource_to_retrieve.name}. Agent inv: {agent.current_inventory['quantity']}")
                        else:
                            self.status = TaskStatus.FAILED; self.error_message = "Agent inv type mismatch during collect from storage."; return
                    elif collected_qty == 0: # Failed to collect anything despite trying
                         self.status = TaskStatus.FAILED; self.error_message = f"Failed to collect reserved {self.resource_to_retrieve.name} from storage."; return
                
                if self.quantity_retrieved > 0:
                    self._current_step_key = "move_to_mill"
                    self.status = TaskStatus.IN_PROGRESS_MOVE_TO_PROCESSOR
                    
                    # Find a walkable tile adjacent to the mill
                    interaction_pos_mill = agent.grid.find_walkable_adjacent_tile(self.target_processor_ref.position) # type: ignore
                    if not interaction_pos_mill:
                        self.error_message = f"Could not find walkable adjacent tile for mill {self.target_processor_ref.position}."
                        self.status = TaskStatus.FAILED
                        # Agent has items, but can't path to mill. This is a task failure.
                        return

                    move_to_mill_intent = MoveIntent(interaction_pos_mill, task_id=self.task_id)
                    self._submit_intent_to_agent(agent, move_to_mill_intent)
                else: # Nothing retrieved, or reservation exhausted before getting anything
                    self.status = TaskStatus.FAILED; self.error_message = "No items retrieved from storage, or reservation issue."; return

            elif self._current_step_key == "move_to_mill":
                print(f"Task {self.task_id}: MoveIntent to mill completed.")
                self._current_step_key = "deliver_to_mill"
                self.status = TaskStatus.IN_PROGRESS_DELIVERING_TO_PROCESSOR
                deliver_intent = InteractAtTargetIntent(
                    target_id=self.target_processor_ref.id, # type: ignore
                    interaction_type="DELIVER_TO_PROCESSOR",
                    duration=agent.config.DEFAULT_DELIVERY_TIME,
                    task_id=self.task_id
                )
                self._submit_intent_to_agent(agent, deliver_intent)

            elif self._current_step_key == "deliver_to_mill":
                print(f"Task {self.task_id}: InteractAtTargetIntent (DELIVER_TO_PROCESSOR) completed.")
                amount_to_deliver = agent.current_inventory.get('quantity', 0)
                if amount_to_deliver > 0 and agent.current_inventory.get('resource_type') == self.resource_to_retrieve:
                    delivered_qty = self.target_processor_ref.receive(self.resource_to_retrieve, amount_to_deliver) # type: ignore
                    if delivered_qty > 0:
                        agent.current_inventory['quantity'] = agent.current_inventory.get('quantity', 0) - delivered_qty # type: ignore
                        self.quantity_delivered_to_processor += delivered_qty
                        print(f"Task {self.task_id}: Agent delivered {delivered_qty} to mill. Task delivered: {self.quantity_delivered_to_processor}. Agent inv: {agent.current_inventory['quantity']}")
                        if agent.current_inventory.get('quantity', 0) == 0:
                            agent.current_inventory['resource_type'] = None
                        
                        if self.quantity_delivered_to_processor >= self.quantity_retrieved:
                            self.status = TaskStatus.COMPLETED
                            print(f"Task {self.task_id} (DeliverWheatToMillTask) COMPLETED.")
                        elif agent.current_inventory.get('quantity', 0) == 0 : # Delivered all it had
                             self.status = TaskStatus.COMPLETED # Assuming one trip completes the task's goal for this specific load
                             print(f"Task {self.task_id} (DeliverWheatToMillTask) COMPLETED (agent empty).")
                    else:
                        self.status = TaskStatus.FAILED; self.error_message = "Mill failed to receive items."; return
                elif amount_to_deliver == 0:
                     self.status = TaskStatus.FAILED; self.error_message = "Agent arrived at mill with no items to deliver."; return
            else:
                print(f"Warning: Task {self.task_id} (DeliverWheatToMillTask) completed intent {intent_id} in unhandled step: {self._current_step_key}")

        if not self.active_intents and self.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            print(f"Task {self.task_id} (DeliverWheatToMillTask) has no active intents but not in terminal state. Step: {self._current_step_key}, Status: {self.status.name}")