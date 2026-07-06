# Balance Notes — Needs Economy (Plan 2)

Reference run: seed=42, 20 sim-minutes, `balance_report.py`.

## Tuned constants (src/core/config.py)

| Constant | Value | Rationale |
|---|---|---|
| `HUNGER_DECAY_PER_SECOND` | `0.002` | Full hunger → zero in 500 sim-s (~8 min). Leaves time for agents to eat before starving. |
| `HUNGER_SEEK_FOOD_THRESHOLD` | `0.4` | Agent self-generates EatTask at 40% hunger — enough lead time to walk to storage. |
| `HUNGER_CRITICAL_THRESHOLD` | `0.15` | Agent abandons current job and eats at 15% — emergency override. |
| `HUNGER_RESTORED_PER_BREAD` | `0.6` | One bread = +60% hunger. Needs ~2 bread from empty; 1 bread from threshold. |
| `STARVATION_GRACE_PERIOD` | `60.0 s` | 60 s at hunger=0 before death — enough for one EatTask round-trip. |
| `EAT_RETRY_COOLDOWN` | `5.0 s` | Wait 5 s before retrying if no bread — avoids tight busy-loop. |
| `INITIAL_BREAD_STOCK` | `24` | 4 per agent; sustains all agents for ~20 min before bakery production ramps. |
| `DEFAULT_STORAGE_CAPACITY` | `100` | Doubled from 50 so berry/wheat gather tasks can always reserve space. |
| `INITIAL_BAKERY_FLOUR` | `4` | 2 bread worth of flour so bakery starts producing on tick 1. |
| `INITIAL_BAKERY_WATER` | `2` | 2 bread worth of water matching initial flour. |

## Reference run results (seed=42, 20 min)

```
Agents alive:  6 / 6   (100%)
Deaths:        0
BREAD consumed: 18
BREAD in stock: 12
Water gathered: 4
```

## Key design decisions

**Pre-seeding**: `INITIAL_BREAD_STOCK = 24` bridges the gap while wheat gathering → milling → flour → baking → auto-distribute completes its first cycle (takes ~3–5 min).

**Storage capacity = 100**: With `MIN_BERRY_STOCK_LEVEL = 50`, the original capacity of 50 left zero headroom for gather tasks to reserve space. Doubling it collapses the 100k+ task failure cascade to near-zero.

**EatTask never re-posted**: Failed EatTask (no bread found) is discarded, not re-posted to the job board. Agents retry via `eat_retry_timer` cooldown instead.

**`_auto_distribute_outputs` extended**: Bakery output bread is auto-pushed to bread storage every tick. Without this, bread sat in the bakery's `current_output_quantity` dict and was invisible to EatTask searches.

**`GatherAndDeliverTask.cleanup` guard**: Processing stations (Bakery) don't implement `release_reservation`. The cleanup guard (`hasattr(..., 'release_reservation')`) prevents crashes when water-delivery tasks are abandoned.
