import uuid
import time
from abc import ABC, abstractmethod
from typing import Optional, List, Callable, TYPE_CHECKING

from .task_types import TaskType, TaskStatus
from ..resources.resource_types import ResourceType
from ..agents.intents import Intent, IntentStatus, MoveIntent, InteractAtTargetIntent
from ..core import config

if TYPE_CHECKING:
    from ..agents.agent import Agent
    from ..resources.manager import ResourceManager
    from ..resources.node import ResourceNode
    from ..resources.storage_point import StoragePoint
    from ..resources.processing import ProcessingStation
    from ..factions.context import FactionContext


# ---------------------------------------------------------------------------
# Utility scoring — Plan 4 Task 1
# ---------------------------------------------------------------------------

# ResourceType -> (base_value, target_stock) for GatherAndDeliverTask.compute_score.
# Only resources with a meaningful global stock target live here; anything else (e.g. WATER,
# reached only via the station-provisioning path) falls back to a flat provisioning urgency.
_GATHER_SCORE_PARAMS = {
    ResourceType.BERRY: (config.UTILITY_BASE_VALUE_BERRY, config.MIN_BERRY_STOCK_LEVEL),
    ResourceType.WHEAT: (config.UTILITY_BASE_VALUE_WHEAT, config.MIN_WHEAT_STOCK_LEVEL),
}


def _nearest_distance_cost(home_centroid, positions_and_pressure, weight: float,
                            contention_weight: float = 0.0) -> float:
    """Coarse generation-time distance approximation: no agent is assigned to a task yet at
    scoring time, so use the faction's home-region centroid as a stand-in anchor.

    positions_and_pressure is an iterable of (position, contention_pressure) pairs; pressure
    is 0.0 for anything that can't be contested (e.g. mills — contention_weight defaults to
    0.0 so those call sites are unaffected). Picking the min over distance+contention combined
    means a contested-but-close candidate can lose to a farther-but-uncontested one — this is
    "nodes in contested areas score slightly lower, remote/safe nodes gain" (Plan 4 Task 2),
    with no separate boost-safe-nodes logic needed."""
    positions_and_pressure = list(positions_and_pressure)
    if not positions_and_pressure:
        return 0.0
    return min(
        weight * (p - home_centroid).length() + contention_weight * pressure
        for p, pressure in positions_and_pressure
    )


# ---------------------------------------------------------------------------
# TaskStep abstraction
# ---------------------------------------------------------------------------

class TaskStep(ABC):
    @abstractmethod
    def create_intent(self, agent: 'Agent', task: 'Task') -> Optional[Intent]:
        """Return the intent for this step, or None to fail the task."""
        pass

    @abstractmethod
    def on_success(self, agent: 'Agent', task: 'Task', resource_manager: 'ResourceManager') -> None:
        """Side effects to apply once the intent completes successfully."""
        pass


class MoveToStep(TaskStep):
    """Move to a position returned by pos_provider(). Fails the task if pos is None."""

    def __init__(self, pos_provider: Callable):
        self._pos_provider = pos_provider

    def create_intent(self, agent: 'Agent', task: 'Task') -> Optional[Intent]:
        pos = self._pos_provider()
        if pos is None:
            task.status = TaskStatus.FAILED
            task.error_message = "MoveToStep: no valid position available"
            return None
        return MoveIntent(pos, task_id=task.task_id)

    def on_success(self, agent: 'Agent', task: 'Task', resource_manager: 'ResourceManager') -> None:
        pass


class InteractStep(TaskStep):
    """Interact at a target for a given duration, then call on_complete."""

    def __init__(
        self,
        target_id_provider: Callable,        # () -> uuid.UUID
        interaction_type: str,
        duration_provider: Callable,          # (agent, task) -> float
        on_complete: Optional[Callable] = None,  # (agent, task, resource_manager) -> None
    ):
        self._target_id_provider = target_id_provider
        self._interaction_type = interaction_type
        self._duration_provider = duration_provider
        self._on_complete = on_complete

    def create_intent(self, agent: 'Agent', task: 'Task') -> Optional[Intent]:
        return InteractAtTargetIntent(
            target_id=self._target_id_provider(),
            interaction_type=self._interaction_type,
            duration=self._duration_provider(agent, task),
            task_id=task.task_id,
        )

    def on_success(self, agent: 'Agent', task: 'Task', resource_manager: 'ResourceManager') -> None:
        if self._on_complete is not None:
            self._on_complete(agent, task, resource_manager)


# ---------------------------------------------------------------------------
# Task base class
# ---------------------------------------------------------------------------

class Task(ABC):
    def __init__(self, task_type: TaskType, priority: int):
        self.task_id: uuid.UUID = uuid.uuid4()
        self.task_type: TaskType = task_type
        self.status: TaskStatus = TaskStatus.PENDING
        self.priority: int = priority
        self.agent_id: Optional[uuid.UUID] = None
        self.creation_time: float = time.time()  # wall-clock, logging only
        self.last_update_time: float = self.creation_time  # wall-clock, logging only
        self.error_message: Optional[str] = None
        self.active_intents: List[uuid.UUID] = []
        self.steps: List[TaskStep] = []
        self.current_step_index: int = 0

    @abstractmethod
    def prepare(self, agent: 'Agent', resource_manager: 'ResourceManager') -> bool:
        pass

    @abstractmethod
    def cleanup(self, agent: 'Agent', resource_manager: 'ResourceManager', success: bool):
        pass

    def compute_score(self, faction_ctx: 'FactionContext', resource_manager: 'ResourceManager') -> float:
        """Utility score for job-board ordering (Plan 4 Task 1). Default: static priority as
        a float — legacy fallback for task types not migrated to scoring (e.g. PatrolTask)."""
        return float(self.priority)

    def get_description(self) -> str:
        return f"{self.task_type.name} (Status: {self.status.name})"

    def _update_timestamp(self):
        self.last_update_time = time.time()  # wall-clock, logging only

    def _submit_intent_to_agent(self, agent: 'Agent', intent: Intent):
        if hasattr(agent, 'submit_intent') and callable(agent.submit_intent):
            agent.submit_intent(intent)
            self.active_intents.append(intent.intent_id)
        else:
            self.status = TaskStatus.FAILED
            self.error_message = "Agent does not support intent submission."

    def _submit_next_step(self, agent: 'Agent', resource_manager: 'ResourceManager') -> bool:
        step = self.steps[self.current_step_index]
        intent = step.create_intent(agent, self)
        if intent is None:
            return False  # create_intent already set status/error_message
        self._submit_intent_to_agent(agent, intent)
        return self.status != TaskStatus.FAILED

    def on_intent_outcome(
        self,
        agent: 'Agent',
        intent_id: uuid.UUID,
        intent_status: IntentStatus,
        resource_manager: 'ResourceManager',
    ):
        self._update_timestamp()
        if intent_id in self.active_intents:
            self.active_intents.remove(intent_id)

        if self.status in (TaskStatus.FAILED, TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            return

        if intent_status in (IntentStatus.FAILED, IntentStatus.CANCELLED):
            self.status = TaskStatus.FAILED
            self.error_message = f"Intent {intent_id} {intent_status.name.lower()}"
            return

        if intent_status == IntentStatus.COMPLETED:
            step = self.steps[self.current_step_index]
            step.on_success(agent, self, resource_manager)
            if self.status in (TaskStatus.FAILED, TaskStatus.COMPLETED, TaskStatus.CANCELLED):
                return
            self.current_step_index += 1
            if self.current_step_index >= len(self.steps):
                self.status = TaskStatus.COMPLETED
            else:
                self._submit_next_step(agent, resource_manager)


# ---------------------------------------------------------------------------
# GatherAndDeliverTask
# ---------------------------------------------------------------------------

class GatherAndDeliverTask(Task):
    """Gather a resource from a node and deliver it to a storage point or processing station."""

    def __init__(
        self,
        priority: int,
        resource_type_to_gather: ResourceType,
        quantity_to_gather: int,
        target_resource_node_id: Optional[uuid.UUID] = None,
        target_dropoff_id: Optional[uuid.UUID] = None,
    ):
        super().__init__(TaskType.GATHER_AND_DELIVER, priority)
        self.resource_type_to_gather: ResourceType = resource_type_to_gather
        self.quantity_to_gather: int = quantity_to_gather
        self.target_resource_node_ref = None
        self.target_dropoff_ref = None
        self.quantity_gathered: int = 0
        self.quantity_delivered: int = 0
        self.reserved_at_node: bool = False
        self.reserved_at_dropoff_quantity: int = 0

    def prepare(self, agent: 'Agent', resource_manager: 'ResourceManager') -> bool:
        self.target_resource_node_ref = None
        self.target_dropoff_ref = None
        self.reserved_at_node = False
        self.reserved_at_dropoff_quantity = 0
        self.error_message = None
        self._update_timestamp()
        self.status = TaskStatus.PREPARING

        faction_id = getattr(agent, 'owner_faction_id', None)

        # 1. Claim a resource node (wild nodes are fair game for any faction)
        events = getattr(resource_manager, 'events', None)
        checked_preferred_candidate = False
        for node in sorted(
            resource_manager.get_nodes_by_type(self.resource_type_to_gather),
            key=lambda n: (n.position - agent.position).length_squared(),
        ):
            if node.current_quantity < 1:
                continue
            if node.claim(agent.id, self.task_id, faction_id=faction_id):
                self.target_resource_node_ref = node
                self.reserved_at_node = True
                break
            # Only the agent's nearest viable candidate counts as a contention signal — "my
            # preferred spot was taken by the enemy." Falling through to a second-choice node
            # further down the sorted list is normal, not a hostility precursor (Plan 4 Task 2).
            if not checked_preferred_candidate:
                checked_preferred_candidate = True
                if (node.claimed_by_faction_id is not None
                        and faction_id is not None
                        and node.claimed_by_faction_id != faction_id):
                    node.add_contention(config.CONTENTION_BUMP_PER_DENIAL)
                    if events is not None:
                        events.record(
                            "claim_contention",
                            faction_id=faction_id,
                            other_faction_id=node.claimed_by_faction_id,
                            position=node.position,
                            resource_type=self.resource_type_to_gather.name,
                        )

        if not self.target_resource_node_ref:
            self.error_message = f"No available node for {self.resource_type_to_gather.name}."
            self.status = TaskStatus.FAILED
            return False

        qty = min(
            self.quantity_to_gather,
            agent.inventory_capacity,
            self.target_resource_node_ref.current_quantity,
        )

        # 2. Reserve space at dropoff — own-faction storage/stations only
        own_dropoffs = [
            d for d in resource_manager.storage_points + resource_manager.processing_stations
            if getattr(d, 'owner_faction_id', None) is None or getattr(d, 'owner_faction_id', None) == faction_id
        ]
        for dropoff in sorted(own_dropoffs, key=lambda d: (d.position - agent.position).length_squared()):
            if hasattr(dropoff, 'can_accept_input') and dropoff.can_accept_input(
                self.resource_type_to_gather, 1
            ):
                self.target_dropoff_ref = dropoff
                self.reserved_at_dropoff_quantity = qty
                break
            elif hasattr(dropoff, 'reserve_space'):
                reserved = dropoff.reserve_space(self.task_id, self.resource_type_to_gather, qty,
                                                  faction_id=faction_id)
                if reserved > 0:
                    self.target_dropoff_ref = dropoff
                    self.reserved_at_dropoff_quantity = reserved
                    break

        if not self.target_dropoff_ref or self.reserved_at_dropoff_quantity == 0:
            self.target_resource_node_ref.release(agent.id, self.task_id)
            self.reserved_at_node = False
            self.error_message = f"No dropoff space for {self.resource_type_to_gather.name}."
            self.status = TaskStatus.FAILED
            return False

        # Validate first move target before committing to the step list
        if not agent.grid.find_walkable_adjacent_tile(self.target_resource_node_ref.position):
            self.target_resource_node_ref.release(agent.id, self.task_id)
            self.reserved_at_node = False
            self.target_dropoff_ref.release_reservation(self.task_id, self.reserved_at_dropoff_quantity)
            self.reserved_at_dropoff_quantity = 0
            self.error_message = "No walkable tile adjacent to resource node."
            self.status = TaskStatus.FAILED
            return False

        node = self.target_resource_node_ref
        dropoff = self.target_dropoff_ref
        grid = agent.grid

        self.steps = [
            MoveToStep(lambda: grid.find_walkable_adjacent_tile(node.position)),
            InteractStep(
                lambda: node.id,
                "GATHER_RESOURCE",
                lambda a, t: a.config.DEFAULT_GATHERING_TIME,
                self._on_gather_complete,
            ),
            MoveToStep(lambda: grid.find_walkable_adjacent_tile(dropoff.position)),
            InteractStep(
                lambda: dropoff.id,
                "DELIVER_RESOURCE",
                lambda a, t: a.config.DEFAULT_DELIVERY_TIME,
                self._on_deliver_complete,
            ),
        ]
        self.current_step_index = 0
        self.status = TaskStatus.IN_PROGRESS
        self._submit_next_step(agent, resource_manager)
        return self.status != TaskStatus.FAILED

    def _on_gather_complete(self, agent, task, resource_manager):
        node = self.target_resource_node_ref
        can_carry = agent.inventory_capacity - agent.current_inventory.get('quantity', 0)
        amount = min(
            can_carry,
            self.reserved_at_dropoff_quantity,
            self.quantity_to_gather - self.quantity_gathered,
        )
        if amount > 0:
            gathered = node.collect_resource(amount)
            if gathered > 0:
                inv_type = agent.current_inventory.get('resource_type')
                if inv_type is not None and inv_type != self.resource_type_to_gather:
                    self.status = TaskStatus.FAILED
                    self.error_message = "Inventory type mismatch during gather."
                    return
                agent.current_inventory['resource_type'] = self.resource_type_to_gather
                agent.current_inventory['quantity'] = (
                    agent.current_inventory.get('quantity', 0) + gathered
                )
                self.quantity_gathered += gathered
        if self.reserved_at_node and (
            self.quantity_gathered >= self.quantity_to_gather or node.current_quantity < 1
        ):
            node.release(agent.id, self.task_id)
            self.reserved_at_node = False

    def _on_deliver_complete(self, agent, task, resource_manager):
        amount = agent.current_inventory.get('quantity', 0)
        if amount <= 0 or agent.current_inventory.get('resource_type') != self.resource_type_to_gather:
            return  # Nothing to deliver; task completes normally
        dropoff = self.target_dropoff_ref
        if hasattr(dropoff, 'commit_reservation_to_storage'):
            delivered = dropoff.commit_reservation_to_storage(
                self.task_id, self.resource_type_to_gather, amount
            )
        elif hasattr(dropoff, 'receive'):
            delivered = dropoff.receive(self.resource_type_to_gather, amount)
        else:
            delivered = 0
        if delivered > 0:
            agent.current_inventory['quantity'] = (
                agent.current_inventory.get('quantity', 0) - delivered
            )
            self.quantity_delivered += delivered
            self.reserved_at_dropoff_quantity -= delivered
            if agent.current_inventory.get('quantity', 0) == 0:
                agent.current_inventory['resource_type'] = None
        else:
            self.status = TaskStatus.FAILED
            self.error_message = "Failed to commit delivery to storage."

    def compute_score(self, faction_ctx: 'FactionContext', resource_manager: 'ResourceManager') -> float:
        rt = self.resource_type_to_gather
        if rt in _GATHER_SCORE_PARAMS:
            base_value, target = _GATHER_SCORE_PARAMS[rt]
            stock_ratio = faction_ctx.stock.get(rt, 0) / max(target, 1)
        else:
            # Station-provisioning fallback (e.g. WATER->Bakery): no meaningful global stock
            # target exists for this resource type. Task creation is already gated by
            # needed_qty > active_delivery_qty upstream in _generate_tasks_if_needed — this
            # task only exists because a station needs it — so score at flat urgency.
            base_value, stock_ratio = config.UTILITY_BASE_VALUE_PROVISION, 0.0
        urgency = max(0.0, 1.0 - stock_ratio) ** config.UTILITY_URGENCY_EXPONENT
        nodes_and_pressure = [
            (n.position, n.contention_pressure) for n in resource_manager.get_nodes_by_type(rt)
        ]
        distance_cost = _nearest_distance_cost(
            faction_ctx.home_centroid, nodes_and_pressure,
            config.UTILITY_DISTANCE_WEIGHT, config.UTILITY_CONTENTION_WEIGHT,
        )
        risk_cost = 0.0  # Task 1: no hostility exists yet. Task 3/4 wire real risk here.
        return base_value * urgency - distance_cost - risk_cost

    def cleanup(self, agent: 'Agent', resource_manager: 'ResourceManager', success: bool):
        self._update_timestamp()
        if self.target_resource_node_ref and self.reserved_at_node:
            self.target_resource_node_ref.release(agent.id, self.task_id)
            self.reserved_at_node = False
        if self.target_dropoff_ref and self.reserved_at_dropoff_quantity > 0:
            # Processing stations don't have a reservation system — only storage points do
            if hasattr(self.target_dropoff_ref, 'release_reservation'):
                self.target_dropoff_ref.release_reservation(self.task_id, self.reserved_at_dropoff_quantity)
            self.reserved_at_dropoff_quantity = 0

    def get_description(self) -> str:
        node = self.target_resource_node_ref
        dropoff = self.target_dropoff_ref
        idx = self.current_step_index
        if idx == 0 and node:
            return f"Moving to {self.resource_type_to_gather.name} at {node.position}"
        if idx == 1 and node:
            return f"Gathering {self.resource_type_to_gather.name} at {node.position}"
        if idx == 2 and dropoff:
            return f"Moving to dropoff at {dropoff.position}"
        if idx == 3 and dropoff:
            return f"Delivering {self.resource_type_to_gather.name} to {dropoff.position}"
        return f"Gather/Deliver {self.resource_type_to_gather.name} ({self.status.name})"


# ---------------------------------------------------------------------------
# DeliverWheatToMillTask
# ---------------------------------------------------------------------------

class DeliverWheatToMillTask(Task):
    """Collect wheat from storage and deliver it to a mill for processing."""

    def __init__(
        self,
        priority: int,
        quantity_to_retrieve: int,
        target_storage_id: Optional[uuid.UUID] = None,
        target_processor_id: Optional[uuid.UUID] = None,
    ):
        super().__init__(TaskType.PROCESS_RESOURCE, priority)
        self.resource_to_retrieve: ResourceType = ResourceType.WHEAT
        self.quantity_to_retrieve: int = quantity_to_retrieve
        self.target_storage_ref = None
        self.target_processor_ref = None
        self.quantity_retrieved: int = 0
        self.quantity_delivered_to_processor: int = 0
        self.reserved_at_storage_for_pickup_quantity: int = 0

    def prepare(self, agent: 'Agent', resource_manager: 'ResourceManager') -> bool:
        from ..resources.mill import Mill

        self._update_timestamp()
        self.status = TaskStatus.PREPARING

        faction_id = getattr(agent, 'owner_faction_id', None)

        if agent.current_inventory['quantity'] > 0:
            self.error_message = "Agent inventory not empty."
            self.status = TaskStatus.FAILED
            return False

        qty_to_reserve = min(
            self.quantity_to_retrieve - self.quantity_retrieved,
            agent.inventory_capacity,
        )

        # 1. Reserve wheat at own-faction storage
        own_storage = resource_manager.storage_points_for(faction_id)
        for sp in sorted(
            [s for s in own_storage if s.has_resource(self.resource_to_retrieve, 1)],
            key=lambda s: (s.position - agent.position).length_squared(),
        ):
            reserved = sp.reserve_for_pickup(self.task_id, self.resource_to_retrieve, qty_to_reserve,
                                              faction_id=faction_id)
            if reserved > 0:
                self.target_storage_ref = sp
                self.reserved_at_storage_for_pickup_quantity = reserved
                break

        if not self.target_storage_ref:
            self.error_message = "No wheat in storage for pickup."
            self.status = TaskStatus.FAILED
            return False

        # 2. Find own-faction mill that can accept wheat
        own_stations = resource_manager.stations_for(faction_id)
        mills = sorted(
            [p for p in own_stations
             if isinstance(p, Mill) and p.can_accept_input(self.resource_to_retrieve, 1)],
            key=lambda p: (p.position - self.target_storage_ref.position).length_squared(),
        )
        if mills:
            self.target_processor_ref = mills[0]

        if not self.target_processor_ref:
            self.target_storage_ref.release_pickup_reservation(
                self.task_id, self.resource_to_retrieve,
                self.reserved_at_storage_for_pickup_quantity,
            )
            self.reserved_at_storage_for_pickup_quantity = 0
            self.error_message = "No mill available."
            self.status = TaskStatus.FAILED
            return False

        if not agent.grid.find_walkable_adjacent_tile(self.target_storage_ref.position):
            self.target_storage_ref.release_pickup_reservation(
                self.task_id, self.resource_to_retrieve,
                self.reserved_at_storage_for_pickup_quantity,
            )
            self.reserved_at_storage_for_pickup_quantity = 0
            self.error_message = "No walkable tile adjacent to storage."
            self.status = TaskStatus.FAILED
            return False

        storage = self.target_storage_ref
        mill = self.target_processor_ref
        grid = agent.grid
        collection_time = getattr(
            agent.config, 'DEFAULT_COLLECTION_TIME_FROM_STORAGE',
            agent.config.DEFAULT_GATHERING_TIME,
        )

        self.steps = [
            MoveToStep(lambda: grid.find_walkable_adjacent_tile(storage.position)),
            InteractStep(
                lambda: storage.id,
                "COLLECT_FROM_STORAGE",
                lambda a, t: collection_time,
                self._on_collect_complete,
            ),
            MoveToStep(lambda: grid.find_walkable_adjacent_tile(mill.position)),
            InteractStep(
                lambda: mill.id,
                "DELIVER_TO_PROCESSOR",
                lambda a, t: a.config.DEFAULT_DELIVERY_TIME,
                self._on_deliver_to_mill_complete,
            ),
        ]
        self.current_step_index = 0
        self.status = TaskStatus.IN_PROGRESS
        self._submit_next_step(agent, resource_manager)
        return self.status != TaskStatus.FAILED

    def _on_collect_complete(self, agent, task, resource_manager):
        can_carry = agent.inventory_capacity - agent.current_inventory.get('quantity', 0)
        amount = min(
            can_carry,
            self.reserved_at_storage_for_pickup_quantity - self.quantity_retrieved,
        )
        if amount > 0:
            collected = self.target_storage_ref.collect_reserved_pickup(
                self.task_id, self.resource_to_retrieve, amount
            )
            if collected > 0:
                inv_type = agent.current_inventory.get('resource_type')
                if inv_type is not None and inv_type != self.resource_to_retrieve:
                    self.status = TaskStatus.FAILED
                    self.error_message = "Inventory type mismatch during collect."
                    return
                agent.current_inventory['resource_type'] = self.resource_to_retrieve
                agent.current_inventory['quantity'] = (
                    agent.current_inventory.get('quantity', 0) + collected
                )
                self.quantity_retrieved += collected
            else:
                self.status = TaskStatus.FAILED
                self.error_message = "Failed to collect reserved wheat."
                return
        if self.quantity_retrieved == 0:
            self.status = TaskStatus.FAILED
            self.error_message = "Nothing retrieved from storage."

    def _on_deliver_to_mill_complete(self, agent, task, resource_manager):
        amount = agent.current_inventory.get('quantity', 0)
        if amount == 0:
            self.status = TaskStatus.FAILED
            self.error_message = "Agent arrived at mill with empty inventory."
            return
        if agent.current_inventory.get('resource_type') == self.resource_to_retrieve:
            delivered = self.target_processor_ref.receive(self.resource_to_retrieve, amount)
            if delivered > 0:
                agent.current_inventory['quantity'] = (
                    agent.current_inventory.get('quantity', 0) - delivered
                )
                self.quantity_delivered_to_processor += delivered
                if agent.current_inventory.get('quantity', 0) == 0:
                    agent.current_inventory['resource_type'] = None
            else:
                self.status = TaskStatus.FAILED
                self.error_message = "Mill refused delivery."

    def compute_score(self, faction_ctx: 'FactionContext', resource_manager: 'ResourceManager') -> float:
        # Urgency is keyed off FLOUR_POWDER (not wheat or bread) — matches this task's own
        # generation gate in _generate_tasks_if_needed, and per the doc's framing each task
        # scores by how far below target stock the faction is for its own resource.
        stock_ratio = (faction_ctx.stock.get(ResourceType.FLOUR_POWDER, 0)
                       / max(config.MIN_FLOUR_STOCK_LEVEL, 1))
        urgency = max(0.0, 1.0 - stock_ratio) ** config.UTILITY_URGENCY_EXPONENT
        from ..resources.mill import Mill
        positions = [
            (s.position, 0.0) for s in resource_manager.stations_for(faction_ctx.faction_id)
            if isinstance(s, Mill)
        ]  # mills are always own-faction, never contested — contention_weight stays at default 0.0
        distance_cost = _nearest_distance_cost(faction_ctx.home_centroid, positions,
                                                config.UTILITY_DISTANCE_WEIGHT)
        risk_cost = 0.0  # Task 1: no hostility exists yet. Task 3/4 wire real risk here.
        return config.UTILITY_BASE_VALUE_PROCESS_WHEAT * urgency - distance_cost - risk_cost

    def cleanup(self, agent: 'Agent', resource_manager: 'ResourceManager', success: bool):
        self._update_timestamp()
        if self.target_storage_ref and self.task_id in self.target_storage_ref.pickup_reservations:
            res = self.target_storage_ref.pickup_reservations.get(self.task_id, {})
            amt = res.get(self.resource_to_retrieve, 0)
            if amt > 0:
                self.target_storage_ref.release_pickup_reservation(
                    self.task_id, self.resource_to_retrieve, amt
                )
            if not self.target_storage_ref.pickup_reservations.get(self.task_id):
                self.target_storage_ref.pickup_reservations.pop(self.task_id, None)

    def get_description(self) -> str:
        storage = self.target_storage_ref
        mill = self.target_processor_ref
        idx = self.current_step_index
        if idx == 0 and storage:
            return f"Moving to Storage at {storage.position}"
        if idx == 1 and storage:
            return f"Collecting {self.resource_to_retrieve.name} from {storage.position}"
        if idx == 2 and mill:
            return f"Moving to Mill at {mill.position}"
        if idx == 3 and mill:
            return f"Delivering {self.resource_to_retrieve.name} to {mill.position}"
        return f"Process {self.resource_to_retrieve.name} ({self.status.name})"


# ---------------------------------------------------------------------------
# PatrolTask — proof of cost for declarative step API (~20 lines)
# ---------------------------------------------------------------------------

class PatrolTask(Task):
    """One-shot patrol: move to point_a then point_b."""

    def __init__(self, priority: int, point_a, point_b):
        super().__init__(TaskType.PATROL, priority)
        self.point_a = point_a
        self.point_b = point_b

    def prepare(self, agent: 'Agent', resource_manager: 'ResourceManager') -> bool:
        a, b = self.point_a, self.point_b
        self.steps = [MoveToStep(lambda: a), MoveToStep(lambda: b)]
        self.current_step_index = 0
        self.status = TaskStatus.IN_PROGRESS
        self._submit_next_step(agent, resource_manager)
        return self.status != TaskStatus.FAILED

    def cleanup(self, agent: 'Agent', resource_manager: 'ResourceManager', success: bool):
        pass

    def get_description(self) -> str:
        pts = [self.point_a, self.point_b]
        idx = min(self.current_step_index, len(pts) - 1)
        return f"Patrol → {pts[idx]}"


# ---------------------------------------------------------------------------
# EatTask — self-generated personal task, never posted to the job board
# ---------------------------------------------------------------------------

class EatTask(Task):
    """Agent moves to a bread storage point and eats, restoring hunger."""

    def __init__(self, priority: int):
        super().__init__(TaskType.EAT, priority)
        self.target_storage_ref = None
        self._reserved_quantity: int = 0

    def prepare(self, agent: 'Agent', resource_manager: 'ResourceManager') -> bool:
        self._update_timestamp()
        self.status = TaskStatus.PREPARING

        faction_id = getattr(agent, 'owner_faction_id', None)
        own_storage = resource_manager.storage_points_for(faction_id)
        candidates = sorted(
            [sp for sp in own_storage if sp.has_resource(ResourceType.BREAD, 1)],
            key=lambda sp: (sp.position - agent.position).length_squared(),
        )
        for sp in candidates:
            reserved = sp.reserve_for_pickup(self.task_id, ResourceType.BREAD, 1, faction_id=faction_id)
            if reserved > 0:
                self.target_storage_ref = sp
                self._reserved_quantity = reserved
                break

        if not self.target_storage_ref:
            self.error_message = "No bread available"
            self.status = TaskStatus.FAILED
            return False

        if not agent.grid.find_walkable_adjacent_tile(self.target_storage_ref.position):
            self.target_storage_ref.release_pickup_reservation(self.task_id)
            self._reserved_quantity = 0
            self.error_message = "No walkable tile adjacent to bread storage"
            self.status = TaskStatus.FAILED
            return False

        storage = self.target_storage_ref
        grid = agent.grid
        collection_time = getattr(
            agent.config, 'DEFAULT_COLLECTION_TIME_FROM_STORAGE',
            agent.config.DEFAULT_GATHERING_TIME,
        )

        self.steps = [
            MoveToStep(lambda: grid.find_walkable_adjacent_tile(storage.position)),
            InteractStep(
                lambda: storage.id,
                "EAT_BREAD",
                lambda a, t: collection_time,
                self._on_eat_complete,
            ),
        ]
        self.current_step_index = 0
        self.status = TaskStatus.IN_PROGRESS
        self._submit_next_step(agent, resource_manager)
        return self.status != TaskStatus.FAILED

    def _on_eat_complete(self, agent, task, resource_manager):
        collected = self.target_storage_ref.collect_reserved_pickup(
            self.task_id, ResourceType.BREAD, 1
        )
        if collected > 0:
            self._reserved_quantity = 0
            agent.needs.hunger = min(1.0, agent.needs.hunger + agent.config.HUNGER_RESTORED_PER_BREAD)
            agent.logger.info(f"Ate bread. Hunger restored to {agent.needs.hunger:.2f}")
        else:
            self.status = TaskStatus.FAILED
            self.error_message = "Failed to collect bread at storage"

    def cleanup(self, agent: 'Agent', resource_manager: 'ResourceManager', success: bool):
        self._update_timestamp()
        if self.target_storage_ref and self._reserved_quantity > 0:
            self.target_storage_ref.release_pickup_reservation(
                self.task_id, ResourceType.BREAD, self._reserved_quantity
            )
            self._reserved_quantity = 0

    def get_description(self) -> str:
        storage = self.target_storage_ref
        if self.current_step_index == 0 and storage:
            return f"Moving to bread at {storage.position}"
        if self.current_step_index == 1 and storage:
            return f"Eating bread at {storage.position}"
        return f"Eat ({self.status.name})"
