"""Canned simulation scenarios for constructing asymmetric/scarcity worlds."""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Scenario:
    """Config-override dataclass passed to Simulation(scenario=...).

    Any field left at its default means "use whatever config.py says".
    """
    wild_berry_bushes: Optional[int] = None   # overrides config.WILD_BERRY_BUSHES
    wild_wheat_fields: Optional[int] = None   # overrides config.WILD_WHEAT_FIELDS
    per_faction_agents: Optional[int] = None  # overrides config.PER_FACTION_AGENTS
    # Per-faction initial bread list, indexed by faction_id.  None = use config default.
    faction_initial_bread: Optional[List[int]] = None
    description: str = ""


# ---------------------------------------------------------------------------
# Canned scenarios
# ---------------------------------------------------------------------------

DEFAULT = Scenario(description="Balanced two-faction world (mirrors config defaults)")

SCARCITY = Scenario(
    wild_berry_bushes=7,
    wild_wheat_fields=7,
    description="Shared wild resources halved — both factions feel the squeeze",
)

ASYMMETRIC = Scenario(
    wild_berry_bushes=5,
    wild_wheat_fields=5,
    faction_initial_bread=[12, 2],
    description="Faction 1 (east/Ashford) starts resource-poor; directional inequality expected",
)
