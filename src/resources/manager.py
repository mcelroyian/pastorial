import pygame
import logging
from typing import List, TYPE_CHECKING, Optional
from .node import ResourceNode # Use relative import within the package
from .resource_types import ResourceType # For get_nodes_by_type
from .processing import ProcessingStation # For managing processing stations

# Forward reference for StoragePoint to avoid circular import if StoragePoint imports ResourceManager
if TYPE_CHECKING:
    from .storage_point import StoragePoint
    # ProcessingStation does not import ResourceManager, so forward ref not strictly needed here
    # but can be kept for consistency if desired.
    # from .processing import ProcessingStation

class ResourceManager:
    """
    Manages all resource nodes, storage points, and processing stations in the simulation.
    """
    def __init__(self):
        """
        Initializes the ResourceManager with empty lists for managed objects.
        """
        self.nodes: List[ResourceNode] = []
        self.storage_points: List['StoragePoint'] = []
        self.processing_stations: List[ProcessingStation] = []
        self.logger = logging.getLogger(__name__)

    def add_node(self, node: ResourceNode):
        """
        Adds a resource node to the manager.

        Args:
            node: The ResourceNode instance to add.
        """
        if isinstance(node, ResourceNode):
            self.nodes.append(node)
            self.logger.debug(f"Added resource node: {node.resource_type.name} at {node.position}")
        else:
            # Simple error handling, could be more robust (e.g., logging)
            self.logger.error(f"Attempted to add non-ResourceNode object to ResourceManager: {node}")

    def add_storage_point(self, storage_point: 'StoragePoint'):
        """
        Adds a storage point to the manager.

        Args:
            storage_point: The StoragePoint instance to add.
        """
        # Can add type checking if StoragePoint is directly imported
        # from .storage_point import StoragePoint
        # if isinstance(storage_point, StoragePoint):
        self.storage_points.append(storage_point) # type: ignore
        self.logger.debug(f"Added storage point at {storage_point.position} accepting {storage_point.accepted_resource_types}")
        # else:
        #     self.logger.error(f"Attempted to add non-StoragePoint object to ResourceManager: {storage_point}")

    def add_processing_station(self, station: ProcessingStation):
        """
        Adds a processing station to the manager.

        Args:
            station: The ProcessingStation instance to add.
        """
        if isinstance(station, ProcessingStation):
            self.processing_stations.append(station)
            self.logger.debug(f"Added processing station: {type(station).__name__} at {station.position}")
        else:
            self.logger.error(f"Attempted to add non-ProcessingStation object to ResourceManager: {station}")

    def get_nodes_by_type(self, resource_type: ResourceType) -> List[ResourceNode]:
        """
        Returns a list of resource nodes of a specific type.
        """
        return [node for node in self.nodes if hasattr(node, 'resource_type') and node.resource_type == resource_type]

    def update_nodes(self, dt: float, metrics=None):
        for node in self.nodes:
            node.update(dt)
        for station in self.processing_stations:
            station.tick()
        self._auto_distribute_outputs(metrics=metrics)

    def _auto_distribute_outputs(self, metrics=None):
        """Route processing station output buffers to downstream sinks each tick.

        - Single-output stations (Mill) → multi-input stations (Bakery) that accept that type.
        - Multi-input stations (Bakery) → storage points that accept each output type.

        This replaces the missing CollectProcessedAndDeliverTask for flour and bread.
        """
        from .processing import MultiInputProcessingStation

        # Mill → Bakery (single-output → multi-input, same faction)
        for source in self.processing_stations:
            if isinstance(source, MultiInputProcessingStation):
                continue
            if source.current_output_quantity < 1.0:
                continue
            output_type = source.produced_output_type
            source_faction = getattr(source, 'owner_faction_id', None)
            for sink in self.processing_stations:
                if sink is source or not isinstance(sink, MultiInputProcessingStation):
                    continue
                if output_type not in sink.recipe.inputs:
                    continue
                # Only route to same-faction sinks (or if either is unowned)
                sink_faction = getattr(sink, 'owner_faction_id', None)
                if source_faction is not None and sink_faction is not None and source_faction != sink_faction:
                    continue
                space = sink.input_capacity - sink.current_input_quantity.get(output_type, 0.0)
                transfer = min(source.current_output_quantity, max(0.0, space))
                if transfer >= 1.0:
                    source.current_output_quantity -= transfer
                    sink.current_input_quantity[output_type] = (
                        sink.current_input_quantity.get(output_type, 0.0) + transfer
                    )
                    if metrics is not None:
                        metrics.record("produced", resource_type=output_type, quantity=int(transfer),
                                       faction_id=source_faction)
                break

        # Bakery → storage points (multi-output → storage, same faction)
        for source in self.processing_stations:
            if not isinstance(source, MultiInputProcessingStation):
                continue
            source_faction = getattr(source, 'owner_faction_id', None)
            for output_type, qty in source.current_output_quantity.items():
                if qty < 1.0:
                    continue
                for sp in self.storage_points:
                    if sp.accepted_resource_types and output_type not in sp.accepted_resource_types:
                        continue
                    # Only push to same-faction storage (or if either is unowned)
                    sp_faction = getattr(sp, 'owner_faction_id', None)
                    if source_faction is not None and sp_faction is not None and source_faction != sp_faction:
                        continue
                    space = sp.overall_capacity - sp.get_current_load() - sp.get_total_reserved_quantity()
                    transfer = int(min(qty, max(0, space)))
                    if transfer >= 1:
                        source.current_output_quantity[output_type] -= transfer
                        sp.stored_resources[output_type] = sp.stored_resources.get(output_type, 0) + transfer
                        if metrics is not None:
                            metrics.record("produced", resource_type=output_type, quantity=transfer,
                                           faction_id=source_faction)
                    break

    def draw_nodes(self, surface: pygame.Surface, font: pygame.font.Font, grid): # Add grid parameter
        """
        Draws all managed resource nodes, storage points, and processing stations.

        Args:
            surface: The pygame surface to draw on.
            font: The pygame font to use for rendering text.
            grid: The game grid object for coordinate conversions (used by some draw methods).
        """
        for node in self.nodes:
            if hasattr(node, 'draw'):
                # All ResourceNode subclasses (including WheatField and BerryBush)
                # are now expected to have a draw(self, surface, font, grid) method.
                node.draw(surface, font, grid)

        for sp in self.storage_points:
            if hasattr(sp, 'draw'):
                # StoragePoint.draw is expected to take (surface, grid)
                sp.draw(surface, grid)
        
        for station in self.processing_stations:
            if hasattr(station, 'draw'):
                # ProcessingStation.draw takes (surface, font)
                station.draw(surface, font)

    def get_nearest_station_accepting(self, current_position: pygame.Vector2, resource_type: ResourceType) -> Optional[ProcessingStation]:
        """
        Finds the nearest processing station that accepts a given resource type and has input capacity.
        """
        available_stations = [
            s for s in self.processing_stations
            if s.can_accept_input(resource_type)
        ]

        if not available_stations:
            return None

        nearest_station = min(
            available_stations,
            key=lambda s: current_position.distance_squared_to(s.position)
        )
        return nearest_station

    def get_stations_with_output(self, resource_type: ResourceType) -> List[ProcessingStation]:
        """
        Returns a list of processing stations that have the specified processed resource type available.
        """
        return [
            s for s in self.processing_stations
            if s.produced_output_type == resource_type and s.has_output()
        ]
    def get_faction_resource_quantity(self, faction_id: Optional[int], resource_type: ResourceType) -> int:
        """Total quantity of a resource across storage points owned by a specific faction."""
        if faction_id is None:
            return self.get_global_resource_quantity(resource_type)
        return sum(
            sp.stored_resources.get(resource_type, 0)
            for sp in self.storage_points
            if sp.owner_faction_id == faction_id
        )

    def storage_points_for(self, faction_id: Optional[int]):
        """Storage points owned by faction_id (or all if faction_id is None)."""
        if faction_id is None:
            return self.storage_points
        return [sp for sp in self.storage_points if sp.owner_faction_id == faction_id]

    def stations_for(self, faction_id: Optional[int]):
        """Processing stations owned by faction_id (or all if faction_id is None)."""
        if faction_id is None:
            return self.processing_stations
        return [s for s in self.processing_stations if getattr(s, 'owner_faction_id', None) == faction_id]

    def get_global_resource_quantity(self, resource_type: ResourceType) -> int:
        """
        Calculates the total quantity of a specific resource type across all storage points.

        Args:
            resource_type: The ResourceType to query.

        Returns:
            The total integer quantity of the specified resource.
        """
        total_quantity = 0
        for sp in self.storage_points:
            # The 'stored_resources' attribute in StoragePoint is a Dict[ResourceType, int]
            total_quantity += sp.stored_resources.get(resource_type, 0)
        return total_quantity

    def has_available_sources(self, resource_type: ResourceType, min_quantity: int = 1) -> bool:
        """
        Checks if there are any available (unclaimed and with sufficient quantity)
        resource nodes for a given resource type.
        """
        for node in self.nodes:
            if node.resource_type == resource_type and \
               node.current_quantity >= min_quantity and \
               node.claimed_by_task_id is None:
                return True
        return False

    def has_available_dropoffs(self, resource_type: ResourceType, min_capacity: int = 1) -> bool:
        """
        Checks if there are any storage points that accept the given resource type
        and have available capacity for reservation/dropoff.
        """
        # Import StoragePoint here if not already available due to TYPE_CHECKING
        # from .storage_point import StoragePoint # Not strictly needed if using 'StoragePoint' string hint

        for sp in self.storage_points:
            # Ensure sp is an instance of StoragePoint if type hints are loose
            # For now, we assume self.storage_points only contains StoragePoint instances
            if sp.can_accept(resource_type, quantity=min_capacity, for_reservation=True): # Checks accepted types and available capacity
                return True
        
        # Future: Could extend to check ProcessingStation input buffers if tasks involve delivering to them
        # for station in self.processing_stations:
        #     if station.accepted_input_type == resource_type and station.can_accept_input(resource_type, min_capacity):
        #         return True
        return False