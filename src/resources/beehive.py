import os
from typing import Optional
import pygame
from src.core import config
from .node import ResourceNode
from .resource_types import ResourceType


class Beehive(ResourceNode):
    """
    Decorative beehive entity that renders a PNG image.
    No behavior (generation/collection) — image-only.
    """

    GRID_WIDTH = 2
    GRID_HEIGHT = 2

    # Cache the loaded image surface to avoid reloading every frame
    _raw_image: Optional[pygame.Surface] = None

    def __init__(self, grid_position: pygame.Vector2):
        # Initialize as a ResourceNode with zero capacity and a dummy type
        # We introduce a distinct type to avoid reusing existing resource semantics.
        super().__init__(
            position=grid_position,
            capacity=0,
            generation_interval=9999999,  # effectively never generates
            resource_type=ResourceType.BEEHIVE  # Decorative type; no behavior
        )
        self.grid_width = Beehive.GRID_WIDTH
        self.grid_height = Beehive.GRID_HEIGHT

        # Precompute target pixel size for the sprite
        self.target_width_px = self.grid_width * config.GRID_CELL_SIZE
        self.target_height_px = self.grid_height * config.GRID_CELL_SIZE

        # Load image once (class cache)
        if Beehive._raw_image is None:
            Beehive._raw_image = self._load_image()

        # Prepare a scaled version matching our grid footprint
        self._scaled_image = self._scale_image(Beehive._raw_image)

    def _image_path(self) -> str:
        # Resolve path relative to this file to avoid cwd issues
        here = os.path.dirname(__file__)
        return os.path.normpath(os.path.join(here, "..", "assets", "images", "beehive.png"))

    def _load_image(self) -> pygame.Surface:
        path = self._image_path()
        try:
            img = pygame.image.load(path)
            # Convert for fast blitting with alpha
            return img.convert_alpha()
        except Exception:
            # If loading fails, fall back to a simple colored block placeholder
            placeholder = pygame.Surface((self.target_width_px, self.target_height_px), pygame.SRCALPHA)
            placeholder.fill((222, 184, 135, 255))  # burlywood
            return placeholder

    def _scale_image(self, img: pygame.Surface) -> pygame.Surface:
        try:
            # Scale to fully occupy the grid footprint
            return pygame.transform.smoothscale(img, (self.target_width_px, self.target_height_px))
        except Exception:
            return img

    def update(self, dt: float):
        # No behavior — decorative only
        pass

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, grid):
        # Top-left pixel based on grid position
        px = int(self.position.x * config.GRID_CELL_SIZE)
        py = int(self.position.y * config.GRID_CELL_SIZE)
        surface.blit(self._scaled_image, (px, py))
