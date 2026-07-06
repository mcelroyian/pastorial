import random
import logging
from typing import List

import pygame
from pygame.math import Vector2

from src.core import config
from src.rendering.grid import Grid
from src.resources.manager import ResourceManager
from src.resources.berry_bush import BerryBush
from src.resources.wheat_field import WheatField
from src.resources.water_source import WaterSource
from src.resources.mill import Mill
from src.resources.bakery import Bakery
from src.resources.beehive import Beehive
from src.resources.storage_point import StoragePoint
from src.resources.resource_types import ResourceType
from src.agents.manager import AgentManager
from src.tasks.task_manager import TaskManager


class Simulation:
    """
    All simulation state: grid, resources, tasks, agents.
    No pygame.display / pygame.font / Surface usage — safe to run headless.
    """

    def __init__(self, seed=None):
        if seed is not None:
            random.seed(seed)

        self.logger = logging.getLogger(__name__)

        self.grid = Grid()
        self.resource_manager = ResourceManager()
        self._spawn_initial_resources()
        self._spawn_initial_storage_points()

        self.task_manager = TaskManager(resource_manager=self.resource_manager)
        self.agent_manager = AgentManager(grid=self.grid, task_manager=self.task_manager)
        self._spawn_initial_agents()

    def update(self, dt: float, manual_mode: bool = False):
        self.resource_manager.update_nodes(dt)
        self.task_manager.update(dt, manual_mode)
        self.agent_manager.update_agents(dt, self.resource_manager)

    def _find_available_spawn_points(self, entity_grid_width: int, entity_grid_height: int) -> List[Vector2]:
        available: List[Vector2] = []
        for gy in range(self.grid.height_in_cells - entity_grid_height + 1):
            for gx in range(self.grid.width_in_cells - entity_grid_width + 1):
                if self.grid.is_area_free(gx, gy, entity_grid_width, entity_grid_height):
                    available.append(Vector2(gx, gy))
        return available

    def _spawn_entity(self, entity_class, num_to_spawn, **kwargs):
        entity_name = entity_class.__name__
        self.logger.info(f"Attempting to spawn {num_to_spawn} {entity_name}(s)...")

        w = getattr(entity_class, 'GRID_WIDTH', 1)
        h = getattr(entity_class, 'GRID_HEIGHT', 1)
        spots = self._find_available_spawn_points(w, h)

        if not spots:
            self.logger.warning(f"No available space to spawn any {entity_name}s of size {w}x{h}.")
            return

        random.shuffle(spots)
        spawned = 0
        for pos_vec in spots[:num_to_spawn]:
            gx, gy = int(pos_vec.x), int(pos_vec.y)
            entity = entity_class(pos_vec, **kwargs)
            if isinstance(entity, (Mill, Bakery)):
                self.resource_manager.add_processing_station(entity)
            else:
                self.resource_manager.add_node(entity)
            self.grid.update_occupancy(entity, gx, gy, w, h, is_placing=True)
            self.logger.debug(f"Spawned {entity_name} at {pos_vec}")
            spawned += 1

        if spawned < num_to_spawn:
            self.logger.warning(f"Spawned {spawned}/{num_to_spawn} {entity_name}s (limited space).")

    def _spawn_initial_resources(self):
        self._spawn_entity(BerryBush, config.INITIAL_BERRY_BUSHES)
        self._spawn_entity(WheatField, config.INITIAL_WHEAT_FIELD)
        self._spawn_entity(WaterSource, config.INITIAL_WELLS)
        self._spawn_entity(Mill, config.DESIRED_NUM_MILLS)
        self._spawn_entity(Bakery, config.INITIAL_BAKERIES)
        self._spawn_entity(Beehive, getattr(config, 'INITIAL_BEEHIVES', 1))

    def _spawn_initial_storage_points(self):
        mid = pygame.math.Vector2(config.SCREEN_WIDTH / 2, config.SCREEN_HEIGHT / 2)
        sg = self.grid.screen_to_grid(mid)
        sgx, sgy = int(sg.x), int(sg.y)

        if self.grid.is_area_free(sgx, sgy, 1, 1):
            sp = StoragePoint(
                position=Vector2(sgx, sgy),
                overall_capacity=config.DEFAULT_STORAGE_CAPACITY,
                accepted_resource_types=[ResourceType.BERRY, ResourceType.WHEAT]
            )
            self.resource_manager.add_storage_point(sp)
            self.grid.update_occupancy(sp, sgx, sgy, 1, 1, is_placing=True)
        else:
            self.logger.warning(f"Could not spawn BERRY/WHEAT StoragePoint at ({sgx},{sgy}).")

        fx = max(0, min(int(self.grid.width_in_cells / 2 + 5), self.grid.width_in_cells - 1))
        fy = max(0, min(int(self.grid.height_in_cells / 2), self.grid.height_in_cells - 1))
        if self.grid.is_area_free(fx, fy, 1, 1):
            fsp = StoragePoint(
                position=Vector2(fx, fy),
                overall_capacity=30,
                accepted_resource_types=[ResourceType.FLOUR_POWDER, ResourceType.BREAD]
            )
            self.resource_manager.add_storage_point(fsp)
            self.grid.update_occupancy(fsp, fx, fy, 1, 1, is_placing=True)
        else:
            self.logger.warning(f"Could not spawn FLOUR StoragePoint at ({fx},{fy}).")

    def _spawn_initial_agents(self):
        for _ in range(config.INITIAL_AGENTS):
            sx = random.uniform(config.SCREEN_SPAWN_MARGIN, config.SCREEN_WIDTH - config.SCREEN_SPAWN_MARGIN)
            sy = random.uniform(config.SCREEN_SPAWN_MARGIN, config.SCREEN_HEIGHT - config.SCREEN_SPAWN_MARGIN)
            grid_pos = self.grid.screen_to_grid(pygame.math.Vector2(sx, sy))
            gx, gy = int(grid_pos.x), int(grid_pos.y)
            if self.grid.is_area_free(gx, gy, 1, 1):
                agent = self.agent_manager.create_agent(position=grid_pos, speed=config.AGENT_SPEED)
                self.grid.update_occupancy(agent, gx, gy, 1, 1, is_placing=True)
            else:
                self.logger.warning(f"Could not spawn agent at {grid_pos}, area occupied.")
