# Plan 4 (Emergent Conflict) — Progress Handoff

**Plan doc:** `docs/plan-4-emergent-conflict.md` — read Task 4 there before continuing.
**Prerequisite docs:** `docs/plan-3-factions.md` (factions, done), `docs/balance-notes.md` (tuning history).

**Branch:** `main` — Task 3 (`dbfa088`) is committed. Task 4 implementation is complete, tests
green, not yet committed — confirm with the user before committing/pushing.

**Start reading here, then the plan doc for the Task 5 spec.**

---

## Status at a Glance

| Task | Description | Status |
|------|-------------|--------|
| Task 1 | Utility-based task scoring (the emergence engine) | ✅ Done (`b1f93d6`) |
| Task 2 | Rung 1 — Contested wild resources (no violence) | ✅ Done (`b4063af`) |
| Task 3 | Rung 2 — Theft (`StealFromStorageTask`) | ✅ Done (`dbfa088`) |
| Task 4 | Rung 3 — Defense (`GuardTask`, threat response) | ✅ Done (uncommitted) |
| Task 5 | Rung 4 — Combat | 🔴 **Next up** — not started |
| Task 6 | Tuning & the emergence report | ⬜ Not started |

Full test suite: **82 passed** (`pytest` from repo root; 71 baseline + 11 new for Task 4).
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

### Task 4 — Defense (`GuardTask`, threat response, uncommitted)

Victims can now respond to theft: a decaying, EventLog-derived `threat_level` drives a new
`GuardTask` that loiters at an owned storage point and makes raiding it materially riskier —
still entirely nonviolent, purely emergent (no `if faction.at_war` anywhere).

- **`AgentManager.get_agents_near(pos, radius, faction_id=None)`** (`src/agents/manager.py`)
  — new. Linear scan over `self.agents`, optional faction filter. Fine at current scale
  (~12 agents total); comment says so instead of adding an index.
- **`FactionContext.threat_level`** (`src/factions/context.py`, `compute_threat_level`
  staticmethod) — deliberately **lazy/query-time**, not a stored accumulator: scans
  `EventLog.since(sim_time - THREAT_LOOKBACK_SECONDS)` fresh every planning tick and sums
  `weight * 0.5**(age/half_life)` per qualifying event. `theft` counts when
  `other_faction_id == self` (I was the victim); `claim_contention` counts when
  `faction_id == self` (my preferred node was denied to me) — same field-semantics
  distinction documented in Task 2's contention event, now load-bearing for the first time.
  No new persistent state anywhere, per the "Key Architecture Notes" decay discipline below.
- **`GuardTask`** (`src/tasks/task.py`, after `StealFromStorageTask`) — building-agnostic by
  design (per explicit direction during planning, over a "just guard the bread building"
  alternative): `TaskManager` retargets whichever owned, not-already-guarded storage point
  currently holds the most stock each generation cycle. Loiters between two waypoints for
  `GUARD_LOITER_LEGS` legs (long enough that one agent stays "the guard" for a stretch, not
  re-tasked every 5s planning tick). `compute_score` = `UTILITY_BASE_VALUE_GUARD *
  threat_level * stock_worth_fraction - distance_cost`; generation is unconditional
  (mirrors Task 3's raid generation) and relies entirely on the existing score-floor `break`
  in `assign_task_to_agent` to keep it off the board when `threat_level` is 0 (score reduces
  to `-distance_cost`, i.e. negative).
- **Guard effect** — checked in `StealFromStorageTask._on_steal_complete`, **not** at
  `prepare()` time: a guard can arrive during the raider's travel/interact window, so the
  raider commits fully and only discovers the target was defended on completion. Blocks (and
  emits a new `raid_repelled` event) if `_count_guards_near` finds
  `>= config.MIN_DEFENDERS_TO_BLOCK_STEAL` of the *victim's own agents currently assigned a
  `GuardTask` for that exact building* within `config.GUARD_RADIUS`.
  **Deliberately scoped to guard-task-assigned agents, not any nearby agent** — the bread
  storage point is also where agents run `EatTask`, so "any nearby agent" would have given
  free, incidental deterrence from ordinary eating traffic and erased "guards don't gather"
  as a real opportunity-cost tradeoff. Required threading `resource_manager.agent_manager_ref`
  and `resource_manager.factions` (new duck-typed attributes, wired in `Simulation.__init__`,
  same pattern as `resource_manager.events`) so `_count_guards_near` can reach the *victim's*
  `TaskManager.assigned_tasks` from inside the raider's task.
- **Raid targeting/scoring became guard-aware**: `_best_raid_target` / `_score_raid_candidate`
  (new module-level helpers in `task.py`) pick the enemy storage maximizing `haul - distance -
  risk`, not simply richest-stock — `risk_cost` (inert since Task 1/3) is now
  `RAID_RISK_COST_PER_DEFENDER * defender_count`. Used identically by `compute_score` (anchor:
  `faction_ctx.home_centroid`) and `prepare()` (anchor: `agent.position`) so the two stay
  consistent. With only one raid-worthy building per faction today this mostly manifests as
  "guarding it lowers the raid score," not literal target-switching — the doc's "or shifts to
  unguarded targets" phrasing already anticipates this degenerate single-target case.
- **Critical empirical tuning — contention is far too continuous to weight naively.**
  The plan doc says "theft high, contention low"; a literal ~10x gap
  (`THREAT_WEIGHT_THEFT=10`, `THREAT_WEIGHT_CONTENTION=1`) broke
  `tests/test_theft.py::test_theft_event_fields`: `ASYMMETRIC` produces on the order of
  400 `claim_contention` events per 500 sim-seconds (ordinary wild-node competition, nothing
  to do with real hostility), so an uncapped decay-sum over even a low per-event weight
  reaches a high **steady-state equilibrium** (`weight * event_rate * half_life/ln2`) that
  alone cleared `GuardTask`'s score-floor bar — a guard formed from ambient foraging at
  ~t=30-40s, long before the seed's one real raid at ~t=317s, and blocked it outright.
  Fixed with **two levers together** (weight alone wasn't enough): `THREAT_WEIGHT_CONTENTION`
  down to `0.005`, plus a separate hard `THREAT_CONTENTION_CAP = 0.02` on the contention
  component specifically (independent of event rate) — tuned so
  `UTILITY_BASE_VALUE_GUARD * cap` (~0.3) stays below even the smallest realistic
  `distance_cost` to an owned building, i.e. contention alone can now *never* clear the
  score-floor bar; only theft (weight 10, uncapped) does. Verified via a headless per-seed
  trace (seeds 1-6): guard-first-seen now lands at/after the seed's first theft event in
  every seed that raids at all (seed 6 raids zero times at baseline, matching Task 3's
  documented "1 in 6 seeds doesn't raid" — not a regression).
- **Tests**: `tests/test_guard.py` (11 new) — `get_agents_near` filtering,
  `compute_threat_level` weighting/capping/decay (including the "decays, guard stops scoring
  positive" verify criterion, checked directly via `sim_time` manipulation rather than a full
  tick loop — same efficiency precedent as `tests/test_task_scoring_raid.py`), guard-blocks-
  steal and its inverse (unguarded succeeds; a merely-nearby-but-not-guarding agent doesn't
  block), guarded-target-scores-worse, `GuardTask.compute_score` threat/stock scaling, and an
  `ASYMMETRIC` scenario test asserting a guard appears at/after every seed's first theft.
- **Manual sanity**: same constraint as Task 3 (`main.py` hardcodes `DEFAULT`, no CLI scenario
  switch) — verified `DEFAULT` renders/runs cleanly via the `run` skill (10s live run,
  screenshot inspected, task board/agents/buildings all normal, no crash); `ASYMMETRIC`'s
  guard-after-theft behavior verified headlessly (see tuning note above).

---

## What Comes Next

### Task 5 — Rung 4: Combat

Per `docs/plan-4-emergent-conflict.md`, Task 5 section — the final rung. Violence enters as
another scored option (`AttackIntent`/`CombatBehavior`) and as guard enforcement, not as a mode
switch. Key pieces: `Agent.health`, death-path extension (cause-of-death metrics, dropped-goods
handling), `FleeBehavior`, guards escalating to attack raiders caught stealing, `AttackTask`
generation gated behind high threat + high scarcity. See the plan doc for full detail — it's
the largest single rung (explicitly flagged as such: health, combat math, flee, a new
`SYMMETRIC SCARCITY` scenario, and a de-escalation test all in one).

### Before starting Task 5

- Re-run `pytest` from a clean checkout to confirm this handoff's state is still green (82
  passed) before layering more on top.
- `threat_level` is now real and load-bearing (`GuardTask` reads it) — Task 5's `AttackTask`
  generation ("gated behind high threat + high scarcity") can reuse it directly; no new
  hostility-accumulation mechanism should be needed, per the "`FactionContext`/`EventLog` are
  the extension points" note below. A `death` or `attack` event type feeding back into
  `threat_level` would need its own weight tuned with the same care as contention's (see the
  empirical tuning note above) — don't assume a naive weight is safe without checking event
  frequency first.
- `_count_guards_near`'s "only agents actively assigned a GuardTask count as defenders"
  design choice will matter again for Task 5's "guard may attack a raider caught stealing" —
  the same guard-agent set is the natural source for "which of my agents should respond to
  this trespass."
- `resource_manager.agent_manager_ref` and `resource_manager.factions` (new Task 4 duck-typed
  attributes) are now available for any task that needs to reach another faction's
  `TaskManager`/agents — Task 5's flee/attack logic will likely need both again.

---

## Key Architecture Notes for Future Rungs

- **Wiring pattern for new sim-wide systems reaching into `Task.prepare()`**: don't change
  `Task.prepare(agent, resource_manager)`'s signature. Attach the new system as a
  duck-typed attribute on `resource_manager` (or wherever `prepare()` already has a
  reference), set once post-construction in `Simulation.__init__`, read via
  `getattr(x, 'attr_name', None)` with a None-guard. Established in Task 1
  (`tm.metrics`/`tm.agent_manager_ref`), Task 2 (`resource_manager.events`), and Task 4
  (`resource_manager.agent_manager_ref`/`resource_manager.factions` — the latter needed
  because a hostile task must sometimes read the *victim's* `TaskManager`, not just its own).
- **Every accumulator must decay, and decay should be lazy/query-time or piggyback an
  existing per-tick hook** — `SimMetrics`'s rolling windows prune lazily at query time;
  `ResourceNode.contention_pressure` decays inside the node's existing `update(dt)` (no new
  timer); `threat_level` (Task 4) is computed fresh every planning tick straight from
  `EventLog`, no stored state at all. Look for an existing tick hook (or go fully lazy)
  before adding a new timer.
- **A frequent, low-weight event source can still dominate a decay-sum accumulator — check
  the steady-state, not just the per-event weight.** For a Poisson-ish event stream at rate
  λ with per-event weight `w` and exponential half-life `h`, the equilibrium value is
  `w * λ * h / ln(2)` — if λ is high (as `claim_contention` is: ~400 events/500s in
  `ASYMMETRIC`, pure ordinary wild-node competition), even a "low" weight can equilibrate
  to something that swamps a rare-but-heavy signal like `theft`. This is why `threat_level`
  needed both a smaller `THREAT_WEIGHT_CONTENTION` *and* a separate hard
  `THREAT_CONTENTION_CAP` (Task 4) — the cap is what actually guarantees ambient noise can
  never alone cross a scoring threshold, independent of how the event rate might shift later.
  Any future rung that folds another frequent event type into an accumulator should compute
  this equilibrium before picking a weight, not tune-by-running-and-eyeballing.
- **`FactionContext` and `EventLog` are the two extension points** every later rung reads
  from — `threat_level` is now real and load-bearing (Task 4); Task 5's combat/attack scoring
  should read it directly rather than inventing a parallel hostility signal.
- **Regression gate**: `tests/test_balance.py` (20 sim-minute `DEFAULT` run, ≥80% survival)
  and `tests/test_factions.py` must stay green after every rung — run them explicitly, not
  just the new rung's own tests, before considering a task done.
- **Statistical/scenario tests need empirical tuning, not guessed thresholds** — true for
  Task 2's contention test, more true for Task 3's raid test, and most true yet for Task 4:
  beyond the usual weight/threshold tuning, Task 4 needed a structural fix (the equilibrium
  insight above) rather than just moving a constant. Budget real iteration time on every
  future rung with a statistical/scenario test — this project does not have a "guess three
  constants and ship" rung.
- **A near-always-preparable task on the shared board is dangerous regardless of its score**
  — `assign_task_to_agent`'s fall-through-on-prepare-failure loop means *any* task type that
  reliably succeeds at `prepare()` can become a fallback of last resort no matter how low its
  cached score is, unless something stops the loop early. The `if task.priority <= 0: break`
  fix in `TaskManager.assign_task_to_agent` (Task 3) is that stop, and Task 4's `GuardTask`
  generation relies on it too (unconditional generation, scoring-only gating) — it will
  matter again for `AttackTask` in Task 5.
- **Coincidental agent presence must not be conflated with deliberate assignment** — Task 4's
  guard-blocks-steal check only counts agents *currently assigned a `GuardTask` for that exact
  building*, not just any nearby agent, because the bread storage point is also the `EatTask`
  destination — "any nearby agent" would have given free deterrence from routine eating
  traffic. The same distinction (assigned-to-do-X vs. merely-near) will likely matter again
  for Task 5's "guard may attack a raider caught stealing."
