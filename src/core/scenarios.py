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
    per_faction_agents: Optional[int] = None  # overrides config.PER_FACTION_AGENTS (all factions)
    # Per-faction initial bread list, indexed by faction_id.  None = use config default.
    faction_initial_bread: Optional[List[int]] = None
    # Per-faction bakery count list, indexed by faction_id — overrides config.PER_FACTION_BAKERIES.
    # A faction with 0 bakeries can mill flour but never convert it to bread, giving it a
    # persistent, deterministic production handicap (Plan 4 Task 3: bumping agent count instead
    # was tried first, but it strains factions via random contention on the *shared* wild-node
    # pool, which swamps the deliberate initial-bread asymmetry and produces non-directional
    # raiding — see docs/plan-4-progress.md). None = use config.PER_FACTION_BAKERIES.
    faction_bakeries: Optional[List[int]] = None
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
    faction_bakeries=[1, 0],  # faction 1 has no bakery — Plan 4 Task 3 empirical tuning: with
                              # normal production the initial bread gap self-corrects too fast
                              # for real desperation (and thus raiding) to emerge. This gives
                              # faction 1 a persistent, deterministic handicap (can mill flour
                              # but never bake bread) instead of a transient one, so it reliably
                              # runs down toward its initial 2 bread over time regardless of
                              # seed — unlike bumping agent count, which strains both factions
                              # via random contention on the *shared* wild-node pool and erases
                              # directionality (observed: raids became ~symmetric).
    description="Faction 1 (east/Ashford) starts resource-poor; directional inequality expected",
)
