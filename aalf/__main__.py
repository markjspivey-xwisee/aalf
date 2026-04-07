"""
CLI entry point for the Autopoietic Artificial Life Forms simulation.

Usage:
    python -m aalf [options]

Options:
    --width W          World width (default: 40)
    --height H         World height (default: 25)
    --population N     Initial population (default: 12)
    --capacity N       Carrying capacity (default: 80)
    --ticks N          Max simulation ticks (default: 2000)
    --delay D          Seconds between frames (default: 0.08)
    --seed S           Random seed for reproducibility
    --headless         Run without visualization
    --stats-only       Only print final statistics
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from .core.simulation import Simulation
from .visualization.renderer import TerminalRenderer


def parse_args():
    parser = argparse.ArgumentParser(
        description="Autopoietic Artificial Life Forms — Subscription-Driven Simulation"
    )
    parser.add_argument("--width", type=int, default=40, help="World width")
    parser.add_argument("--height", type=int, default=25, help="World height")
    parser.add_argument("--population", type=int, default=12, help="Initial population")
    parser.add_argument("--capacity", type=int, default=80, help="Carrying capacity")
    parser.add_argument("--ticks", type=int, default=2000, help="Max simulation ticks")
    parser.add_argument("--delay", type=float, default=0.08, help="Delay between frames (seconds)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument("--headless", action="store_true", help="Run without visualization")
    parser.add_argument("--stats-only", action="store_true", help="Only print final stats")
    return parser.parse_args()


def main():
    args = parse_args()

    sim = Simulation(
        width=args.width,
        height=args.height,
        initial_population=args.population,
        carrying_capacity=args.capacity,
        seed=args.seed,
    )

    if args.headless or args.stats_only:
        _run_headless(sim, args)
    else:
        _run_visual(sim, args)


def _run_visual(sim: Simulation, args):
    """Run with terminal visualization."""
    renderer = TerminalRenderer(sim)

    # Hide cursor
    sys.stdout.write("\033[?25l")

    try:
        for _ in range(args.ticks):
            result = sim.step()
            renderer.display()

            if result.get("alive", 0) == 0:
                print(f"\n  {'=' * 40}")
                print(f"  EXTINCTION at tick {sim.world.tick_count}")
                print(f"  {'=' * 40}")
                break

            time.sleep(args.delay)

    except KeyboardInterrupt:
        pass
    finally:
        # Show cursor
        sys.stdout.write("\033[?25h\n")
        _print_final_stats(sim)


def _run_headless(sim: Simulation, args):
    """Run without visualization, periodic status updates."""
    report_interval = max(1, args.ticks // 20)

    try:
        for i in range(args.ticks):
            result = sim.step()

            if not args.stats_only and (i + 1) % report_interval == 0:
                s = sim.get_summary()
                print(f"[tick {s['tick']:>5}] pop={s['population']:>3} "
                      f"autopoietic={s['autopoietic']:>3} "
                      f"viability={s['avg_viability']:.2f} "
                      f"gen={s['max_generation']}")

            if result.get("alive", 0) == 0:
                print(f"EXTINCTION at tick {sim.world.tick_count}")
                break

    except KeyboardInterrupt:
        pass

    _print_final_stats(sim)


def _print_final_stats(sim: Simulation):
    """Print comprehensive final statistics."""
    s = sim.get_summary()
    alive = sim.get_alive()

    print(f"\n{'═' * 50}")
    print(f" SIMULATION COMPLETE — Final Report")
    print(f"{'═' * 50}")
    print(f" Total ticks:        {s['tick']}")
    print(f" Final population:   {s['population']}")
    print(f" Autopoietic:        {s['autopoietic']}")
    print(f" Peak population:    {s['peak_population']}")
    print(f" Total births:       {s['total_births']}")
    print(f" Total deaths:       {s['total_deaths']}")
    print(f" Max generation:     {s['max_generation']}")
    print(f" Events processed:   {s['events_processed']}")
    print(f" Active subscribers: {s['active_subscribers']}")

    if alive:
        print(f"\n Surviving Life Forms:")
        print(f" {'ID':<10} {'Gen':>4} {'Age':>5} {'Energy':>7} {'Viability':>9} {'Autopoietic'}")
        for lf in sorted(alive, key=lambda l: -l.viability)[:15]:
            ap = "✓" if lf.autopoietic else "✗"
            print(f" {lf.id:<10} {lf.generation:>4} {lf.age:>5} {lf.energy:>7.1f} {lf.viability:>9.3f} {ap}")

    # Genome diversity
    if alive:
        print(f"\n Genome Diversity (surviving population):")
        for attr in ["metabolic_efficiency", "membrane_investment", "division_threshold",
                      "permeability_gene", "signal_sensitivity"]:
            vals = [getattr(lf.genome, attr) for lf in alive]
            print(f"   {attr:<25} min={min(vals):.2f}  max={max(vals):.2f}  "
                  f"avg={sum(vals)/len(vals):.2f}")

    print(f"{'═' * 50}\n")


if __name__ == "__main__":
    main()
