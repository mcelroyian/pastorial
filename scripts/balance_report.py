#!/usr/bin/env python3
"""
Headless balance report: run the sim for N sim-minutes and print a summary table.

Usage:
    python scripts/balance_report.py [--seed SEED] [--minutes MINUTES] [--scenario SCENARIO]

Scenarios: DEFAULT, SCARCITY, ASYMMETRIC
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.simulation import Simulation
from src.core import scenarios as _scenarios
from src.resources.resource_types import ResourceType


def run(seed: int, minutes: float, scenario=None):
    sim = Simulation(seed=seed, scenario=scenario)
    target_sim_time = minutes * 60.0
    dt = 1.0 / 60.0
    ticks = int(target_sim_time / dt)
    for _ in range(ticks):
        sim.update(dt)
    return sim


def _fmt_dict(d: dict) -> str:
    return "  " + "\n  ".join(f"{k}: {v}" for k, v in d.items()) if d else "  (none)"


def report(sim: "Simulation") -> None:
    m = sim.metrics
    summary = m.summary()
    rm = sim.resource_manager
    am = sim.agent_manager

    current_stock = {rt.name: rm.get_global_resource_quantity(rt) for rt in ResourceType
                     if rm.get_global_resource_quantity(rt) > 0}

    print("=" * 60)
    print(f"Balance Report — sim_time={sim.sim_time:.1f}s  ({sim.sim_time/60:.1f} min)")
    print("=" * 60)
    print(f"\nAgents alive:  {len(am.agents)}")
    print(f"Deaths:        {summary['agent_deaths']}")

    print("\n--- Per-faction summary ---")
    for faction in sim.factions:
        fid = faction.faction_id
        alive = sum(1 for a in am.agents if a.owner_faction_id == fid)
        deaths = summary["faction_deaths"].get(fid, 0)
        produced = summary["faction_produced"].get(fid, {})
        consumed = summary["faction_consumed"].get(fid, {})
        stock = {rt.name: rm.get_faction_resource_quantity(fid, rt)
                 for rt in ResourceType if rm.get_faction_resource_quantity(fid, rt) > 0}
        print(f"  [{faction.name} (id={fid})]  alive={alive}  deaths={deaths}")
        if stock:
            print(f"    stock:    " + "  ".join(f"{k}={v}" for k, v in stock.items()))
        if produced:
            print(f"    produced: " + "  ".join(f"{rt.name}={qty}" for rt, qty in produced.items()))
        if consumed:
            print(f"    consumed: " + "  ".join(f"{rt.name}={qty}" for rt, qty in consumed.items()))

    print("\n--- Global stock ---")
    for name, qty in current_stock.items():
        print(f"  {name}: {qty}")

    print("\n--- Total gathered ---")
    for rt, qty in summary["gathered"].items():
        print(f"  {rt.name}: {qty}")

    print("\n--- Total produced ---")
    for rt, qty in summary["produced"].items():
        print(f"  {rt.name}: {qty}")

    print("\n--- Total consumed (bread eaten) ---")
    consumed = summary["consumed"]
    if consumed:
        for rt, qty in consumed.items():
            print(f"  {rt.name}: {qty}")
    else:
        print("  (none)")

    print("\n--- Tasks completed by type ---")
    for ttype, count in sorted(summary["tasks_completed"].items()):
        print(f"  {ttype}: {count}")

    print("\n--- Tasks failed by type ---")
    for ttype, count in sorted(summary["tasks_failed"].items()):
        print(f"  {ttype}: {count}")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Headless balance report")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--minutes", type=float, default=10.0)
    parser.add_argument(
        "--scenario",
        choices=["DEFAULT", "SCARCITY", "ASYMMETRIC"],
        default="DEFAULT",
        help="Named scenario to run (default: DEFAULT)",
    )
    args = parser.parse_args()

    scenario_obj = getattr(_scenarios, args.scenario)
    desc = scenario_obj.description or args.scenario
    print(f"Running seed={args.seed} for {args.minutes} sim-minutes  scenario={args.scenario} ({desc}) …")
    sim = run(args.seed, args.minutes, scenario=scenario_obj)
    report(sim)


if __name__ == "__main__":
    main()
