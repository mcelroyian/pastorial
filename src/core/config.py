# Game and Simulation Configuration

from ..resources.resource_types import ResourceType # Import for RESOURCE_VISUAL_COLORS

# Screen dimensions
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
SCREEN_SPAWN_MARGIN = 50  # Margin around the screen for spawning

# Frame rate and timing
TARGET_FPS = 60

# Logging Settings
LOG_TO_FILE = False
LOG_FILE_PATH = "simulation.log" 
LOG_FILE_MODE = "w" # "w" for overwrite, "a" for append
LOG_TO_CONSOLE = False

# Grid settings
GRID_CELL_SIZE = 32
GRID_WIDTH = SCREEN_WIDTH // GRID_CELL_SIZE
GRID_HEIGHT = SCREEN_HEIGHT // GRID_CELL_SIZE
GRID_COLOR = (50, 50, 50)  # Dark grey

# Colors
COLOR_BLACK = (0, 0, 0)
COLOR_WHITE = (255, 255, 255)
DEBUG_TEXT_COLOR = COLOR_WHITE
PANEL_BACKGROUND_ALPHA = 128  # Value from 0 (transparent) to 255 (opaque)
 
# Resource Node Settings
BERRY_BUSH_COLOR = (0, 128, 0)  # Green
BERRY_BUSH_CAPACITY = 23
BERRY_BUSH_GENERATION_INTERVAL = 6 # Resources per second
INITIAL_BERRY_BUSHES = 15
INITIAL_WHEAT_FIELD = 15
DESIRED_NUM_MILLS = 2 # Default desired number of mills

WHEAT_GENERATION_INTERVAL = 12 # How many simulation ticks to generate 1 unit of wheat
WHEAT_FIELD_CAPACITY = 11 # Max wheat in a field

# Water Source (Well) Configuration
WELL_CAPACITY = 1_000_000
WELL_GENERATION_INTERVAL = 0.1
INITIAL_WELLS = 1 # The number of wells to spawn at startup

# Bakery Configuration
BAKERY_PROCESSING_SPEED = 180 # Ticks to produce bread
BAKERY_FLOUR_CAPACITY = 10
BAKERY_WATER_CAPACITY = 5
BAKERY_OUTPUT_CAPACITY = 10
BAKERY_COLOR = (139, 69, 19)  # SaddleBrown
BAKERY_PROCESSING_COLOR = (184, 115, 51) # A lighter brown
INITIAL_BAKERIES = 1

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
    ResourceType.WATER: (0, 128, 255), # A distinct blue color
    ResourceType.BREAD: (210, 180, 140), # Tan for BREAD
}
# Task Generation Settings
MIN_BERRY_STOCK_LEVEL = 50
BERRY_GATHER_TASK_QUANTITY = 20
BERRY_GATHER_TASK_PRIORITY = 5
MAX_ACTIVE_BERRY_GATHER_TASKS = 3
PROVISION_TASK_PRIORITY = 10 # Priority for tasks that deliver resources to bakeries
# Wheat Task Generation Settings
MIN_WHEAT_STOCK_LEVEL = 40
WHEAT_GATHER_TASK_QUANTITY = 15
WHEAT_GATHER_TASK_PRIORITY = 4
MAX_ACTIVE_WHEAT_GATHER_TASKS = 2
# Flour Processing Task Generation Settings (DeliverWheatToMillTask)
MIN_FLOUR_STOCK_LEVEL = 20
PROCESS_WHEAT_TASK_QUANTITY = 10 # Amount of Wheat to retrieve from storage for one task
PROCESS_WHEAT_TASK_PRIORITY = 75 # Higher than basic gathering
MAX_ACTIVE_PROCESS_WHEAT_TASKS = 2 # Max concurrent tasks to take wheat to mill

# Agent Action Timings (continued)
DEFAULT_COLLECTION_TIME_FROM_STORAGE = 1.5 # Seconds to collect from a storage point
DEFAULT_STORAGE_CAPACITY = 50
# Pathfinding Failure Recovery Settings
PATHFINDING_MAX_RETRIES = 3  # Max number of times to retry a failed path
PATHFINDING_RETRY_DELAY = 1.0  # Seconds to wait before a retry
PATHFINDING_NEW_TARGET_SEARCH_RADIUS = 5 # Max grid cells to search for an alternative walkable tile