# Game and Simulation Configuration

from ..resources.resource_types import ResourceType # Import for RESOURCE_VISUAL_COLORS

# Faction settings
NUM_FACTIONS = 2
FACTION_CONFIGS = [
    {"name": "Redwood", "color": (210, 60, 60)},   # faction 0 — west, red
    {"name": "Ashford", "color": (60, 110, 210)},   # faction 1 — east, blue
]
PER_FACTION_AGENTS = 3
PER_FACTION_MILLS = 1
PER_FACTION_BAKERIES = 1
PER_FACTION_WELLS = 1
PER_FACTION_INITIAL_BREAD = 12  # pre-seeded bread per faction (=4 per agent)
WILD_BERRY_BUSHES = 15          # shared wild nodes — deliberately not scaled with faction count
WILD_WHEAT_FIELDS = 15
WILD_BEEHIVES = 1

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
COLOR_GRAY = (30, 30, 30)

# Inspector Panel Settings
INSPECTOR_PANEL_WIDTH = 300

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
INITIAL_BEEHIVES = 1

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

# --- UTILITY WEIGHTS (Plan 4 Task 1 — main tuning surface for the emergence phase) ---
# score = base_value * urgency(stock_ratio) - distance_cost - risk_cost
UTILITY_URGENCY_EXPONENT = 2.0          # (1 - stock/target)^exponent: >1 concentrates urgency
                                         # near true scarcity; 1.0 = linear ramp.
UTILITY_BASE_VALUE_BERRY = 50.0         # replaces BERRY_GATHER_TASK_PRIORITY as scoring anchor
UTILITY_BASE_VALUE_WHEAT = 40.0         # replaces WHEAT_GATHER_TASK_PRIORITY
UTILITY_BASE_VALUE_PROCESS_WHEAT = 750.0  # replaces PROCESS_WHEAT_TASK_PRIORITY; kept >> gather
                                           # base values so processing still outranks gathering
                                           # at comparable urgency, same as today's static gap.
UTILITY_BASE_VALUE_PROVISION = 100.0    # replaces PROVISION_TASK_PRIORITY (station-recipe fallback,
                                         # e.g. WATER->Bakery — no meaningful global stock target)
UTILITY_DISTANCE_WEIGHT = 1.0           # multiplies raw grid-unit distance into a score cost
UTILITY_CONSUMPTION_WINDOW_SECONDS = 300.0  # rolling window for SimMetrics recent-rate queries.
                                             # Widened from 60s during Task 3 tuning: with only
                                             # 3 agents/faction eating roughly once per ~300s
                                             # each, a 60s window frequently contains zero eat
                                             # events even under real scarcity, causing
                                             # food_deficit_seconds to fall back to its "abundant"
                                             # sentinel (see FactionContext.compute_food_deficit_
                                             # seconds) and masking genuine desperation from the
                                             # raid scorer. 300s matches SimMetrics's own
                                             # _EVENT_RETENTION_SECONDS ceiling.
FOOD_DEFICIT_SECONDS_CAP = 1e6          # sentinel for "abundant" when consumption rate is ~0
UTILITY_CONTENTION_WEIGHT = 2.0         # multiplies a node's contention_pressure into distance_cost

# --- CONTENTION (Plan 4 Task 2 — contested wild resources) ---
CONTENTION_BUMP_PER_DENIAL = 8.0        # added to a node's pressure on each cross-faction claim denial
CONTENTION_PRESSURE_CAP = 40.0          # ceiling; ~5 rapid denials saturate a node
CONTENTION_DECAY_RATE = 1.0             # pressure units/sec removed every tick (full decay from cap: 40s)
EVENT_LOG_MAX_SIZE = 500                # ring-buffer size for src/core/events.py

# --- RAID (Plan 4 Task 3 — theft) ---
# raid_score = UTILITY_BASE_VALUE_RAID * food_deficit_urgency(deficit_seconds) * haul_factor
#              - distance_cost - risk_cost - UTILITY_RAID_PEACE_BIAS
# Values below are empirically tuned (like Task 2's CONTENTION constants) against
# tests/test_theft.py's ASYMMETRIC/DEFAULT scenario tests, not derived analytically — see
# docs/plan-4-progress.md for the tuning process (widened UTILITY_CONSUMPTION_WINDOW_SECONDS,
# scenarios.ASYMMETRIC's faction_bakeries lever, and these three constants all had to move
# together before ASYMMETRIC produced directional raids without DEFAULT producing any).
UTILITY_BASE_VALUE_RAID = 100.0         # comparable order of magnitude to BERRY/WHEAT base values —
                                         # raiding isn't a "super task"; UTILITY_RAID_PEACE_BIAS is
                                         # what keeps it strictly dominated in ordinary conditions.
RAID_FOOD_DEFICIT_HORIZON_SECONDS = 500.0  # food_deficit_seconds at/below this -> urgency saturates
                                            # toward 1.0 (steep ramp, see task._food_deficit_urgency).
                                            # DEFAULT's observed deficit floor is ~1200s even under
                                            # this widened consumption window — comfortable margin.
UTILITY_RAID_PEACE_BIAS = 20.0          # constant handicap making raids strictly worse than a viable
                                         # peaceful task under normal conditions — THE tuning constant
                                         # for this rung; get this inequality right per the plan doc.
RAID_STEAL_TIME_MULTIPLIER = 1.5        # steal Interact duration = DEFAULT_COLLECTION_TIME_FROM_STORAGE * this
MAX_ACTIVE_STEAL_TASKS = 1              # cap on concurrent pending/assigned raid tasks per faction —
                                         # generation is unconditional (not scarcity-gated); scoring
                                         # alone decides whether the task is ever picked.
STEAL_TASK_QUANTITY = DEFAULT_AGENT_INVENTORY_CAPACITY  # attempt a full single-trip carry per raid

# Agent Action Timings (continued)
DEFAULT_COLLECTION_TIME_FROM_STORAGE = 1.5 # Seconds to collect from a storage point
DEFAULT_STORAGE_CAPACITY = 100
INITIAL_BAKERY_FLOUR = 4   # pre-stocked flour so bakery can start producing immediately
INITIAL_BAKERY_WATER = 2   # pre-stocked water so bakery can start producing immediately
# Hunger / Needs Settings
HUNGER_DECAY_PER_SECOND = 0.002        # full → starving in ~500 sim-seconds (~8 min)
HUNGER_SEEK_FOOD_THRESHOLD = 0.4       # agent starts self-generating EatTask
HUNGER_CRITICAL_THRESHOLD = 0.15       # agent drops current task to eat
HUNGER_RESTORED_PER_BREAD = 0.6        # hunger restored by eating one bread
STARVATION_GRACE_PERIOD = 60.0         # sim-seconds at hunger==0 before death
EAT_RETRY_COOLDOWN = 5.0               # sim-seconds before retrying when no bread
INITIAL_BREAD_STOCK = 24               # pre-seeded bread in storage at startup (4 per agent)

# Pathfinding Failure Recovery Settings
PATHFINDING_MAX_RETRIES = 3  # Max number of times to retry a failed path
PATHFINDING_RETRY_DELAY = 1.0  # Seconds to wait before a retry
PATHFINDING_NEW_TARGET_SEARCH_RADIUS = 5 # Max grid cells to search for an alternative walkable tile
