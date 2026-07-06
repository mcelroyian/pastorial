# Plan 2: Needs & Consumption — Make the Economy Mean Something

**Audience:** An implementation agent working on this codebase.
**Prerequisite:** Step-1 refactor (done): headless `Simulation` (src/core/simulation.py), `TaskStep` abstraction (src/tasks/task.py), pytest suite (tests/).
**Followed by:** `plan-3-factions.md`, then `plan-4-emergent-conflict.md`.

## Context & Motivation

The production chain works end-to-end (berries/wheat gathered; mill makes flour; bakery makes bread) but is one-directional: **bread is produced and never consumed**. Nothing in the world exerts pressure. The project's end goal is emergent warfare driven by resource competition, and competition requires scarcity, which requires consumption.

This phase gives agents a hunger need, makes them eat bread, and makes starvation have consequences. It also adds the measurement tooling (sim clock, metrics) that phases 3–4 depend on for balancing. **No factions, no combat in this phase.**

Design principle throughout: needs are *agent-local pressure*, not global planner logic. An agent decides to eat because *it* is hungry. This is the first step away from the centralized TaskManager threshold model and toward the local decision-making that emergence requires.

---

## Task 0: Simulation clock (small, do first)

### Why
`Task` timestamps and `TaskManager` scheduling use wall-clock `time.time()`. Hunger decay, starvation timers, and later combat cooldowns must run on *simulation time* or headless fast-forward tests (thousands of ticks in seconds) will behave differently from real-time play. This is also the known nondeterminism source flagged in step 1.

### What to do
- Add `self.sim_time: float = 0.0` to `Simulation`, incremented by `dt` each `update()`.
- Thread it into `TaskManager.update` and `Task` timestamps (pass sim_time or a clock reference; pick the least invasive option that removes all gameplay-relevant `time.time()` calls). Wall-clock may remain for logging only.
- `InteractingBehavior`'s duration timing (src/agents/agent_behaviors.py) should also count sim `dt`, not wall time — verify and fix if needed.

### Verify
- `grep -rn "time.time()" src/` → remaining hits are logging/metrics-only, with a comment saying so.
- Existing test suite passes. Same-seed determinism test (two runs, identical end-state resource counts) passes — add it if it doesn't exist.

## Task 1: Hunger need on agents

### Why
The core scarcity driver. Everything in phases 3–4 (faction food planning, raid utility scoring) reads this value.

### What to do
- Add to `Agent`: `hunger: float` in `[0.0, 1.0]` (0 = starving, 1 = full), decaying at `config.HUNGER_DECAY_PER_SECOND`. Structure it as a small `Needs` component (`src/agents/needs.py`) rather than bare fields — phase 4 may add more needs (safety), and a component keeps `Agent` from re-bloating.
- Config (add to src/core/config.py with these suggested starting values, tune during Task 4):
  - `HUNGER_DECAY_PER_SECOND = 0.005` (full → starving in ~200 sim-seconds)
  - `HUNGER_SEEK_FOOD_THRESHOLD = 0.4` (agent starts wanting food)
  - `HUNGER_CRITICAL_THRESHOLD = 0.15` (drop everything)
  - `HUNGER_RESTORED_PER_BREAD = 0.5`
  - `STARVATION_GRACE_PERIOD = 30.0` (sim-seconds at hunger 0 before death)
- Update `Needs` in `Agent.update` (sim dt).
- Rendering: a small hunger bar or color pip near the agent (src/rendering/agent_renderer.py or wherever agent drawing landed after step 1). Keep it minimal.

### Verify
- Unit test: hunger decays at configured rate over N ticks; clamped at 0.
- Run `python main.py` — hunger indicator visible and decreasing.

## Task 2: EatTask — agents fetch and consume bread

### Why
Closes the economic loop: bread now leaves the world. This creates the demand signal that makes all production upstream *matter*.

### What to do
- New `EatTask(Task)` using the step system: `MoveToStep`(bread storage) → `InteractStep`("COLLECT", withdraw 1 bread) → consume (restore hunger via `on_complete`; eating can be instantaneous at the storage point for now — no need for a "home" location yet).
- `prepare()`: find nearest `StoragePoint` with ≥1 `BREAD` and reserve/withdraw-claim it (reuse the existing reservation pattern from `GatherAndDeliverTask.prepare`; check whether `StoragePoint` supports *withdrawal* reservations — `DeliverWheatToMillTask` retrieves from storage, so a pattern exists; follow it).
- **Selection logic** — this is the important design point:
  - When `hunger < HUNGER_SEEK_FOOD_THRESHOLD`, the agent (in `EvaluatingIntentBehavior` / `acquire_task_or_perform_idle_action`) creates its *own* `EatTask` instead of pulling from the job board. Personal-need tasks are self-generated, never posted to the shared board.
  - When `hunger < HUNGER_CRITICAL_THRESHOLD` while working, the agent abandons its current task (fail it back to the board via the existing `report_task_outcome` re-post path — verify reservations get released by `cleanup`) and eats.
  - If no bread is available, do **not** spin: agent retries with a cooldown (`config.EAT_RETRY_COOLDOWN = 5.0` sim-seconds) and continues normal work meanwhile (a hungry agent that can't eat should still gather — that's the pressure that drives production and, later, raiding).
- Add `TaskType.EAT`.

### Verify
- Test: hungry agent + storage with bread ⇒ within N ticks, bread count decremented, agent hunger restored above threshold.
- Test: hungry agent + no bread ⇒ agent does not deadlock; still completes normal gather tasks; retries eating periodically.
- Test: agent mid-gather-task hitting critical hunger abandons the task; the task's node claim and dropoff reservation are released (assert on the node/storage state — this is a likely bug site).

## Task 3: Starvation consequences + agent death

### Why
Without consequences, hunger is a decorative bar. Death is what makes food scarcity an existential problem a faction must solve — by production or, later, by taking someone else's.

### What to do
- At `hunger == 0`, start the grace timer; at expiry, the agent dies.
- Optional but recommended: below `HUNGER_CRITICAL_THRESHOLD`, scale `agent.speed` down (e.g., ×0.6) — visible desperation, and a death spiral that phase 4's raid scoring will exploit.
- **Agent removal is the risky part.** On death:
  - Fail/cancel its current task via existing paths so reservations and node claims release.
  - Remove from `AgentManager.agents` and from `TaskManager.assigned_tasks`.
  - Clear grid occupancy (`grid.update_occupancy(..., is_placing=False)`).
  - Drop carried inventory: for now, log it and discard (item-on-ground entities are out of scope; phase 4 revisits).
  - Emit a metrics/log event (Task 4).
- Do a search for every structure holding agent references (inspector panel in rendering, `assigned_tasks` keyed by agent id, behaviors holding `self.agent`) and handle each.

### Verify
- Test: agent with no food access dies after decay + grace period; sim continues without exceptions for 1,000 more ticks; dead agent's claims/reservations are released; occupancy cell is free again.
- Test: run default config for a long horizon (see Task 5) — agents do NOT all die (balance gate).
- Manual: kill food production in a live run (possible via config: 0 bakeries) and watch agents slow, then die, without crashes or ghost references (check the inspector panel with a dead agent selected).

## Task 4: Metrics collector

### Why
Phases 3–4 make balance judgments ("does scarcity cause raids?") that are impossible to evaluate by watching the screen. A metrics object also gives faction AI (phase 3) its inputs: per-tick production/consumption rates.

### What to do
- `src/core/metrics.py`: a `SimMetrics` class owned by `Simulation`. Track counters and time series (coarse — sample every N sim-seconds, don't store per-tick): resources gathered/produced/consumed by type, tasks completed/failed by type, agent deaths, current agent count, current stock by type.
- Instrument at the choke points: step `on_complete` handlers (gather/deliver/consume), processing station output, agent death. Prefer a small event API (`metrics.record(event_name, **fields)`) over scattering counter logic.
- Add a headless report script `scripts/balance_report.py`: run a seeded sim for M sim-minutes, print a summary table (production vs consumption per resource, deaths, net bread flow). This is the tuning tool.

### Verify
- Test: after a smoke run, `metrics.consumed[BREAD] > 0` and equals total hunger-restoration events.
- `python scripts/balance_report.py --seed 42 --minutes 10` runs headless and prints sane numbers.

## Task 5: Balance pass

### Why
Default config must sit *near* equilibrium: enough food that the village survives, little enough that stock doesn't grow unboundedly. Phase 4 induces scarcity by perturbing this equilibrium, so it has to exist first.

### What to do
- Using `balance_report.py`, tune: `INITIAL_AGENTS`, bakery throughput (`BAKERY_PROCESSING_SPEED`), hunger constants, task-generation thresholds (`MIN_*_STOCK_LEVEL`) until: over a 20-sim-minute seeded run, zero-to-rare deaths and bread stock roughly flat (not monotonically exploding).
- Record chosen values and the reasoning in a short `docs/balance-notes.md`.
- Encode the equilibrium as a test: `test_balance.py` — default config, fixed seed, 20 sim-minutes: ≥80% of agents alive, bread was both produced and consumed. Mark it clearly so future contributors re-tune instead of deleting it when it fails.

### Verify
- Full `pytest` green. `python main.py` shows a living village: agents gathering, eating, hunger bars oscillating rather than draining to zero.

---

## Ground rules

- Personal needs are agent-local; the shared job board stays for economic work. Don't route EatTasks through `_generate_tasks_if_needed`.
- All new timing on sim time, never wall clock.
- Keep the pygbag/browser build working (no threading/subprocess; `main.py` asyncio structure unchanged).
- Commit per task; `pytest` before each commit.

## Definition of done

1. Agents get hungry, fetch bread, eat it; bread stock visibly cycles.
2. Agents starve and die cleanly (no leaked claims, reservations, occupancy, or references) when food runs out.
3. Sim clock: gameplay logic free of wall-clock time; seeded runs deterministic.
4. `SimMetrics` + `balance_report.py` exist; balance test encodes a surviving default village.
5. All tests pass headless; visual run looks alive.
