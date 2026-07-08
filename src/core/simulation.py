import random
import logging
from typing import List, Optional

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
from src.core.metrics import SimMetrics
from src.factions.faction import Faction


class Simulation:
    """
    All simulation state: grid, resources, tasks, agents, factions.
    No pygame.display / pygame.font / Surface usage — safe to run headless.
    """

    def __init__(self, seed=None, scenario=None):
        if seed is not None:
            random.seed(seed)

        self.sim_time: float = 0.0
        self.metrics: SimMetrics = SimMetrics()
        self.logger = logging.getLogger(__name__)
        self.scenario = scenario  # optional config-override dataclass

        self.grid = Grid()
        self.resource_manager = ResourceManager()
        self.factions: List[Faction] = []

        self._build_factions()
        self._spawn_wild_nodes()
        self._spawn_faction_buildings()
        self._spawn_faction_agents()

    # ------------------------------------------------------------------
    # Faction construction
    # ------------------------------------------------------------------

    def _build_factions(self):
        num_factions = config.NUM_FACTIONS
        grid_w = self.grid.width_in_cells
        grid_h = self.grid.height_in_cells

        if num_factions == 1:
            regions = [pygame.Rect(0, 0, grid_w, grid_h)]
        else:
            third = grid_w // 3
            regions = [
                pygame.Rect(0, 0, third, grid_h),                   # west
                pygame.Rect(grid_w - third, 0, third, grid_h),      # east
            ]

        faction_cfgs = config.FACTION_CONFIGS
        for i in range(num_factions):
            cfg = faction_cfgs[i] if i < len(faction_cfgs) else {"name": f"Faction{i}", "color": (180, 180, 60)}
            tm = TaskManager(resource_manager=self.resource_manager)
            tm.faction_id = i
            tm.metrics = self.metrics
            faction = Faction(
                faction_id=i,
                name=cfg["name"],
                color=cfg["color"],
                home_region=regions[i],
                task_manager=tm,
            )
            self.factions.append(faction)

    # ------------------------------------------------------------------
    # Spawn helpers
    # ------------------------------------------------------------------

    def _find_available_spawn_points(
        self,
        entity_grid_width: int,
        entity_grid_height: int,
        bounds: Optional[pygame.Rect] = None,
    ) -> List[Vector2]:
        """Return free grid positions, optionally constrained to a rect (grid coords)."""
        available: List[Vector2] = []
        r = bounds or pygame.Rect(0, 0, self.grid.width_in_cells, self.grid.height_in_cells)
        for gy in range(r.top, r.bottom - entity_grid_height + 1):
            for gx in range(r.left, r.right - entity_grid_width + 1):
                if self.grid.is_area_free(gx, gy, entity_grid_width, entity_grid_height):
                    available.append(Vector2(gx, gy))
        return available

    def _spawn_entity(self, entity_class, num_to_spawn, bounds=None, owner_faction_id=None, **kwargs):
        entity_name = entity_class.__name__
        w = getattr(entity_class, 'GRID_WIDTH', 1)
        h = getattr(entity_class, 'GRID_HEIGHT', 1)
        spots = self._find_available_spawn_points(w, h, bounds)

        if not spots:
            self.logger.warning(f"No space for {entity_name} (bounds={bounds}).")
            return []

        random.shuffle(spots)
        spawned_entities = []
        for pos_vec in spots[:num_to_spawn]:
            gx, gy = int(pos_vec.x), int(pos_vec.y)
            entity = entity_class(pos_vec, **kwargs)
            if owner_faction_id is not None:
                entity.owner_faction_id = owner_faction_id
            if isinstance(entity, (Mill, Bakery)):
                self.resource_manager.add_processing_station(entity)
            else:
                self.resource_manager.add_node(entity)
            self.grid.update_occupancy(entity, gx, gy, w, h, is_placing=True)
            spawned_entities.append(entity)

        if len(spawned_entities) < num_to_spawn:
            self.logger.warning(f"Spawned {len(spawned_entities)}/{num_to_spawn} {entity_name}s.")
        return spawned_entities

    def _spawn_storage(self, position: Vector2, accepted_types, capacity, owner_faction_id=None, initial_stock=None):
        gx, gy = int(position.x), int(position.y)
        if not self.grid.is_area_free(gx, gy, 1, 1):
            self.logger.warning(f"Could not spawn storage at ({gx},{gy}) — occupied.")
            return None
        sp = StoragePoint(position=position, overall_capacity=capacity, accepted_resource_types=accepted_types)
        sp.owner_faction_id = owner_faction_id
        if initial_stock:
            for rt, qty in initial_stock.items():
                sp.stored_resources[rt] = qty
        self.resource_manager.add_storage_point(sp)
        self.grid.update_occupancy(sp, gx, gy, 1, 1, is_placing=True)
        return sp

    # ------------------------------------------------------------------
    # Wild nodes (shared, concentrated in center strip)
    # ------------------------------------------------------------------

    def _spawn_wild_nodes(self):
        grid_w = self.grid.width_in_cells
        grid_h = self.grid.height_in_cells
        num_factions = config.NUM_FACTIONS

        if num_factions <= 1:
            # 1-faction path: distribute uniformly
            wild_bounds = None
        else:
            third = grid_w // 3
            wild_bounds = pygame.Rect(third, 0, grid_w - 2 * third, grid_h)

        def _scen(attr, default):
            v = getattr(self.scenario, attr, None) if self.scenario else None
            return v if v is not None else default

        berry_count = _scen('wild_berry_bushes', config.WILD_BERRY_BUSHES)
        wheat_count = _scen('wild_wheat_fields', config.WILD_WHEAT_FIELDS)

        self._spawn_entity(BerryBush, berry_count, bounds=wild_bounds)   # owner_faction_id stays None
        self._spawn_entity(WheatField, wheat_count, bounds=wild_bounds)
        self._spawn_entity(Beehive, config.WILD_BEEHIVES)               # always wild, no bounds

    # ------------------------------------------------------------------
    # Per-faction buildings
    # ------------------------------------------------------------------

    def _spawn_faction_buildings(self):
        for faction in self.factions:
            fid = faction.faction_id
            region = faction.home_region

            mills = self._spawn_entity(Mill, config.PER_FACTION_MILLS, bounds=region, owner_faction_id=fid)
            bakeries = self._spawn_entity(Bakery, config.PER_FACTION_BAKERIES, bounds=region, owner_faction_id=fid)
            self._spawn_entity(WaterSource, config.PER_FACTION_WELLS, bounds=region, owner_faction_id=fid)

            # Pre-stock bakeries
            for station in bakeries:
                station.current_input_quantity[ResourceType.FLOUR_POWDER] = config.INITIAL_BAKERY_FLOUR
                station.current_input_quantity[ResourceType.WATER] = config.INITIAL_BAKERY_WATER

            # Berry/wheat storage — near faction center
            cx = region.centerx
            cy = region.centery
            bw_sp = self._try_place_storage_near(
                cx, cy, region,
                accepted_types=[ResourceType.BERRY, ResourceType.WHEAT],
                capacity=config.DEFAULT_STORAGE_CAPACITY,
                owner_faction_id=fid,
            )

            # Flour/bread storage — offset a few cells
            initial_bread = getattr(self.scenario, 'faction_initial_bread', None) if self.scenario else None
            bread_qty = initial_bread[fid] if initial_bread and fid < len(initial_bread) else config.PER_FACTION_INITIAL_BREAD
            fb_sp = self._try_place_storage_near(
                cx + 2, cy, region,
                accepted_types=[ResourceType.FLOUR_POWDER, ResourceType.BREAD],
                capacity=50,
                owner_faction_id=fid,
                initial_stock={ResourceType.BREAD: bread_qty},
            )

            # Register building ids on the faction
            for e in (mills + bakeries):
                faction.building_ids.append(e.id)
            for sp in (bw_sp, fb_sp):
                if sp:
                    faction.building_ids.append(sp.id)

    def _try_place_storage_near(self, cx, cy, region, accepted_types, capacity, owner_faction_id, initial_stock=None):
        """Try several candidate positions near (cx, cy) within region."""
        candidates = [
            (cx, cy), (cx + 1, cy), (cx - 1, cy),
            (cx, cy + 1), (cx, cy - 1),
            (cx + 2, cy), (cx - 2, cy),
            (cx + 3, cy), (cx - 3, cy),
        ]
        for gx, gy in candidates:
            gx = max(region.left, min(gx, region.right - 1))
            gy = max(region.top, min(gy, region.bottom - 1))
            sp = self._spawn_storage(
                Vector2(gx, gy), accepted_types, capacity, owner_faction_id, initial_stock
            )
            if sp:
                return sp
        self.logger.warning(f"Could not place storage near ({cx},{cy}) for faction {owner_faction_id}.")
        return None

    # ------------------------------------------------------------------
    # Per-faction agents
    # ------------------------------------------------------------------

    def _spawn_faction_agents(self):
        for faction in self.factions:
            fid = faction.faction_id
            region = faction.home_region
            per_faction_sc = getattr(self.scenario, 'per_faction_agents', None) if self.scenario else None
            per_faction = per_faction_sc if per_faction_sc is not None else config.PER_FACTION_AGENTS

            spawned = 0
            attempts = 0
            while spawned < per_faction and attempts < per_faction * 10:
                attempts += 1
                gx = random.randint(region.left, region.right - 1)
                gy = random.randint(region.top, region.bottom - 1)
                if not self.grid.is_area_free(gx, gy, 1, 1):
                    continue
                grid_pos = Vector2(gx, gy)
                agent = self.agent_manager_for(faction).create_agent(
                    position=grid_pos,
                    speed=config.AGENT_SPEED,
                    faction_id=fid,
                )
                self.grid.update_occupancy(agent, gx, gy, 1, 1, is_placing=True)
                faction.agent_ids.append(agent.id)
                spawned += 1

            if spawned < per_faction:
                self.logger.warning(f"Faction {faction.name}: spawned {spawned}/{per_faction} agents.")

    def agent_manager_for(self, faction: Faction) -> 'AgentManager':
        """Return (or lazily create) the shared AgentManager, wiring the faction's task_manager."""
        if not hasattr(self, '_agent_manager'):
            self._agent_manager = AgentManager(grid=self.grid, task_manager=faction.task_manager)
        else:
            # Swap task_manager reference so create_agent wires the right board
            self._agent_manager.task_manager_ref = faction.task_manager
        return self._agent_manager

    @property
    def agent_manager(self) -> 'AgentManager':
        if not hasattr(self, '_agent_manager'):
            self._agent_manager = AgentManager(grid=self.grid, task_manager=self.factions[0].task_manager)
        return self._agent_manager

    @property
    def task_manager(self) -> TaskManager:
        """Legacy accessor — returns faction 0's task manager."""
        return self.factions[0].task_manager

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, dt: float, manual_mode: bool = False):
        self.sim_time += dt
        self.resource_manager.update_nodes(dt, metrics=self.metrics)
        for faction in self.factions:
            faction.task_manager.update(dt, manual_mode, self.sim_time)
        self.agent_manager.update_agents(dt, self.resource_manager, self.metrics)
        self.metrics.update(self.sim_time, self.resource_manager, self.agent_manager, factions=self.factions)
