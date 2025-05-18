import pygame
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

    def add_node(self, node: ResourceNode):
        """
        Adds a resource node to the manager.

        Args:
            node: The ResourceNode instance to add.
        """
        if isinstance(node, ResourceNode):
            self.nodes.append(node)
        else:
            # Simple error handling, could be more robust (e.g., logging)
            print(f"Error: Attempted to add non-ResourceNode object to ResourceManager: {node}")

    def add_storage_point(self, storage_point: 'StoragePoint'):
        """
        Adds a storage point to the manager.

        Args:
            storage_point: The StoragePoint instance to add.
        """
        # Can add type checking if StoragePoint is directly imported
        # from .storage_point import StoragePoint
        # if isinstance(storage_point, StoragePoint):
        self.storage_points.append(storage_point)
        # else:
        #     print(f"Error: Attempted to add non-StoragePoint object to ResourceManager: {storage_point}")

    def add_processing_station(self, station: ProcessingStation):
        """
        Adds a processing station to the manager.

        Args:
            station: The ProcessingStation instance to add.
        """
        if isinstance(station, ProcessingStation):
            self.processing_stations.append(station)
        else:
            print(f"Error: Attempted to add non-ProcessingStation object to ResourceManager: {station}")

    def get_nodes_by_type(self, resource_type: ResourceType) -> List[ResourceNode]:
        """
        Returns a list of resource nodes of a specific type.
        """
        return [node for node in self.nodes if hasattr(node, 'resource_type') and node.resource_type == resource_type]

    def update_nodes(self, dt: float):
        """
        Updates all managed resource nodes and processing stations.

        Args:
            dt: The time elapsed since the last update in seconds (for ResourceNodes).
        """
        for node in self.nodes:
            node.update(dt)
        
        for station in self.processing_stations:
            station.tick() # Processing stations are updated per tick

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