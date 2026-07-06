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
| Task 2 | pytest harness + smoke tests | 🔴 **Next up** — in progress at session end |
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

### Task 5 (folded into Task 1)
The `TaskManager(resource_manager, agent_manager=None)` + post-init patch was removed.
`TaskManager.__init__` now only takes `resource_manager`. `agent_manager_ref` is gone.

---

## What Comes Next

### Task 2 — Test harness (START HERE next session)

`pytest` is installed in `.venv` (`uv pip install pytest` already run).
The `tests/` directory and `tests/__init__.py` exist but no test files yet.

Write these four files per the plan:

**`tests/test_smoke.py`**
- Build `Simulation(seed=42)`, run **9,000 ticks** of `update(1/60)` (~150 sim-sec).
- Assert no exceptions.
- Assert `resource_manager.get_global_resource_quantity(ResourceType.BERRY) > 0`.
- Assert wheat gathered > 0 (check completed tasks or mill input received).
- Assert flour produced > 0 — check `sum(st.current_output_quantity for st in
  resource_manager.processing_stations if isinstance(st, Mill))` OR check bakery flour
  input. With the bug fix, flour reaches the bakery by tick ~4,000.
- Assert bread produced > 0 — check `sum(st.current_output_quantity.get(ResourceType.BREAD, 0)
  for st in processing_stations if isinstance(st, Bakery))`. Bread appears ~tick 6,000.
- Determinism check: same seed twice → same end-state berry count.

**`tests/test_pathfinding.py`**
- `find_path` on a small `Grid` (mock or real): path found around obstacle, None when
  blocked, start==goal case.
- Key import: `from src.pathfinding.astar import find_path` and `from src.rendering.grid import Grid`.

**`tests/test_storage_point.py`**
- Capacity limits, accepted-type rejection, `reserve_space` / `release_reservation` /
  `commit_reservation_to_storage` cycle, `reserve_for_pickup` / `release_pickup_reservation`.

**`tests/test_task_lifecycle.py`**
- A `GatherAndDeliverTask` goes PENDING → ASSIGNED → COMPLETED for one agent in a
  minimal hand-built world (1 bush, 1 storage, 1 agent adjacent). Use `Simulation` in
  a very small config or build objects directly — keep it fast.

**Verify after writing:**
```
.venv/bin/pytest tests/ -v
```
Also deliberately break something (e.g., comment out `station.tick()`) and confirm
smoke test fails, then revert.

### Task 3 — Declarative task steps
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
