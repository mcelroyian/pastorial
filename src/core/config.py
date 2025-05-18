# Game and Simulation Configuration

from ..resources.resource_types import ResourceType # Import for RESOURCE_VISUAL_COLORS

# Screen dimensions
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
SCREEN_SPAWN_MARGIN = 50  # Margin around the screen for spawning

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
BERRY_BUSH_CAPACITY = 23
BERRY_BUSH_GENERATION_INTERVAL = 6 # Resources per second
INITIAL_BERRY_BUSHES = 15
INITIAL_WHEAT_FIELD = 15

WHEAT_GENERATION_INTERVAL = 12 # How many simulation ticks to generate 1 unit of wheat
WHEAT_FIELD_CAPACITY = 11 # Max wheat in a field

# Resource Display Settings
RESOURCE_TEXT_COLOR = COLOR_WHITE
RESOURCE_FONT_SIZE = 16
# NODE_SIZE = GRID_CELL_SIZE # Optional: Use if node size differs from grid cell
# Agent Settings
INITIAL_AGENTS = 6
AGENT_SPEED = 5.0 # Grid units per second
DEFAULT_AGENT_INVENTORY_CAPACITY = 5 # Max items an agent can carry

# Agent Action Timings
DEFAULT_GATHERING_TIME = 2.0 # Seconds to gather a resource
DEFAULT_DELIVERY_TIME = 1.0  # Seconds to deliver a resource

# Resource Visuals (used by agent draw for carried items)
RESOURCE_VISUAL_COLORS = {
    ResourceType.BERRY: (220, 20, 60),   # Crimson for BERRY
    ResourceType.WHEAT: (218, 165, 32),  # Goldenrod for WHEAT
    ResourceType.FLOUR_POWDER: (211, 211, 211), # LightGrey for FLOUR_POWDER
    # Add other resource type colors here as they are defined
    # Example: ResourceType.WATER: (0, 191, 255) # Deep Sky Blue
}
# Task Generation Settings
MIN_BERRY_STOCK_LEVEL = 50
BERRY_GATHER_TASK_QUANTITY = 20
BERRY_GATHER_TASK_PRIORITY = 5
MAX_ACTIVE_BERRY_GATHER_TASKS = 3
# Wheat Task Generation Settings
MIN_WHEAT_STOCK_LEVEL = 40
WHEAT_GATHER_TASK_QUANTITY = 15
WHEAT_GATHER_TASK_PRIORITY = 4
MAX_ACTIVE_WHEAT_GATHER_TASKS = 2