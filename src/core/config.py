# Game and Simulation Configuration

from ..resources.resource_types import ResourceType # Import for RESOURCE_VISUAL_COLORS

# Screen dimensions
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720

# Frame rate and timing
TARGET_FPS = 60

# Grid settings
GRID_CELL_SIZE = 32
GRID_COLOR = (50, 50, 50)  # Dark grey

# Colors
COLOR_BLACK = (0, 0, 0)
COLOR_WHITE = (255, 255, 255)
DEBUG_TEXT_COLOR = COLOR_WHITE

# Resource Node Settings
BERRY_BUSH_COLOR = (0, 128, 0)  # Green
BERRY_BUSH_CAPACITY = 100
BERRY_BUSH_GENERATION_RATE = 5.0 # Resources per second
INITIAL_BERRY_BUSHES = 10

# Resource Display Settings
RESOURCE_TEXT_COLOR = COLOR_WHITE
RESOURCE_FONT_SIZE = 16
# NODE_SIZE = GRID_CELL_SIZE # Optional: Use if node size differs from grid cell
# Agent Settings
AGENT_SPEED = 5.0 # Grid units per second
DEFAULT_AGENT_INVENTORY_CAPACITY = 5 # Max items an agent can carry

# Agent Action Timings
DEFAULT_GATHERING_TIME = 2.0 # Seconds to gather a resource
DEFAULT_DELIVERY_TIME = 1.0  # Seconds to deliver a resource

# Resource Visuals (used by agent draw for carried items)
RESOURCE_VISUAL_COLORS = {
    ResourceType.BERRY: (220, 20, 60),   # Crimson for BERRY
    ResourceType.WHEAT: (218, 165, 32),  # Goldenrod for WHEAT
    # Add other resource type colors here as they are defined
    # Example: ResourceType.WATER: (0, 191, 255) # Deep Sky Blue
}