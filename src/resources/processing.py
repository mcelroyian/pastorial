import pygame
import logging # Added
import uuid # Added for unique id
from typing import Optional, Dict
from src.resources.resource_types import ResourceType
from src.core import config # For potential future use, e.g. visual configuration
from .recipe import Recipe

class ProcessingStation:
    """
    Base class for resource processing stations (e.g., Mill, Bakery).
    Processes input resources into output resources over time.
    """
    def __init__(self,
                 position: pygame.Vector2,
                 accepted_input_type: ResourceType,
                 produced_output_type: ResourceType,
                 conversion_ratio: float, # e.g., 1.0 means 1 input makes 1 output
                 processing_speed: int,   # Ticks required to process one unit (or one batch based on conversion)
                 input_capacity: int,
                 output_capacity: int):
        """
        Initializes a ProcessingStation.

        Args:
            position: The position of the station on the grid.
            accepted_input_type: The type of resource this station accepts.
            produced_output_type: The type of resource this station produces.
            conversion_ratio: How many input units are needed for one output unit,
                              or how many output units are produced from one input unit.
                              For simplicity, let's assume 1 input unit produces X output units,
                              where X is conversion_ratio. Or 1 input -> 1 output if ratio is 1.0.
                              Let's refine: conversion_ratio = output_units / input_units.
                              If 1 WHEAT makes 1 FLOUR, ratio = 1.0.
                              If 2 WHEAT makes 1 FLOUR, ratio = 0.5 (meaning 1 input makes 0.5 output, effectively needing 2 inputs for 1 output).
                              Let's stick to: 1 input unit produces `conversion_ratio` output units.
                              The plan for Mill implies 1 WHEAT -> 1 FLOUR_POWDER, so ratio = 1.0.
           processing_speed: Number of simulation ticks required to complete one processing cycle.
           input_capacity: Maximum amount of input resources the station can hold.
           output_capacity: Maximum amount of output resources the station can hold.
       """
        self.id = uuid.uuid4() # Added for unique identification
        self.logger = logging.getLogger(__name__) # Added
        if not isinstance(position, pygame.Vector2):
            self.logger.critical("Position must be a pygame.Vector2") # Added
            raise TypeError("Position must be a pygame.Vector2")

        self.position = position
        self.accepted_input_type = accepted_input_type
        self.produced_output_type = produced_output_type
        self.conversion_ratio = float(conversion_ratio) # Ensure float
        self.processing_speed = int(processing_speed) # Ticks per processing cycle
        self.input_capacity = int(input_capacity)
        self.output_capacity = int(output_capacity)

        self.current_input_quantity = 0.0  # Can be float if partial inputs are allowed by agents
        self.current_output_quantity = 0.0 # Can be float
        self.is_processing = False
        self.processing_progress = 0  # Ticks accumulated towards current processing cycle

        # For drawing (subclasses should define specific colors/sprites)
        self.color = (100, 100, 100) # Default grey
        self.processing_color = (150, 150, 50) # Yellowish when processing

    def receive(self, resource_type: ResourceType, quantity: int) -> bool:
        """
        Adds input resources to the station if the type is accepted and there's capacity.
        Agents will typically deliver integer quantities.
        Returns True if resources were successfully added, False otherwise.
        """
        if resource_type == self.accepted_input_type and self.current_input_quantity < self.input_capacity:
            amount_to_add = min(float(quantity), self.input_capacity - self.current_input_quantity)
            if amount_to_add > 0:
                self.current_input_quantity += amount_to_add
                self.logger.debug(f"{self} received {amount_to_add} of {resource_type.name}. Input: {self.current_input_quantity}") # Changed
                return True
        self.logger.debug(f"{self} FAILED to receive {quantity} of {resource_type.name}. Input: {self.current_input_quantity}, Capacity: {self.input_capacity}, Accepted: {self.accepted_input_type.name}") # Changed
        return False

    def tick(self):
        """
        Handles the processing logic per simulation tick.
        One processing cycle consumes 1 unit of input and produces `conversion_ratio` units of output.
        """
        if self.current_input_quantity >= 1.0 and self.current_output_quantity < self.output_capacity:
            self.is_processing = True
            self.processing_progress += 1
            if self.processing_progress >= self.processing_speed:
                # One processing cycle complete
                self.current_input_quantity -= 1.0 # Consume one unit of input
                
                produced_amount = 1.0 * self.conversion_ratio
                
                # Ensure we don't overflow output capacity
                actual_produced_amount = min(produced_amount, self.output_capacity - self.current_output_quantity)
                
                self.current_output_quantity += actual_produced_amount
                
                self.processing_progress = 0 # Reset for next cycle
                
                # If we couldn't produce the full amount due to output capacity,
                # the input was still consumed. This implies a need for agents to clear output.
                self.logger.debug(f"{self} processed. Input: {self.current_input_quantity}, Output: {self.current_output_quantity}") # Changed

                if self.current_input_quantity < 1.0 or self.current_output_quantity >= self.output_capacity:
                    self.is_processing = False # Stop if no more input or output full
        else:
            self.is_processing = False
            self.processing_progress = 0 # Reset if not enough input or output is full

    def dispense(self, requested_quantity: int) -> int:
        """
        Allows an agent to collect processed output resources.
        Returns the actual integer amount of resources dispensed.
        """
        available_integer_output = int(self.current_output_quantity)
        amount_to_dispense = min(requested_quantity, available_integer_output)

        if amount_to_dispense > 0:
            self.current_output_quantity -= float(amount_to_dispense)
            self.logger.debug(f"{self} dispensed {amount_to_dispense} of {self.produced_output_type.name}. Output: {self.current_output_quantity}") # Changed
            return amount_to_dispense
        return 0

    def can_accept_input(self, resource_type: ResourceType, quantity: int = 1) -> bool:
        """Checks if the station can accept the given resource type and has space for at least the quantity."""
        return resource_type == self.accepted_input_type and (self.current_input_quantity + quantity) <= self.input_capacity

    def has_output(self) -> bool:
        """Checks if there are any processed goods (at least 1 full unit) to collect."""
        return self.current_output_quantity >= 1.0

    def get_visual_state(self) -> str:
        """Returns 'idle' or 'processing' for visualization purposes."""
        return "processing" if self.is_processing else "idle"

    def draw(self, surface: pygame.Surface, font: pygame.font.Font):
        """
        Draws the processing station on the given surface.
        Subclasses should override for specific visuals.
        """
        rect_x = self.position.x * config.GRID_CELL_SIZE
        rect_y = self.position.y * config.GRID_CELL_SIZE
        station_rect = pygame.Rect(rect_x, rect_y, config.GRID_CELL_SIZE, config.GRID_CELL_SIZE)

        current_color = self.processing_color if self.is_processing else self.color
        pygame.draw.rect(surface, current_color, station_rect)
        pygame.draw.rect(surface, config.COLOR_BLACK, station_rect, 1) # Border

        # Display input: "I:type qty/cap"
        input_text_str = f"I:{self.accepted_input_type.name[0]}:{int(self.current_input_quantity)}/{self.input_capacity}"
        input_surface = font.render(input_text_str, True, config.DEBUG_TEXT_COLOR)
        input_rect = input_surface.get_rect(midtop=station_rect.midtop)
        input_rect.y += 2 # Small offset
        surface.blit(input_surface, input_rect)
        
        # Display output: "O:type qty/cap"
        output_text_str = f"O:{self.produced_output_type.name[0]}:{int(self.current_output_quantity)}/{self.output_capacity}"
        output_surface = font.render(output_text_str, True, config.DEBUG_TEXT_COLOR)
        output_rect = output_surface.get_rect(midbottom=station_rect.midbottom)
        output_rect.y -= 2 # Small offset
        surface.blit(output_surface, output_rect)

        if self.is_processing:
            progress_text_str = f"{self.processing_progress}/{self.processing_speed}"
            progress_surface = font.render(progress_text_str, True, config.DEBUG_TEXT_COLOR)
            progress_rect = progress_surface.get_rect(center=station_rect.center)
            surface.blit(progress_surface, progress_rect)


    def __str__(self):
        return (f"{self.__class__.__name__} at {self.position} "
                f"[{self.accepted_input_type.name} -> {self.produced_output_type.name}] "
                f"Input: {self.current_input_quantity:.1f}/{self.input_capacity}, "
                f"Output: {self.current_output_quantity:.1f}/{self.output_capacity}, "
                f"State: {self.get_visual_state()} ({self.processing_progress}/{self.processing_speed})")

    def __repr__(self):
       return (f"{self.__class__.__name__}(position={self.position}, "
               f"input_type={self.accepted_input_type.name}, output_type={self.produced_output_type.name})")

class MultiInputProcessingStation(ProcessingStation):
    """
    A processing station that uses a data-driven recipe to define its
    inputs and outputs. It can handle multiple types of input resources.
    """
    def __init__(self,
                 position: pygame.Vector2,
                 recipe: Recipe,
                 processing_speed: int,
                 input_capacity: int,
                 output_capacity: int):
        """
        Initializes a MultiInputProcessingStation.

        Args:
            position: The position of the station on the grid.
            recipe: The Recipe object defining inputs and outputs.
            processing_speed: Ticks required to complete one processing cycle.
            input_capacity: Maximum amount of each input resource the station can hold.
            output_capacity: Maximum amount of each output resource the station can hold.
        """
        # We need to call the parent __init__ but some of its parameters are now
        # derived from the recipe. We'll use the first input/output type as a placeholder.
        first_input_type = next(iter(recipe.inputs)) if recipe.inputs else None
        first_output_type = next(iter(recipe.outputs)) if recipe.outputs else None

        super().__init__(
            position=position,
            accepted_input_type=first_input_type,
            produced_output_type=first_output_type,
            conversion_ratio=1.0,  # Not directly used; logic is in the recipe
            processing_speed=processing_speed,
            input_capacity=input_capacity,
            output_capacity=output_capacity
        )

        self.recipe = recipe
        # Override storage to handle multiple resource types
        self.current_input_quantity: Dict[str, float] = {resource_type: 0.0 for resource_type in self.recipe.inputs}
        self.current_output_quantity: Dict[str, float] = {resource_type: 0.0 for resource_type in self.recipe.outputs}

    def _has_required_inputs(self) -> bool:
        """Checks if the station has enough of all required inputs for one cycle."""
        for resource_type, required_qty in self.recipe.inputs.items():
            if self.current_input_quantity.get(resource_type, 0.0) < required_qty:
                return False
        return True

    def _has_output_space(self) -> bool:
        """Checks if there is enough space for all outputs of one cycle."""
        for resource_type, produced_qty in self.recipe.outputs.items():
            if self.current_output_quantity.get(resource_type, 0.0) + produced_qty > self.output_capacity:
                return False
        return True

    def tick(self):
        """
        Handles the processing logic per simulation tick based on the recipe.
        """
        if self._has_required_inputs() and self._has_output_space():
            self.is_processing = True
            self.processing_progress += 1
            if self.processing_progress >= self.processing_speed:
                # Consume inputs
                for resource_type, required_qty in self.recipe.inputs.items():
                    self.current_input_quantity[resource_type] -= required_qty
                
                # Produce outputs
                for resource_type, produced_qty in self.recipe.outputs.items():
                    self.current_output_quantity[resource_type] += produced_qty

                self.processing_progress = 0
                self.logger.debug(f"{self} processed recipe. Inputs: {self.current_input_quantity}, Outputs: {self.current_output_quantity}")
        else:
            self.is_processing = False
            self.processing_progress = 0

    def receive(self, resource_type: ResourceType, quantity: int) -> bool:
        """
        Adds input resources to the station if the type is in the recipe and there's capacity.
        """
        if resource_type in self.recipe.inputs and self.current_input_quantity.get(resource_type, 0.0) < self.input_capacity:
            amount_to_add = min(float(quantity), self.input_capacity - self.current_input_quantity[resource_type])
            if amount_to_add > 0:
                self.current_input_quantity[resource_type] += amount_to_add
                self.logger.debug(f"{self} received {amount_to_add} of {resource_type}. Input cache: {self.current_input_quantity[resource_type]}")
                return True
        self.logger.debug(f"{self} FAILED to receive {quantity} of {resource_type}. Check recipe or capacity.")
        return False

    def can_accept_input(self, resource_type: ResourceType, quantity: int = 1) -> bool:
        """Checks if the station can accept the given resource type and has space."""
        if resource_type not in self.recipe.inputs:
            return False
        return (self.current_input_quantity.get(resource_type, 0.0) + quantity) <= self.input_capacity

    def has_output(self) -> bool:
        """Checks if there are any processed goods to collect."""
        for resource_type in self.recipe.outputs:
            if self.current_output_quantity.get(resource_type, 0.0) >= 1.0:
                return True
        return False

    def dispense(self, requested_quantity: int, resource_type: ResourceType) -> int:
        """
        Allows an agent to collect a specific type of processed output resource.
        """
        if resource_type not in self.recipe.outputs:
            return 0

        available_integer_output = int(self.current_output_quantity.get(resource_type, 0.0))
        amount_to_dispense = min(requested_quantity, available_integer_output)

        if amount_to_dispense > 0:
            self.current_output_quantity[resource_type] -= float(amount_to_dispense)
            self.logger.debug(f"{self} dispensed {amount_to_dispense} of {resource_type}. Output cache: {self.current_output_quantity[resource_type]}")
            return amount_to_dispense
        return 0

    def draw(self, surface: pygame.Surface, font: pygame.font.Font):
        """
        Draws the multi-input processing station on the given surface.
        """
        rect_x = self.position.x * config.GRID_CELL_SIZE
        rect_y = self.position.y * config.GRID_CELL_SIZE
        station_rect = pygame.Rect(rect_x, rect_y, config.GRID_CELL_SIZE, config.GRID_CELL_SIZE)

        current_color = self.processing_color if self.is_processing else self.color
        pygame.draw.rect(surface, current_color, station_rect)
        pygame.draw.rect(surface, config.COLOR_BLACK, station_rect, 1)

        # Simplified display for multiple inputs/outputs
        # TODO: A more robust UI for this might be needed
        num_input_types = len(self.recipe.inputs)
        input_text = f"I:{num_input_types}"
        input_surface = font.render(input_text, True, config.DEBUG_TEXT_COLOR)
        surface.blit(input_surface, (rect_x + 2, rect_y + 2))

        num_output_types = len(self.recipe.outputs)
        output_text = f"O:{num_output_types}"
        output_surface = font.render(output_text, True, config.DEBUG_TEXT_COLOR)
        surface.blit(output_surface, (rect_x + 2, rect_y + config.GRID_CELL_SIZE - 18))

        if self.is_processing:
            progress_text_str = f"{self.processing_progress}/{self.processing_speed}"
            progress_surface = font.render(progress_text_str, True, config.DEBUG_TEXT_COLOR)
            progress_rect = progress_surface.get_rect(center=station_rect.center)
            surface.blit(progress_surface, progress_rect)

    def __str__(self):
        return (f"{self.__class__.__name__} at {self.position} "
                f"Inputs: {self.current_input_quantity}, "
                f"Outputs: {self.current_output_quantity}, "
                f"State: {self.get_visual_state()} ({self.processing_progress}/{self.processing_speed})")