# Plan 4: Emergent Conflict — Competition, Theft, and War from Scarcity

**Audience:** An implementation agent working on this codebase.
**Prerequisite:** `plan-3-factions.md` completed (independent faction economies, scenario system, per-faction metrics, peaceful 2-faction baseline).

## Context & Motivation

This is the phase the project has been building toward. The design goal is **warfare that emerges, not warfare that is scripted**. There is no "declare war" function anywhere in this plan. Instead:

- Factions choose actions by *utility scoring* against their own state (food deficit, distances, perceived risk).
- Hostile actions (claim-jumping, theft, violence) are just tasks that outscore peaceful ones under the right conditions.
- Escalation is a feedback loop: scarcity → theft → defense/retaliation → deaths → deeper scarcity. De-escalation must be equally possible: when abundance returns, hostile options score poorly and peace resumes.

The tests for this phase are therefore *statistical and scenario-based*: abundance ⇒ ~no conflict; asymmetric scarcity ⇒ raiding emerges; symmetric scarcity ⇒ escalation. If conflict happens in abundance, or never happens in scarcity, the tuning is wrong.

Build in the order below — each rung of the ladder is shippable and testable alone.

---

## Task 1: Utility-based task scoring (the emergence engine)

### Why
Task selection is currently static integer priority. Emergence requires priorities that *respond to conditions*: a raid must be a terrible idea when granaries are full and an increasingly good one as the faction starves. Do this first, on the existing peaceful tasks, so the mechanism is proven before any hostile task exists.

### What to do
- Replace static `priority` with a scoring function evaluated at generation time and refreshed periodically for pending tasks: `score = base_value * urgency(faction_state) - distance_cost - risk_cost`. Suggested shape: each Task class implements `compute_score(faction_ctx) -> float`; `TaskManager` sorts the board by current score.
- Define `FactionContext` (built per faction each planning tick from `SimMetrics`/stock queries): current stock by type, consumption rate, agents alive, recent deaths, food deficit projection (e.g., `stock_bread / (consumption_rate)` = seconds of food remaining) — this last number is the master scarcity signal; and (Task 3) recent hostility events.
- Migrate existing generation logic: gather-berry/wheat/process tasks score by how far below target stock the faction is (smooth curve, not threshold cliff). Keep `EatTask` self-generated as-is (personal needs bypass the board).
- Config: scoring weights in one place (`config` section "UTILITY WEIGHTS") — these are the main tuning surface for the whole phase.

### Verify
- Test: with low bread and full wheat, wheat-processing tasks outscore wheat-gathering; with empty stores everything gathers. (Assert on relative score ordering, not absolute values.)
- Peaceful baseline still passes plan-3's balance tests — scoring migration must not destabilize the peaceful economy. This is the regression gate for the phase.

## Task 2: Rung 1 — Contested wild resources (no violence)

### Why
The cheapest competition: both factions want the same bushes. Mostly exists already via node claims; this rung makes it *strategic* and observable.

### What to do
- Distance-aware node choice already emerges from scoring (closer nodes cheaper). Add **contention pressure**: when a faction's preferred nodes are frequently claimed by the enemy (track claim-denied-by-other-faction events), gathering scores for nodes in contested areas drop slightly and remote/safe nodes gain — factions naturally partition the wilderness when supply allows, and overlap (conflict precursor) when it doesn't.
- Emit hostility-precursor events to metrics: `claim_contention(faction, other_faction, node)`.
- Add an **event log** (`src/core/events.py`): ring buffer of typed sim events (contention, later theft/attack/death) with sim timestamps, faction ids, positions. This is both the observability tool for this phase and the input for threat perception (Task 3). Render the last few events in the UI panel (one line each).

### Verify
- Scenario test (`SCARCITY`, seeded): contention events occur; in `DEFAULT`, they are rare. Statistical assertion over ≥3 seeds.

## Task 3: Rung 2 — Theft (RaidTask)

### Why
First deliberately hostile act, still nonviolent. An agent walks to an enemy storage point and takes food.

### What to do
- `StealFromStorageTask(Task)`: steps = MoveTo(enemy storage) → Interact("STEAL", duration ~ `DEFAULT_COLLECTION_TIME_FROM_STORAGE * 1.5`) → withdraw up to inventory capacity (bypassing the faction gate via an explicit `force=True`/steal path on `StoragePoint` — the plan-3 gate stays intact for normal ops) → MoveTo(own storage) → deposit.
- **Scoring — where emergence lives.** Raid score ≈ `food_deficit_urgency * expected_haul - distance_cost - risk_cost - peace_bias`:
  - `food_deficit_urgency`: from `FactionContext` (seconds-of-food-remaining; steep as it approaches 0).
  - `expected_haul`: what the faction *believes* is in the target storage. Start with perfect information (simple); add scouting/memory only if time permits — note the simplification in code comments.
  - `risk_cost`: grows with defenders near target (Task 4) and with own recent losses.
  - `peace_bias`: constant making raids strictly worse than any viable peaceful option. **Raiding must only win when gathering can't meet the deficit** (no reachable wild food, or too slow). Get this inequality right and everything else follows.
- Theft generates events: `theft(victim_faction, raider_faction, amount, position)` — victims react in Task 4.
- Witnessing: keep v1 simple — the victim faction learns of theft when it happens (event-driven), regardless of line of sight.

### Verify
- Scenario test (`ASYMMETRIC`, ≥3 seeds): poor faction raids rich faction; bread flows measurably A→B via theft metrics.
- Scenario test (`DEFAULT`, ≥3 seeds): zero or near-zero raids.
- Unit: `StoragePoint` steal path works despite faction gate; normal path still gated.
- The peaceful balance test stays green.

## Task 4: Rung 3 — Defense (threat response, still nonviolent)

### Why
Victims must be able to respond, or theft is free and escalation is one-sided. Guarding creates the risk term that raid scoring prices in — a genuine strategic tradeoff (guards don't gather).

### What to do
- `FactionContext.threat_level`: decaying accumulator fed by hostility events against the faction (theft high, contention low). Decay over sim-minutes so peace can return.
- `GuardTask`: agent moves to own storage/building and loiters (reuse/extend the existing `PatrolTask` pattern — waypoints around owned buildings). Score scales with `threat_level` and stock worth protecting; competes against economic tasks on the same board.
- Guard effect (nonviolent v1): a raider's `InteractStep("STEAL")` fails if ≥N enemy agents are within `config.GUARD_RADIUS` of the target when the steal begins (add the proximity check to the steal interaction). Failed raid emits an event, raises raider's perceived risk of that target.
- Requires an agent spatial query: `AgentManager.get_agents_near(pos, radius, faction_id=...)`. Linear scan is fine at current scale (~12 agents); leave a comment, not an optimization.

### Verify
- Scenario test: `ASYMMETRIC` with theft happening ⇒ victim faction generates guards; guarded raids fail; raid frequency drops or shifts to unguarded targets (assert directionally over seeds).
- Threat decays: force threat high, run quiet sim-minutes, guards stop being generated.

## Task 5: Rung 4 — Combat

### Why
The final rung. Violence enters as another scored option and as guard enforcement — not as a mode switch.

### What to do
- `Agent` gains `health: float` (max 1.0), regen slow when fed, none when starving. Death reuses plan-2's death path (it must already handle claims/occupancy/references — extend for cause-of-death metrics and dropping carried resources; v1 of drops: return to nearest same-faction storage of the *killer's* faction if carried by a raider... keep it simpler: carried resources are lost, logged. Revisit later).
- `AttackIntent(target_agent_id)` + `CombatBehavior`: close to melee range (adjacent cell), exchange damage per sim-second (`config.COMBAT_DPS`); target agent is notified and either fights back (if own combat option scores) or flees.
- `FleeBehavior`: triggered at `health < FLEE_THRESHOLD` or when attacked while noncombat-tasked — move toward own home region; abandons current task through the normal fail path.
- Guards escalate: a guard may attack a raider caught stealing (guard's attack scores high on trespass events). Raiders may fight guards only when desperation is extreme (utility, again).
- `AttackTask` generation: gated behind high threat + high scarcity, targeting enemy agents in/near own territory first (defensive violence before offensive). Offensive raids-with-violence should only emerge at the far end of the desperation curve. Encode this purely through scoring weights + `peace_bias` tiers (violence bias >> theft bias), not special-case logic.
- Rendering: health bar sliver; combat flash/line between combatants; death event in the panel log.

### Verify
- Unit: combat math (two agents fight; one dies; death cleanup clean — run 500 ticks after).
- Unit: flee triggers at threshold; fleeing agent's task fails cleanly.
- Scenario (`SYMMETRIC SCARCITY` — add scenario: both factions short on wild nodes, ≥3 seeds): escalation observed — sequence contention → theft → guarding → at least some combat deaths; sim survives 30+ sim-minutes without exceptions regardless of who wins.
- Scenario (`DEFAULT`): zero combat over long horizon.
- **De-escalation test:** start in `SCARCITY`, then mid-run inject abundance (scenario hook: spawn wild nodes / stock injection at sim-time T); hostility events per minute must fall substantially after T. War must be able to *end*.

## Task 6: Tuning & the emergence report

### What to do
- Extend `scripts/balance_report.py` with a conflict section: hostility events by type/faction over time buckets, deaths by cause, food flow including stolen goods.
- Add `scripts/emergence_matrix.py`: run all scenarios × K seeds headless, print a matrix of conflict intensity per scenario. Target picture: DEFAULT ≈ 0; SCARCITY = low/contention; ASYMMETRIC = theft, one direction; SYMMETRIC-SCARCITY = escalation.
- Tune `UTILITY WEIGHTS` until the matrix reads correctly. Record final weights + rationale in `docs/balance-notes.md`.
- Encode the matrix's key inequalities as `test_emergence.py` (marked slow; statistical, seeded, directional assertions only — never exact counts).

---

## Ground rules

- **No scripted war state.** If you find yourself writing `if faction.at_war:` — stop; express it through scoring inputs (threat, deficit) instead.
- Every hostile behavior must also de-escalate; every accumulator decays.
- Peaceful baseline tests from plans 2–3 must stay green throughout — run them at every rung.
- Keep each rung ≤ a few hundred lines; prefer new Task/Intent/Behavior classes over modifying agent core.
- Sim time only; statistical tests use multiple seeds; pygbag constraints unchanged; commit per rung.

## Definition of done

1. Utility scoring replaces static priorities; peaceful economy stable under it.
2. Four-rung ladder implemented: contention → theft → guarding → combat, each individually tested.
3. Emergence matrix reads correctly: no conflict in abundance, theft under asymmetric scarcity, escalation under symmetric scarcity, de-escalation when abundance returns.
4. Event log + conflict reporting tooling; all long-run scenarios crash-free.
5. `python main.py` on the SYMMETRIC-SCARCITY scenario is *watchable*: you can see a war start, be fought, and end, with no line of code that told it to.
