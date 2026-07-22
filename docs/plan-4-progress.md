# Plan 4 (Emergent Conflict) — Progress Handoff

**Plan doc:** `docs/plan-4-emergent-conflict.md` — read Task 3 there before continuing.
**Prerequisite docs:** `docs/plan-3-factions.md` (factions, done), `docs/balance-notes.md` (tuning history).

**Branch:** `main` — all work committed and pushed directly, no PRs.

**Start reading here, then the plan doc for the Task 3 spec.**

---

## Status at a Glance

| Task | Description | Status |
|------|-------------|--------|
| Task 1 | Utility-based task scoring (the emergence engine) | ✅ Done (`b1f93d6`) |
| Task 2 | Rung 1 — Contested wild resources (no violence) | ✅ Done (`b4063af`) |
| Task 3 | Rung 2 — Theft (`StealFromStorageTask`) | 🔴 **Next up** — not started |
| Task 4 | Rung 3 — Defense (`GuardTask`, threat response) | ⬜ Not started |
| Task 5 | Rung 4 — Combat | ⬜ Not started |
| Task 6 | Tuning & the emergence report | ⬜ Not started |

Full test suite: **60 passed** as of `b4063af` (`pytest` from repo root). Peaceful baseline
(`tests/test_balance.py`, `tests/test_factions.py`) is the regression gate — must stay green
through every future rung.

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
  a rival faction. **Important lesson learned**: an earlier version recorded contention for
  *every* already-claimed node encountered while scanning past it to find an open one — this
  saturated the event log identically for both `SCARCITY` and `DEFAULT` scenarios within
  ~180 sim-seconds (both factions are drawing on the same 30-node wild pool more or less
  constantly), destroying the differentiating signal the Task 2 verify criterion needs.
  Narrowing to "was my *preferred* choice specifically taken by the enemy" fixed it.
- **Score integration**: `_nearest_distance_cost` widened to take `(position,
  contention_pressure)` pairs + a `contention_weight` param (default `0.0`, so the
  `DeliverWheatToMillTask`/mill call site — mills are never contested — is a one-line,
  no-new-mechanism adaptation). Because it's a `min(...)` over combined distance+contention
  cost, a contested-but-close node can lose to a farther-but-uncontested one — that alone
  produces "contested areas score lower, safe nodes gain," no separate boost logic needed.
- **UI**: `TaskStatusDisplay` gained a "Recent Events" panel section (`events.recent(5)`,
  newest first). Confirmed visually — note the existing panel has no global height budget
  across its 5 sections, so with a busy task board the events section can get pushed off
  the visible area (pre-existing characteristic, not new).
- **Tests**: `tests/test_events.py` (3 tests). The scenario/statistical test
  (`test_scarcity_has_more_contention_than_default_over_seeds`) needed real empirical
  tuning of both run length and threshold — see the "Important lesson learned" note above.
  Landed on a **60 sim-second** window (both scenarios' counts still growing, not yet
  saturated): `DEFAULT` sums to ~5 events across 3 seeds, `SCARCITY` to ~85+, a wide margin.
  `total_default <= 10` is the "rare" bound.

---

## What Comes Next

### Task 3 — Rung 2: Theft (`StealFromStorageTask`)

Per `docs/plan-4-emergent-conflict.md`, Task 3 section:

- **`StealFromStorageTask(Task)`**: steps = `MoveTo(enemy storage)` → `Interact("STEAL",
  duration ~ DEFAULT_COLLECTION_TIME_FROM_STORAGE * 1.5)` → withdraw up to inventory
  capacity (bypassing the faction gate via an explicit `force=True`/steal path on
  `StoragePoint` — the Plan 3 gate must stay intact for normal ops) → `MoveTo(own storage)`
  → deposit. Follow the existing declarative `TaskStep`/`MoveToStep`/`InteractStep` pattern
  from `src/tasks/task.py` — don't hand-roll a new step mechanism.
- **Scoring is where the emergence lives** — this is the load-bearing design point of the
  whole phase: `raid_score ≈ food_deficit_urgency * expected_haul - distance_cost -
  risk_cost - peace_bias`.
  - `food_deficit_urgency`: from `FactionContext.food_deficit_seconds` (already built in
    Task 1 — this is exactly the "seconds of food remaining" signal it exists for).
  - `expected_haul`: start with perfect information (read the target storage's actual
    stock) — note the simplification in a code comment; scouting/memory is explicitly
    out of scope unless time permits.
  - `risk_cost`: this is the field Task 1 wired to `0.0` and Task 2 partially activated for
    gather tasks — Task 3 doesn't need defenders yet (that's Task 4's `GuardTask`), but
    should still route through the same named term.
  - `peace_bias`: a constant that must make raiding strictly worse than any viable peaceful
    option. **Get this inequality right and everything else follows** — raiding should only
    win when gathering genuinely can't meet the deficit (no reachable wild food, or too
    slow). This is the single most important tuning constant in this rung.
- **`StoragePoint` steal path**: add an explicit bypass of the Plan 3 faction gate
  (`can_accept`/`reserve_space`/`reserve_for_pickup` currently check `_faction_allowed` —
  see `src/resources/storage_point.py`), gated behind an explicit `force=True` or similar,
  so normal delivery/pickup paths are provably untouched. Unit-test both paths.
- **Events**: emit `theft(victim_faction, raider_faction, amount, position)` to the Task 2
  `EventLog` (`src/core/events.py`) — same `record(event_type, **fields)` call shape as
  `claim_contention`. Victims react to this in Task 4 (event-driven "witnessing," not
  line-of-sight, per the doc — keep v1 simple).
- **Verify** (from the doc): scenario test on `ASYMMETRIC` (≥3 seeds) — poor faction raids
  rich faction, bread flows measurably A→B via theft metrics. Scenario test on `DEFAULT`
  (≥3 seeds) — zero or near-zero raids. Unit test: steal path works despite the faction
  gate; normal path stays gated. **The peaceful balance test must stay green** — same
  regression gate as Tasks 1 and 2.

### Before starting Task 3

- Re-run `pytest` from a clean checkout to confirm `b4063af`'s state is still green (should
  be, but confirm before layering more on top).
- Skim `docs/balance-notes.md`'s "Balance levers for Phase 4" section — it already names
  the levers for inducing scarcity (raise `BAKERY_PROCESSING_SPEED`, reduce
  `INITIAL_BAKERIES`, increase `INITIAL_AGENTS`) if `ASYMMETRIC`'s current tuning doesn't
  produce raids readily.

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
  timer). Look for an existing tick hook before adding a new one.
- **`FactionContext` and `EventLog` are the two extension points** every later rung reads
  from — `threat_level` on `FactionContext` and the `EventLog` ring buffer are both
  explicitly inert/generic today, built so Task 3+ add *behavior*, not new *shape*.
- **Regression gate**: `tests/test_balance.py` (20 sim-minute `DEFAULT` run, ≥80% survival)
  and `tests/test_factions.py` must stay green after every rung — run them explicitly, not
  just the new rung's own tests, before considering a task done.
- **Statistical/scenario tests need empirical tuning, not guessed thresholds** — Task 2's
  contention test required actually running the simulation at several checkpoints to find a
  run length where the `SCARCITY` vs `DEFAULT` signal was both real and not yet washed out
  by saturation. Budget time for this on Task 3's `ASYMMETRIC` raid test too.
