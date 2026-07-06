# Plan 3: Factions & Ownership

**Audience:** An implementation agent working on this codebase.
**Prerequisite:** `plan-2-needs-economy.md` completed (agents eat, starve, die; sim clock; `SimMetrics`; balance test green).
**Followed by:** `plan-4-emergent-conflict.md`.

## Context & Motivation

The sim is currently one communal village: every agent serves one job board, every storage point accepts everyone. Emergent conflict needs *parties with separate interests*. This phase splits the world into factions — separate villages with their own agents, stockpiles, buildings, and economic planning — while wild resource nodes (bushes, fields, wells) remain unowned and shared.

The payoff at the end of this phase is **implicit competition without any combat code**: two villages drawing from the same finite wild nodes will already stress each other. Phase 4 only has to make that competition explicit.

**No combat, no theft, no aggression in this phase.** The deliverable is two (or N) fully independent, coexisting economies.

## Design decisions (make these, in this direction, unless the code strongly argues otherwise)

- **One `Simulation`, N `Faction` objects.** A `Faction` owns: id, name, color, a `TaskManager` (its job board), its agents (or a faction filter over `AgentManager`), references to its owned buildings, and its own metrics view.
- **Per-faction TaskManager** rather than one board with faction filters. The task-generation logic (`_generate_tasks_if_needed`) reads *faction* stock levels, not global ones. This is the natural seam — the class already encapsulates board + generation.
- **Shared world:** one `Grid`, one `ResourceManager` for wild nodes. Buildings (storage points, mills, bakeries) carry an `owner_faction_id`; wild nodes carry `owner_faction_id = None`.
- **Ownership is a field, not a subclass.** Suggested: `Ownable` mixin or plain attribute `owner_faction_id: Optional[int]` on `StoragePoint`, `ProcessingStation`, `ResourceNode`, `Agent`. Default `None` = neutral/wild.

---

## Task 1: Faction core + ownership tags

### What to do
- `src/factions/faction.py`: `Faction` dataclass-ish (id, name, color, home_region: Rect in grid coords, task_manager, agent_ids or agent list, member/building registries as needed).
- `Simulation` gains `self.factions: List[Faction]` and constructs `config.NUM_FACTIONS` (default 2) of them. Faction definitions (colors, names, spawn regions) in config.
- Add `owner_faction_id` to `Agent`, `StoragePoint`, `ProcessingStation`, `ResourceNode` (default None).
- `SimMetrics`: key relevant counters by faction id (deaths, production, consumption, stock).

### Verify
- Existing tests still pass with `NUM_FACTIONS = 1` (backward-compat path: one faction should reproduce today's behavior — this is the regression guard for the whole phase; consider parametrizing the smoke test over 1 and 2 factions).

## Task 2: Territorial spawning

### Why
Spawn placement is currently uniform across the whole grid. Factions need spatial identity: a home region containing their buildings and agents, with wild nodes scattered between/around. Distance is what will later make "their berries are closer than ours" a real strategic fact.

### What to do
- Give each faction a home region (e.g., faction 0 west third, faction 1 east third of the grid; center strip is wilderness). Configurable rects.
- Refactor `Simulation._spawn_entity` to accept an optional region constraint (`_find_available_spawn_points` gains a bounds parameter).
- Per faction, spawn within its region: agents, 1 berry/wheat storage, 1 flour/bread storage, 1 mill, 1 bakery, 1 well — set `owner_faction_id` on each. (Split the current `INITIAL_*` counts per-faction in config, e.g. `PER_FACTION_MILLS = 1`.)
- Spawn wild nodes (berry bushes, wheat fields) across the whole map or biased to the neutral middle — **deliberately make total wild nodes NOT scale with faction count** (keep near current totals). Finite shared supply is the point.
- Rendering: tint agents by faction color (behavior state can become a ring/outline instead of fill, or vice versa — implementer's choice, but both faction and behavior must stay readable); tint owned buildings (small colored border is enough).

### Verify
- Visual: two distinct villages with a wild middle; colors legible.
- Test: every spawned building/agent has the correct `owner_faction_id`; each faction's buildings lie within its region.

## Task 3: Faction-scoped task system

### Why
This is the heart of the phase. Each faction must plan for itself using its own stock levels.

### What to do
- Each `Faction` gets its own `TaskManager`. Agents call *their faction's* manager in `acquire_task_or_perform_idle_action` (agent needs a `faction` or `task_manager_ref` wired at spawn — it already holds `task_manager_ref`, so mostly a wiring change in `Simulation`/`AgentManager.create_agent`).
- `_generate_tasks_if_needed` and stock queries (`get_global_resource_quantity`) become faction-scoped: sum only storage points with matching `owner_faction_id`. Add `ResourceManager.get_faction_resource_quantity(faction_id, resource_type)` and similar filtered accessors (`storage_points_for(faction_id)`).
- **Delivery targeting:** `GatherAndDeliverTask.prepare` / `DeliverWheatToMillTask.prepare` currently pick nearest dropoff/source from *all* storage/stations. They must filter to the acting agent's faction (own buildings only). Same for `EatTask` bread lookup. Wild nodes remain fair game for gathering by anyone.
- **Storage enforcement:** `StoragePoint.can_accept` / reservation methods should reject actors from other factions (add an optional `faction_id` arg checked against `owner_faction_id`; `None`-owned storage accepts anyone). Enforce at the storage layer, not just in task `prepare` — phase 4's theft mechanic will *bypass* this check explicitly, so the check must exist as a real gate.
- Mind the claim system: `ResourceNode.claim` already prevents two tasks sharing a node — cross-faction claiming of wild nodes is the first competition mechanic and needs **no new code**, just a test proving it works cross-faction.

### Verify
- Test: 2 factions, seeded, long run — each faction independently produces and consumes bread (per-faction metrics both nonzero).
- Test: faction A agent never delivers to / withdraws from faction B storage (assert via metrics or storage transaction log).
- Test: a wild node claimed by a faction-A task is not claimable by a faction-B task until released.
- Test: `StoragePoint` rejects a reservation attempt with mismatched faction id.

## Task 4: Scarcity scenario support

### Why
Phase 4 needs the ability to construct asymmetric worlds ("faction A rich, faction B poor") for its emergence tests. Building scenario plumbing now, while touching spawn code anyway, is cheap.

### What to do
- Allow `Simulation(seed=, scenario=)` where scenario is a small config-override object/dict (counts of wild nodes per region, per-faction agent counts, initial stock injections into storage). Keep it simple — a dataclass with defaults mirroring config is fine.
- Provide 3 canned scenarios in `src/core/scenarios.py`: `DEFAULT` (balanced), `SCARCITY` (wild nodes halved), `ASYMMETRIC` (faction B's region has few/no wild nodes and fewer bushes overall).
- Extend `scripts/balance_report.py` to accept `--scenario` and print per-faction tables.

### Verify
- Test: `ASYMMETRIC` scenario runs headless; faction B's food metrics are measurably worse than A's (don't assert deaths — just directional inequality; exact tuning is phase 4's job).

## Task 5: Balance & polish pass

### What to do
- Tune per-faction config so `DEFAULT` with 2 factions passes the survival bar (≥80% agents alive over 20 sim-minutes, both factions).
- Update `test_balance.py` to run the 2-faction default.
- Update `docs/balance-notes.md`.
- Manual visual pass: `python main.py` shows two villages working in parallel; inspector panel shows agent faction.

---

## Ground rules

- No aggression mechanics of any kind — resist the temptation; phase 4 depends on this phase being a stable, *peaceful* baseline.
- Keep `NUM_FACTIONS = 1` working (regression path).
- Ownership checks live in the owned objects (storage/station), not only in task code.
- Sim time only; pygbag constraints unchanged; commit per task with green `pytest`.

## Definition of done

1. N-faction sim with territorial villages; buildings/agents owned; wild nodes neutral and shared.
2. Fully independent per-faction economies: own job boards, own stock-driven task generation, own-storage-only delivery, faction-gated storage access.
3. Cross-faction wild-node claim contention proven by test.
4. Scenario system with `DEFAULT` / `SCARCITY` / `ASYMMETRIC`; per-faction metrics and balance report.
5. All tests green (1- and 2-faction); 2-faction default is a stable peaceful baseline.
