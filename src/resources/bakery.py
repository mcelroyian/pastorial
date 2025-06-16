import pygame
from typing import Dict, List
from ..core import config
from .processing import ProcessingStation
from .resource_types import ResourceType

class Bakery(ProcessingStation):
    """
    A bakery that processes flour and water into bread.
    It requires multiple input types, so it overrides some base functionality.
    """
    GRID_WIDTH = 2
    GRID_HEIGHT = 2

    def __init__(self, position: pygame.Vector2):
        # Call super() with placeholder values for single-resource attributes.
        # These will be largely ignored in favor of the multi-resource logic.
        super().__init__(
            position=position,
            accepted_input_type=ResourceType.FLOUR_POWDER, # Placeholder
            produced_output_type=ResourceType.BREAD,
            conversion_ratio=1.0, # Placeholder
            processing_speed=config.BAKERY_PROCESSING_SPEED,
            input_capacity=0, # Placeholder
            output_capacity=config.BAKERY_OUTPUT_CAPACITY
        )

        # Multi-resource specific attributes
        self.accepted_input_types: List[ResourceType] = [ResourceType.FLOUR_POWDER, ResourceType.WATER]
        self.input_capacities: Dict[ResourceType, int] = {
            ResourceType.FLOUR_POWDER: config.BAKERY_FLOUR_CAPACITY,
            ResourceType.WATER: config.BAKERY_WATER_CAPACITY
        }
        self.input_storage: Dict[ResourceType, float] = {
            ResourceType.FLOUR_POWDER: 0.0,
            ResourceType.WATER: 0.0
        }
        self.recipe: Dict[ResourceType, int] = {
            ResourceType.FLOUR_POWDER: 2, # 2 units of flour
            ResourceType.WATER: 1        # 1 unit of water
        }
        self.output_per_cycle = 1 # Produces 1 BREAD per cycle

        # Visuals
        self.color = config.BAKERY_COLOR
        self.processing_color = config.BAKERY_PROCESSING_COLOR

    def can_accept_input(self, resource_type: ResourceType, quantity: int = 1) -> bool:
        """Checks if the station can accept the given resource type and has space."""
        if resource_type not in self.accepted_input_types:
            return False
        
        has_capacity = (self.input_storage[resource_type] + quantity) <= self.input_capacities[resource_type]
        return has_capacity

    def receive(self, resource_type: ResourceType, quantity: int) -> bool:
        """Adds input resources to the station if the type is accepted and there's capacity."""
        if not self.can_accept_input(resource_type, quantity):
            return False

        amount_to_add = min(float(quantity), self.input_capacities[resource_type] - self.input_storage[resource_type])
        if amount_to_add > 0:
            self.input_storage[resource_type] += amount_to_add
            self.logger.debug(f"{self} received {amount_to_add} of {resource_type.name}. New total: {self.input_storage[resource_type]}")
            return True
        return False

    def _has_ingredients_for_cycle(self) -> bool:
        """Checks if there are enough ingredients to start a processing cycle."""
        for resource, required_amount in self.recipe.items():
            if self.input_storage.get(resource, 0) < required_amount:
                return False
        return True

    def tick(self):
        """Handles the processing logic per simulation tick for multiple inputs."""
        if not self.is_processing and self._has_ingredients_for_cycle() and self.current_output_quantity < self.output_capacity:
            self.is_processing = True
            self.processing_progress = 0

        if self.is_processing:
            self.processing_progress += 1
            if self.processing_progress >= self.processing_speed:
                # Cycle complete, consume ingredients and produce output
                for resource, required_amount in self.recipe.items():
                    self.input_storage[resource] -= required_amount
                
                produced_amount = self.output_per_cycle
                actual_produced_amount = min(produced_amount, self.output_capacity - self.current_output_quantity)
                self.current_output_quantity += actual_produced_amount
                
                self.logger.debug(f"{self} processed bread. Output: {self.current_output_quantity}")
                
                # Reset and check if another cycle can start
                self.processing_progress = 0
                if not self._has_ingredients_for_cycle() or self.current_output_quantity >= self.output_capacity:
                    self.is_processing = False
        else:
            # Ensure progress is reset if we can't process
            self.processing_progress = 0

    def draw(self, surface: pygame.Surface, font: pygame.font.Font):
        """Draws the bakery on the given surface."""
        rect_x = self.position.x * config.GRID_CELL_SIZE
        rect_y = self.position.y * config.GRID_CELL_SIZE
        station_rect = pygame.Rect(rect_x, rect_y, self.GRID_WIDTH * config.GRID_CELL_SIZE, self.GRID_HEIGHT * config.GRID_CELL_SIZE)

        current_color = self.processing_color if self.is_processing else self.color
        pygame.draw.rect(surface, current_color, station_rect)
        pygame.draw.rect(surface, config.COLOR_BLACK, station_rect, 1)

        # Display inputs
        flour_text = f"F: {int(self.input_storage[ResourceType.FLOUR_POWDER])}/{self.input_capacities[ResourceType.FLOUR_POWDER]}"
        water_text = f"W: {int(self.input_storage[ResourceType.WATER])}/{self.input_capacities[ResourceType.WATER]}"
        
        flour_surface = font.render(flour_text, True, config.DEBUG_TEXT_COLOR)
        water_surface = font.render(water_text, True, config.DEBUG_TEXT_COLOR)
        
        surface.blit(flour_surface, (station_rect.x + 5, station_rect.y + 5))
        surface.blit(water_surface, (station_rect.x + 5, station_rect.y + 25))

        # Display output
        output_text = f"B: {int(self.current_output_quantity)}/{self.output_capacity}"
        output_surface = font.render(output_text, True, config.DEBUG_TEXT_COLOR)
        output_rect = output_surface.get_rect(bottomright=(station_rect.right - 5, station_rect.bottom - 5))
        surface.blit(output_surface, output_rect)

        if self.is_processing:
            progress_text = f"{self.processing_progress}/{self.processing_speed}"
            progress_surface = font.render(progress_text, True, config.DEBUG_TEXT_COLOR)
            progress_rect = progress_surface.get_rect(center=station_rect.center)
            surface.blit(progress_surface, progress_rect)

    def __str__(self):
        inputs = ", ".join([f"{r.name}: {q:.1f}/{self.input_capacities[r]}" for r, q in self.input_storage.items()])
        return (f"{self.__class__.__name__} at {self.position} "
                f"[{inputs} -> {self.produced_output_type.name}] "
                f"Output: {self.current_output_quantity:.1f}/{self.output_capacity}, "
                f"State: {self.get_visual_state()} ({self.processing_progress}/{self.processing_speed})")