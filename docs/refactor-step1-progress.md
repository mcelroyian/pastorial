# Refactor Step 1 — Progress Handoff

**Plan doc:** `C:\Users\Ian\projects\pastorial\docs\refactor-step1-plan.md`
(WSL path: `/mnt/c/Users/Ian/projects/pastorial/docs/refactor-step1-plan.md`)

**Branch:** `main` — all work committed directly.

**Start reading here, then the plan doc for task details.**

---

## Status at a Glance

| Task | Description | Status |
|------|-------------|--------|
| Bug fix | Mill flour output had no delivery path; never reached bakery | ✅ Done (`6a4ab77`) |
| Task 1 | Headless Simulation class; decouple sim from rendering | ✅ Done (`87ce5f1`) |
| Task 2 | pytest harness + smoke tests | ✅ Done (commit pending) |
| Task 3 | Declarative task steps (TaskStep abstraction) | ⬜ Not started |
| Task 4 | Dead code & comment residue removal | ⬜ Not started |
| Task 5 | Fix TaskManager/AgentManager init wiring | ✅ Done (folded into Task 1 commit) |

---

## What Was Done

### Bug fix (commit `6a4ab77`)
`Mill.tick()` was producing flour into `current_output_quantity` but no agent task or
automatic mechanism existed to move it to the bakery. Added
`ResourceManager._auto_distribute_outputs()` (called each `update_nodes()` tick) that
pushes single-output station buffers directly into the nearest accepting
`MultiInputProcessingStation`. Bread now appears by tick ~6,000 (seed=42).

### Task 1 (commit `87ce5f1`)
- **Created `src/core/simulation.py`** — owns `Grid`, `ResourceManager`, `TaskManager`,
  `AgentManager`, all five spawn methods, and `update(dt, manual_mode)`. No
  `pygame.display` / `pygame.font` / `Surface` usage. Safe to instantiate headlessly.
- **Created `src/rendering/agent_renderer.py`** — standalone `draw_agent()` function
  with behavior→color map. Replaces `Agent.draw()`.
- **`GameLoop`** stripped to a thin shell: owns screen/clock/fonts/UI panels and a
  `Simulation` instance. `render()` reads sim state only, never mutates it.
- **`Agent`**: removed `draw()`, `behavior_colors`, `self.color`. Renamed `v()` →
  `cancel_current_task()` (was already called by `TaskManager.cancel_task()` under that
  name — pre-existing name mismatch).
- **`AgentManager.render_agents()`** now calls `agent_renderer.draw_agent()`.
- **`TaskManager`**: removed `agent_manager` constructor param (was patched post-init
  and never read in any method body). Replaced `time.time()` scheduling with accumulated
  `dt` — makes headless runs deterministic (Task 5 goal also satisfied here).

**Verify headless:**
```
python -c "from src.core.simulation import Simulation; s = Simulation(seed=42); [s.update(1/60) for _ in range(600)]"
```

### Task 2 (commit pending)
- **Created `pytest.ini`** — sets `pythonpath = .`, `testpaths = tests`. No other config
  needed; `src` is a PEP 420 namespace package, works without `__init__.py`.
- **`tests/test_smoke.py`** — 6 tests sharing a module-scoped fixture (9,000-tick run
  executed once). Asserts: no exception; berries in storage > 0; wheat reached mill
  (not checked in storage — wheat is fully hauled to mill by tick 9,000); flour + bread
  evidence > 0; bread in bakery output > 0; determinism (sequential runs, same seed).
  Teeth verified: commenting out `station.tick()` → flour and bread tests fail.
- **`tests/test_pathfinding.py`** — 5 tests: straight path, route around vertical wall
  obstacle, fully blocked (isolated start corner) returns None, blocked goal returns
  None, start == goal returns single-element path.
- **`tests/test_storage_point.py`** — 9 tests: add within/at capacity; rejected type;
  `reserve_space` / `release_reservation` / `commit_reservation_to_storage` cycle;
  `reserve_for_pickup` / `collect_reserved_pickup` / `release_pickup_reservation`.
- **`tests/test_task_lifecycle.py`** — 3 tests using `Simulation(seed=42)`: task starts
  PENDING; `GatherAndDeliverTask` (priority=100, 3 berries) completes within 3,000 ticks;
  completed task appears in `task_manager.completed_tasks`.

**Non-obvious gotchas discovered:**
- `get_global_resource_quantity(WHEAT)` returns 0 at tick 9,000 because wheat is fully
  hauled from storage to mill by then. Wheat check uses mill input buffer + bread evidence.
- Determinism test must run sims **sequentially** (not interleaved tick-by-tick), because
  `random` is module-global; interleaving two sims' `update()` calls corrupts both
  sequences. Sequential runs from same seed → identical counts confirmed.
- TaskManager public API for posting is `add_task()`, not `post_task()`.

**Run:**
```
.venv/bin/pytest tests/ -v   # 23 tests, ~1.6s
```

### Task 5 (folded into Task 1)
The `TaskManager(resource_manager, agent_manager=None)` + post-init patch was removed.
`TaskManager.__init__` now only takes `resource_manager`. `agent_manager_ref` is gone.

---

## What Comes Next

### Task 3 — Declarative task steps (START HERE next session)
After Task 2 tests pass and are committed, introduce:
```python
class TaskStep(ABC):
    def create_intent(self, agent, task) -> Intent: ...
    def on_success(self, agent, task, resource_manager) -> None: ...
```
Rewrite `GatherAndDeliverTask` and `DeliverWheatToMillTask` using a step list.
The big `on_intent_outcome` switch blocks should disappear.
Add a trivial `PatrolTask` (A→B→A) as proof-of-cost (~20 lines). All Task 2 tests
must still pass unchanged.

### Task 4 — Dead code removal
- `grep -rn "# Added\|# Changed" src/` → remove all hits.
- Delete commented-out `request_task_for_agent` block in `task_manager.py`.
- Delete commented-out `execute_step` stubs in `task.py`.
- Remove `GatherIntent`, `DeliverIntent`, `GatherAndDeliverFullLoadIntent` from
  `intents.py` (and the dead inventory-update branches in `agent.py:395–410`).
- Trim per-frame DEBUG logging in `Agent._follow_path` / `update` (keep state
  *transitions*, not every frame).
- Fix unreachable `pygame.quit()` after `raise` in `main.py` line 63.

---

## Key Architecture Notes

- `Simulation` is the unit under test — import it directly, no display needed.
- `pygame.math.Vector2` works headlessly; no `pygame.init()` required for sim code.
- `TaskManager` scheduling now uses accumulated `dt`, not wall-clock `time.time()`,
  so headless tests are deterministic with a fixed seed.
- The `asyncio`/pygbag structure in `main.py` must stay — browser deploy depends on it.
  Do not use `threading` or `subprocess` anywhere in sim code.
- The mill bug fix means the production chain (`wheat→flour→bread`) now works.
  The smoke test should verify it end-to-end.
