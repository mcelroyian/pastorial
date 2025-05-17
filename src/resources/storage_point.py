import pygame
import uuid # Added for task_id in reservations
from typing import List, Dict, Optional

# Assuming ResourceType is defined in resource_types.py
from .resource_types import ResourceType

class StoragePoint:
    """Represents a location where agents can drop off collected resources, with reservation capabilities."""

    def __init__(self,
                 position: pygame.math.Vector2,
                 overall_capacity: int,
                 accepted_resource_types: Optional[List[ResourceType]] = None):
        """
        Initializes a StoragePoint.

        Args:
            position (pygame.math.Vector2): The grid coordinates of the storage point.
            overall_capacity (int): The maximum total quantity of all resources this point can hold.
            accepted_resource_types (Optional[List[ResourceType]]): A list of resource types
                                     this storage point accepts. If None, accepts all types.
        """
        self.position = position
        self.overall_capacity = overall_capacity
        self.accepted_resource_types = accepted_resource_types
        self.stored_resources: Dict[ResourceType, int] = {}
        self.reservations: Dict[uuid.UUID, int] = {} # task_id -> reserved_quantity

    def get_current_load(self) -> int:
        """Returns the total quantity of all resources currently physically stored."""
        return sum(self.stored_resources.values())

    def get_total_reserved_quantity(self) -> int:
        """Returns the total quantity of all resources currently reserved."""
        return sum(self.reservations.values())

    def get_available_capacity_for_reservation(self) -> int:
        """Calculates space available for new reservations."""
        return self.overall_capacity - self.get_current_load() - self.get_total_reserved_quantity()

    def can_accept(self, resource_type: ResourceType, quantity: int, for_reservation: bool = False) -> bool:
        """
        Checks if the storage point can accept a given quantity of a resource type.
        If for_reservation is True, checks against capacity available for new reservations.
        Otherwise, checks against overall capacity minus existing reservations (for direct non-task additions).
        """
        if self.accepted_resource_types is not None and resource_type not in self.accepted_resource_types:
            return False
        
        if for_reservation:
            if quantity > self.get_available_capacity_for_reservation():
                return False
        else: # Checking for a direct, non-reserved addition
            # A direct addition must fit into space not physically filled and not already reserved by others.
            if self.get_current_load() + quantity > self.overall_capacity - self.get_total_reserved_quantity():
                return False
        return True

    def reserve_space(self, task_id: uuid.UUID, resource_type: ResourceType, quantity: int) -> int:
        """
        Attempts to reserve space for a given task.

        Args:
            task_id (uuid.UUID): The ID of the task making the reservation.
            resource_type (ResourceType): The type of resource to reserve space for.
            quantity (int): The amount of space to reserve.

        Returns:
            int: The actual quantity of space reserved. Can be less than requested if
                 not enough space is available or 0 if type not accepted or no space.
        """
        if task_id in self.reservations: # Task already has a reservation, should modify or release first
            print(f"Warning: Task {task_id} attempting to reserve space again. Current reservation: {self.reservations[task_id]}")
            # Potentially allow modification, but for now, let's assume new reservation means prior one should be handled.
            # Or, this could be an addition to an existing reservation. For simplicity, let's make it overwrite/add.
            # self.reservations[task_id] += quantity_to_reserve ... (this needs careful thought)
            # For now, let's assume a task makes one reservation request that should be sufficient.
            # If a task needs to change its reservation, it should release and re-reserve.
            # This simplifies logic. If this call happens, it's likely an error in task logic or a new reservation.
            # Let's assume it's a new reservation attempt.
            pass # Allow re-evaluation if needed.

        if not self.can_accept(resource_type, quantity, for_reservation=True):
            # Try to reserve as much as possible
            available_for_res = self.get_available_capacity_for_reservation()
            if self.accepted_resource_types is not None and resource_type not in self.accepted_resource_types:
                 return 0 # Cannot accept this type at all
            
            quantity_to_reserve = min(quantity, available_for_res)
            if quantity_to_reserve <= 0:
                return 0
        else:
            quantity_to_reserve = quantity
        
        # Add to existing reservation for the task or create a new one
        self.reservations[task_id] = self.reservations.get(task_id, 0) + quantity_to_reserve
        print(f"Storage at {self.position} reserved {quantity_to_reserve} for task {task_id}. Total reserved: {self.get_total_reserved_quantity()}")
        return quantity_to_reserve

    def release_reservation(self, task_id: uuid.UUID, quantity_to_release: Optional[int] = None) -> bool:
        """
        Releases a reservation made by a task.

        Args:
            task_id (uuid.UUID): The ID of the task whose reservation is to be released.
            quantity_to_release (Optional[int]): The amount of reservation to release.
                                                 If None, releases the entire reservation for the task.

        Returns:
            bool: True if the reservation was found and released/reduced, False otherwise.
        """
        if task_id not in self.reservations:
            return False
        
        if quantity_to_release is None or quantity_to_release >= self.reservations[task_id]:
            released_amount = self.reservations.pop(task_id)
            print(f"Storage at {self.position} fully released reservation of {released_amount} for task {task_id}.")
        else:
            self.reservations[task_id] -= quantity_to_release
            print(f"Storage at {self.position} reduced reservation by {quantity_to_release} for task {task_id}. Remaining: {self.reservations[task_id]}")
        return True

    def commit_reservation_to_storage(self, task_id: uuid.UUID, resource_type: ResourceType, quantity_to_add: int) -> int:
        """
        Commits a previously reserved quantity of a resource to actual storage.
        This will decrease the reservation and increase stored_resources.

        Args:
            task_id (uuid.UUID): The task ID that holds the reservation.
            resource_type (ResourceType): The type of resource being added.
            quantity_to_add (int): The quantity to add from the reservation.

        Returns:
            int: The actual quantity added to storage.
        """
        if task_id not in self.reservations:
            print(f"Error: Task {task_id} has no reservation at {self.position} to commit.")
            return 0 # No reservation for this task

        reserved_for_task = self.reservations[task_id]
        if quantity_to_add > reserved_for_task:
            print(f"Warning: Task {task_id} trying to commit {quantity_to_add} but only {reserved_for_task} reserved. Committing max reserved.")
            quantity_to_add = reserved_for_task # Cannot add more than reserved by this task

        # Actual addition to storage - this uses the existing add_resource logic but bypasses some checks
        # as the space was already accounted for by the reservation.
        # However, add_resource itself checks overall_capacity.
        # We need a way to ensure this addition is "safe" because it was reserved.

        # Simplified: directly add to stored_resources and adjust reservation
        # Check if type is accepted (should have been checked at reservation time too)
        if self.accepted_resource_types is not None and resource_type not in self.accepted_resource_types:
            print(f"Error: Task {task_id} trying to commit unaccepted type {resource_type.name} at {self.position}.")
            return 0 # Should not happen if reservation was done correctly

        # Check if physical space is available (current_load + quantity_to_add <= overall_capacity)
        # This check is vital because reservations are conceptual; physical space is paramount.
        if self.get_current_load() + quantity_to_add > self.overall_capacity:
            # This indicates a problem: reservation allowed more than physical capacity.
            # Or, other non-reserved items filled up space.
            # For now, only add what physically fits.
            can_physically_add = self.overall_capacity - self.get_current_load()
            if quantity_to_add > can_physically_add:
                 print(f"Critical Warning: Task {task_id} at {self.position}: Physical space ({can_physically_add}) less than committed quantity ({quantity_to_add}) from reservation. Data integrity issue or race condition?")
                 quantity_to_add = can_physically_add
            
            if quantity_to_add <= 0:
                return 0


        if quantity_to_add > 0:
            current_amount = self.stored_resources.get(resource_type, 0)
            self.stored_resources[resource_type] = current_amount + quantity_to_add
            
            # Reduce or remove reservation
            if quantity_to_add >= reserved_for_task:
                self.reservations.pop(task_id)
            else:
                self.reservations[task_id] -= quantity_to_add
            
            print(f"Storage at {self.position} committed {quantity_to_add} of {resource_type.name} from task {task_id}. Stored: {self.stored_resources.get(resource_type, 0)}, Remaining Res for task: {self.reservations.get(task_id, 0)}")
            return quantity_to_add
        return 0


    def add_resource(self, resource_type: ResourceType, quantity: int) -> int:
        """
        Adds a quantity of a specific resource type to the storage.
        This is for direct additions, not via reservations.
        It must respect space not already reserved by other tasks.

        Args:
            resource_type (ResourceType): The type of resource to add.
            quantity (int): The amount of resource to add.

        Returns:
            int: The actual quantity of the resource added (might be less than requested
                 if capacity is exceeded or type not accepted).
        """
        # Use the modified can_accept for non-reservation additions
        if not self.can_accept(resource_type, quantity, for_reservation=False):
            if self.accepted_resource_types is not None and resource_type not in self.accepted_resource_types:
                return 0

            # Calculate available capacity considering other reservations
            available_for_direct_add = self.overall_capacity - self.get_current_load() - self.get_total_reserved_quantity()
            quantity_to_add = min(quantity, available_for_direct_add)

            if quantity_to_add <= 0:
                return 0
        else:
            quantity_to_add = quantity
        
        if quantity_to_add > 0:
            current_amount = self.stored_resources.get(resource_type, 0)
            self.stored_resources[resource_type] = current_amount + quantity_to_add
            print(f"Storage at {self.position} (direct add) received {quantity_to_add} of {resource_type.name}. Total stored: {self.stored_resources.get(resource_type, 0)}")
        return quantity_to_add

    def draw(self, screen: pygame.Surface, grid):
        """Draws the storage point on the screen."""
        screen_pos = grid.grid_to_screen(self.position)
        color = (128, 128, 128) # Grey for storage
        radius = grid.cell_width // 2
        pygame.draw.rect(screen, color, (screen_pos[0] - radius, screen_pos[1] - radius, grid.cell_width, grid.cell_height))
        # Optionally, draw stored resource counts or indicators