# Plan 4 (Emergent Conflict) — Progress Handoff

**Plan doc:** `docs/plan-4-emergent-conflict.md` — read Task 4 there before continuing.
**Prerequisite docs:** `docs/plan-3-factions.md` (factions, done), `docs/balance-notes.md` (tuning history).

**Branch:** `main` — work is uncommitted as of this handoff (Task 3 implementation complete,
tests green, not yet committed — confirm with the user before committing/pushing).

**Start reading here, then the plan doc for the Task 4 spec.**

---

## Status at a Glance

| Task | Description | Status |
|------|-------------|--------|
| Task 1 | Utility-based task scoring (the emergence engine) | ✅ Done (`b1f93d6`) |
| Task 2 | Rung 1 — Contested wild resources (no violence) | ✅ Done (`b4063af`) |
| Task 3 | Rung 2 — Theft (`StealFromStorageTask`) | ✅ Done (uncommitted) |
| Task 4 | Rung 3 — Defense (`GuardTask`, threat response) | 🔴 **Next up** — not started |
| Task 5 | Rung 4 — Combat | ⬜ Not started |
| Task 6 | Tuning & the emergence report | ⬜ Not started |

Full test suite: **71 passed** (`pytest` from repo root; 60 baseline + 11 new for Task 3).
Peaceful baseline (`tests/test_balance.py`, `tests/test_factions.py`) is the regression gate —
must stay green through every future rung.

---

## What Was Done

### Task 1 — Utility-based task scoring (`b1f93d6`)

Replaced the static integer `Task.priority` with a continuously-recomputed score:
`score = base_value * urgency(stock_ratio) - distance_cost - risk_cost`.

- **New `src/factions/context.py`** — `FactionContext` dataclass, built fresh every 5s
  planning tick (`TaskManager._build_faction_context()`): stock by resource type,
  consumption rate, agents alive, recent deaths, `food_deficit_seconds` (the master
  scarcity signal), home-region centroid, and an inert `threat_level=0.0` placeholder for
  Task 4.
- **`SimMetrics`** gained rolling-window deques (`_consumption_events`, `_death_events`)
  feeding `recent_consumption_rate()` / `recent_deaths()` — gross consumption, not
  net-of-production, since a faction's stock can look flat while it's actually eating a lot.
- **`Task.compute_score(faction_ctx, resource_manager)`** — concrete default on the base
  class (`return float(self.priority)`, so unmigrated types like `PatrolTask` are
  unaffected), real implementations on `GatherAndDeliverTask` and `DeliverWheatToMillTask`.
  `risk_cost` exists as a named term, wired to `0.0` — a real line in the formula, not an
  omission, so Task 3/4 can activate it without reshaping anything.
- **`priority` was repurposed in-place** as the cached live score (not a separate `score`
  field) — a deliberate choice to avoid touching every debug log / `get_description()` call
  site that already reads `task.priority`. Type is now `float`.
- **`TaskManager.update()`** reuses the existing 5s generation cadence for a new
  `_rescore_pending_tasks(ctx)` step — no second timer.
- **Config**: new `UTILITY WEIGHTS` section in `src/core/config.py` — the main tuning
  surface for all of Plan 4.
- **Tests**: `tests/test_task_scoring.py` (3 tests) — relative score ordering + rescore-cadence
  proof, not absolute numbers, per the doc's own instruction.

### Task 2 — Contested wild resources (`b4063af`)

Wild-node claim denials between rival factions now generate observable "contention
pressure" that feeds back into scoring.

- **`ResourceNode`** (`src/resources/node.py`) gained faction-aware claims —
  `claim(agent_id, task_id, faction_id=None)` stores `claimed_by_faction_id` (backward
  compatible, only prod call site is `GatherAndDeliverTask.prepare()`) — plus a decaying
  `contention_pressure: float`, bumped via `add_contention()`, decayed every tick inside
  the node's existing `update(dt)`.
- **New `src/core/events.py`** — `EventLog`/`SimEvent`: a sim-wide bounded ring buffer
  (`deque(maxlen=500)`), owned by `Simulation`, timestamped once/tick
  (`events.update(sim_time)`, mirrors `SimMetrics._current_sim_time`'s idiom). This is the
  **sole** record of contention events — deliberately no parallel `SimMetrics` counter, to
  avoid two sources of truth. It's also the intended input for Task 3's threat perception.
- **Wiring pattern**: `resource_manager.events = self.events`, a duck-typed
  post-construction attribute (same pattern as `tm.metrics = self.metrics` from Task 1) —
  avoids changing `Task.prepare()`'s signature across all 4 subclasses just for the one
  (`GatherAndDeliverTask`) that needs it. Read via `getattr(resource_manager, 'events', None)`.
- **Node-selection loop** (`GatherAndDeliverTask.prepare()`): only the agent's *first
  viable candidate* (nearest node with stock) counts as a contention signal if it's held by
  a rival faction — narrowing from "every already-claimed node encountered while scanning"
  to "was my *preferred* choice specifically taken by the enemy" was needed to keep the
  DEFAULT-vs-SCARCITY signal from saturating identically.
- **Score integration**: `_nearest_distance_cost` widened to take `(position,
  contention_pressure)` pairs + a `contention_weight` param (default `0.0`).
- **UI**: `TaskStatusDisplay` gained a "Recent Events" panel section (`events.recent(5)`).
- **Tests**: `tests/test_events.py` (3 tests), including a seeded statistical scenario test.

### Task 3 — Theft / `StealFromStorageTask` (uncommitted)

First deliberately hostile task: an agent walks to an **enemy** faction's storage, steals
bread (bypassing the Plan 3 faction gate via an explicit bypass), carries it home, deposits
it — purely emergent, gated only by utility scoring, no `if faction.at_war` anywhere.

- **`StoragePoint.reserve_for_pickup`** (`src/resources/storage_point.py`) gained a
  `force: bool = False` param that skips the `_faction_allowed` check when `True`. This is
  the *entire* bypass mechanism — `collect_reserved_pickup`/`release_pickup_reservation`
  were never faction-gated in the first place, so nothing downstream needed to change.
  Default-`False` keeps every pre-existing call site (`EatTask`, `DeliverWheatToMillTask`)
  provably untouched (regression-tested directly in `tests/test_storage_point.py`).
- **`StealFromStorageTask`** (`src/tasks/task.py`, placed after `DeliverWheatToMillTask` —
  its closer structural template) follows the same declarative `MoveToStep`/`InteractStep`
  pattern as every other task: reserve pickup at the richest enemy storage holding BREAD
  (`force=True`) → move → `InteractStep("STEAL", ...)` → move home → deposit via the
  completely normal `reserve_space`/`commit_reservation_to_storage` path (depositing into
  your *own* storage needs no bypass). Emits a `theft(faction_id=raider,
  other_faction_id=victim, position, resource_type, detail=amount)` event to the Task 2
  `EventLog` at the moment bread is actually collected — same "EventLog is the sole record"
  discipline as `claim_contention`, no parallel `SimMetrics` counter.
- **Scoring** (`StealFromStorageTask.compute_score`): `UTILITY_BASE_VALUE_RAID *
  food_deficit_urgency(deficit_seconds) * haul_factor - distance_cost - risk_cost -
  UTILITY_RAID_PEACE_BIAS`. `food_deficit_urgency` (new helper in `task.py`) is a steep 0→1
  ramp as `food_deficit_seconds` approaches 0, reusing `UTILITY_URGENCY_EXPONENT` as its
  shape parameter, keyed off a new `RAID_FOOD_DEFICIT_HORIZON_SECONDS` config constant.
  `haul_factor` is the richest reachable enemy storage's actual BREAD stock (perfect
  information, per the doc), **capped at `DEFAULT_AGENT_INVENTORY_CAPACITY`** so one large
  enemy stockpile can't make `peace_bias` untunable. `risk_cost` stays `0.0` (Task 4 wires it).
- **Generation** (`TaskManager._generate_tasks_if_needed`): unconditional, capped at
  `MAX_ACTIVE_STEAL_TASKS = 1` pending/assigned raid task per faction — no scarcity gate on
  the generation side; scoring alone decides whether it's ever picked.
- **Critical bug found and fixed during implementation — a scoring floor in
  `assign_task_to_agent`.** A persistently-present, almost-always-preparable raid task (enemy
  storage nearly always has *some* bread) became a "fallback of last resort" whenever a
  higher-scored peaceful task's `prepare()` transiently failed (e.g. a wild node momentarily
  claimed by another agent) — `assign_task_to_agent`'s loop just falls through to the next
  candidate on `prepare()` failure, so a deeply-negative-scored-but-always-succeeding task
  would eventually get reached regardless of how negative `peace_bias` made its score. This
  showed up as real theft events in the `DEFAULT` scenario during a routine regression run
  (`tests/test_events.py`'s contention test started failing — a knock-on effect, not a direct
  assertion on theft). **Fix**: `assign_task_to_agent` now `break`s out of its
  (score-descending-sorted) candidate loop the moment it hits a task with `priority <= 0` —
  doing nothing beats a net-negative action. This is generic (applies to any current or future
  task type, not raid-specific) and is *the* mechanism that makes `peace_bias` actually mean
  something; without it, no amount of tuning `peace_bias` could have kept raiding out of
  `DEFAULT`, because the raid task would always be reachable as a fallback.
- **Empirical tuning — the food_deficit_seconds signal was too spiky to use as-is.** With
  only 3-6 agents per faction eating infrequently (~once per 300s each), a 60s rolling
  consumption window frequently contained zero eat events even under real scarcity, so
  `FactionContext.food_deficit_seconds` kept falling back to its "abundant" sentinel
  (`FOOD_DEFICIT_SECONDS_CAP`) regardless of actual stock level. Fixed by widening
  `UTILITY_CONSUMPTION_WINDOW_SECONDS` from 60s to 300s (matches `SimMetrics`'s own
  `_EVENT_RETENTION_SECONDS` ceiling) — this is a Task 1 constant, but Task 3 is the first
  real consumer of `food_deficit_seconds`, so its noisiness had never been exercised before.
  Separately, `scenarios.ASYMMETRIC`'s original tuning (initial-bread gap only) self-corrected
  too fast under normal production for real desperation to build. **Tried and rejected**:
  bumping `per_faction_agents` for both factions — strains both equally via random contention
  on the *shared* wild-node pool, which swamped the deliberate initial-bread asymmetry and
  produced non-directional (roughly 50/50) raiding. **What worked**: a new
  `Scenario.faction_bakeries` field (`src/core/scenarios.py`, wired into
  `Simulation._spawn_faction_buildings`) — `ASYMMETRIC` now gives faction 1 zero bakeries
  (`faction_bakeries=[1, 0]`), a *persistent* production handicap (can mill flour, can never
  bake bread) instead of a transient one, so it reliably runs down over time regardless of
  seed. Final tuned constants: `UTILITY_BASE_VALUE_RAID=100.0`,
  `RAID_FOOD_DEFICIT_HORIZON_SECONDS=500.0`, `UTILITY_RAID_PEACE_BIAS=20.0` — verified against
  `DEFAULT`'s observed deficit floor of ~1200s (comfortable margin) and `ASYMMETRIC` producing
  exactly one directional raid (faction 1 → faction 0, zero reverse) in 5/6 seeds tested.
- **Tests**: `tests/test_storage_point.py` (+3: normal gate, force bypass, force-omitted
  regression), `tests/test_task_scoring_raid.py` (5: abundance-low-score, disqualified
  sentinel when no enemy bread, monotonic ramp, urgency-shape unit test, severe-deficit
  crossover vs. gather), `tests/test_theft.py` (3: `ASYMMETRIC` directional raids over 3
  seeds, `DEFAULT` zero raids over 3 seeds, theft event field sanity).
- **Manual sanity**: `main.py` has no CLI scenario switch (hardcodes `Simulation()` =
  `DEFAULT` in `GameLoop.__init__`), so a live visual check of `ASYMMETRIC` raiding wasn't
  possible without a temporary code change. Verified DEFAULT renders/runs cleanly via the
  `run` skill (no crashes, task board and event panel look normal), and verified
  `ASYMMETRIC`'s raid behavior headlessly via deterministic seeded event-log traces (bread
  visibly transfers faction 0 → faction 1's storage at the same tick a `theft` event fires).
  If a live visual check matters going forward, worth adding a `--scenario` CLI flag to
  `main.py`/`GameLoop` in a later task.

---

## What Comes Next

### Task 4 — Rung 3: Defense (`GuardTask`, threat response)

Per `docs/plan-4-emergent-conflict.md`, Task 4 section:

- **`FactionContext.threat_level`**: currently inert (`0.0`), needs to become a decaying
  accumulator fed by hostility events against the faction — theft (now real, from Task 3)
  weighted high, contention (Task 2) weighted low. Decay over sim-minutes so peace can
  return. The `EventLog` (`src/core/events.py`) already has everything needed to compute
  this: `theft` events carry `other_faction_id` = victim, so a faction can query "how much
  have I been victimized recently" directly from the event log.
- **`GuardTask`**: agent moves to own storage/building and loiters — reuse/extend
  `PatrolTask`'s waypoint pattern. Score scales with `threat_level` and stock worth
  protecting; competes against economic *and raid* tasks on the same board (guards don't
  gather).
- **Guard effect (nonviolent v1)**: a raider's `InteractStep("STEAL", ...)` should fail if
  ≥N enemy agents are within `config.GUARD_RADIUS` of the target when the steal begins — add
  a proximity check inside `StealFromStorageTask._on_steal_complete` (or a new step
  precondition). Failed raid should still emit an event and raise the raider's perceived
  risk of that target — this is exactly the `risk_cost` term already wired to `0.0` in both
  `GatherAndDeliverTask.compute_score` (from Task 1) and `StealFromStorageTask.compute_score`
  (from Task 3): Task 4 activates it, no new term needed.
- **Requires** `AgentManager.get_agents_near(pos, radius, faction_id=...)` — doesn't exist
  yet. Linear scan is fine at current scale (~12 agents total); leave a comment, not an
  optimization.

### Before starting Task 4

- Re-run `pytest` from a clean checkout to confirm this handoff's state is still green (71
  passed) before layering more on top.
- Read the "Critical bug found and fixed" note above (`assign_task_to_agent`'s score-floor
  `break`) before adding `GuardTask` to the board — it's a generic mechanism that will also
  govern whether guarding ever gets picked, not just raiding.
- `UTILITY_CONSUMPTION_WINDOW_SECONDS` is now 300s (was 60s) — if Task 4's `threat_level`
  decay or any other new signal depends on shorter-window responsiveness, this is the
  constant to revisit.

---

## Key Architecture Notes for Future Rungs

- **Wiring pattern for new sim-wide systems reaching into `Task.prepare()`**: don't change
  `Task.prepare(agent, resource_manager)`'s signature. Attach the new system as a
  duck-typed attribute on `resource_manager` (or wherever `prepare()` already has a
  reference), set once post-construction in `Simulation.__init__`, read via
  `getattr(x, 'attr_name', None)` with a None-guard. Established in Task 1
  (`tm.metrics`/`tm.agent_manager_ref`) and Task 2 (`resource_manager.events`).
- **Every accumulator must decay, and decay should be lazy/query-time or piggyback an
  existing per-tick hook** — `SimMetrics`'s rolling windows prune lazily at query time;
  `ResourceNode.contention_pressure` decays inside the node's existing `update(dt)` (no new
  timer). Look for an existing tick hook before adding a new one. `threat_level` (Task 4)
  should follow the same discipline.
- **`FactionContext` and `EventLog` are the two extension points** every later rung reads
  from — `threat_level` on `FactionContext` is still inert/generic today (Task 3 didn't touch
  it), built so Task 4 adds *behavior*, not new *shape*.
- **Regression gate**: `tests/test_balance.py` (20 sim-minute `DEFAULT` run, ≥80% survival)
  and `tests/test_factions.py` must stay green after every rung — run them explicitly, not
  just the new rung's own tests, before considering a task done.
- **Statistical/scenario tests need empirical tuning, not guessed thresholds** — this was
  true for Task 2's contention test and *much* more true for Task 3's raid test: the
  `food_deficit_seconds` master-scarcity signal needed a widened consumption window to be
  usable at all, and `scenarios.ASYMMETRIC` needed a persistent (not transient) handicap
  before it produced directional raiding. Budget real iteration time — this is not a "guess
  three constants and ship" rung.
- **A near-always-preparable task on the shared board is dangerous regardless of its score**
  — `assign_task_to_agent`'s fall-through-on-prepare-failure loop means *any* task type that
  reliably succeeds at `prepare()` can become a fallback of last resort no matter how low its
  cached score is, unless something stops the loop early. The `if task.priority <= 0: break`
  fix in `TaskManager.assign_task_to_agent` (Task 3) is that stop — it's generic and will
  matter again for `GuardTask`/`AttackTask` in Tasks 4-5, not just raiding.
