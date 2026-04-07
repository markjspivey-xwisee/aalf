"""
Terminal-based visualization for the autopoietic life simulation.

Renders the world state, life forms, resources, and statistics
using Unicode characters and ANSI colors in the terminal.
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from typing import Optional

from ..core.chemistry import MoleculeType
from ..core.life_form import LifeForm
from ..core.simulation import Simulation
from ..environment.world import World
from ..subscriptions.event_bus import EventBus, EventType, Event


# ANSI color codes
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    BG_BLACK = "\033[40m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"
    BG_CYAN = "\033[46m"

    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_MAGENTA = "\033[95m"


def _life_form_char(lf: LifeForm) -> str:
    """Choose a character representing the life form's state."""
    if not lf.alive:
        return f"{C.DIM}·{C.RESET}"

    if not lf.autopoietic:
        return f"{C.RED}○{C.RESET}"

    v = lf.viability
    if v > 0.8:
        color = C.BRIGHT_GREEN
    elif v > 0.5:
        color = C.GREEN
    elif v > 0.3:
        color = C.YELLOW
    else:
        color = C.BRIGHT_RED

    # Size/generation variants
    if lf.membrane.can_divide():
        char = "◉"
    elif lf.generation >= 5:
        char = "●"
    elif lf.generation >= 2:
        char = "◎"
    else:
        char = "○"

    return f"{color}{char}{C.RESET}"


def _resource_bg(sub_a: float, sub_b: float) -> str:
    """Background shade based on resource density."""
    total = sub_a + sub_b
    if total > 8:
        return f"{C.BG_CYAN} "
    elif total > 5:
        return f"{C.BG_BLUE} "
    elif total > 2:
        return f"{C.BG_GREEN} "
    else:
        return f"{C.BG_BLACK} "


def _sparkline(values: list[float], width: int = 30) -> str:
    """Render a sparkline from a list of values."""
    if not values:
        return ""
    blocks = "▁▂▃▄▅▆▇█"
    recent = values[-width:]
    if not recent:
        return ""
    mn, mx = min(recent), max(recent)
    rng = mx - mn if mx != mn else 1
    return "".join(blocks[min(7, int((v - mn) / rng * 7))] for v in recent)


class TerminalRenderer:
    """
    Renders the simulation state to the terminal.

    Features:
    - World grid with resource heatmap background
    - Life forms as colored Unicode glyphs
    - Stats dashboard
    - Event log (subscription-driven)
    - Population sparkline
    """

    def __init__(self, sim: Simulation, event_log_size: int = 8):
        self.sim = sim
        self.event_log: list[str] = []
        self.event_log_size = event_log_size
        self._setup_event_log()

    def _setup_event_log(self):
        """Subscribe to interesting events for the log."""
        interesting = [
            EventType.LIFE_FORM_SPAWNED,
            EventType.LIFE_FORM_DIED,
            EventType.LIFE_FORM_DIVIDED,
            EventType.AUTOPOIESIS_SUSTAINED,
            EventType.AUTOPOIESIS_LOST,
            EventType.MEMBRANE_BREACHED,
            EventType.CLUSTER_FORMED,
        ]

        def _log_event(event: Event):
            icons = {
                EventType.LIFE_FORM_SPAWNED: f"{C.GREEN}+{C.RESET}",
                EventType.LIFE_FORM_DIED: f"{C.RED}✗{C.RESET}",
                EventType.LIFE_FORM_DIVIDED: f"{C.BRIGHT_CYAN}÷{C.RESET}",
                EventType.AUTOPOIESIS_SUSTAINED: f"{C.BRIGHT_GREEN}◆{C.RESET}",
                EventType.AUTOPOIESIS_LOST: f"{C.BRIGHT_RED}◇{C.RESET}",
                EventType.MEMBRANE_BREACHED: f"{C.RED}!{C.RESET}",
                EventType.CLUSTER_FORMED: f"{C.MAGENTA}⊕{C.RESET}",
            }
            icon = icons.get(event.event_type, "·")
            src = event.source_id[:6] if event.source_id else "world"
            detail = ""
            if event.event_type == EventType.LIFE_FORM_DIVIDED:
                detail = f" → {event.data.get('daughter_id', '?')[:6]} gen{event.data.get('generation', '?')}"
            elif event.event_type == EventType.LIFE_FORM_DIED:
                detail = f" age={event.data.get('age', '?')} gen{event.data.get('generation', '?')}"
            self.event_log.append(f"  {icon} [{src}] {event.event_type.value}{detail}")
            if len(self.event_log) > self.event_log_size:
                self.event_log = self.event_log[-self.event_log_size:]

        self.sim.bus.subscribe(interesting, _log_event)

    def render(self) -> str:
        """Render the full simulation frame as a string."""
        world = self.sim.world
        lines: list[str] = []

        # Header
        summary = self.sim.get_summary()
        lines.append("")
        lines.append(f"  {C.BOLD}{C.BRIGHT_CYAN}═══ AUTOPOIETIC ARTIFICIAL LIFE ═══{C.RESET}")
        lines.append(f"  {C.DIM}Subscription-Driven Simulation{C.RESET}")
        lines.append("")

        # Build cell occupancy map
        occupancy: dict[tuple[int, int], list[LifeForm]] = defaultdict(list)
        for lf in world.life_forms:
            if lf.alive:
                key = (int(lf.x) % world.width, int(lf.y) % world.height)
                occupancy[key].append(lf)

        # World grid
        lines.append(f"  {C.DIM}┌{'─' * world.width}┐{C.RESET}")
        for y in range(world.height):
            row = f"  {C.DIM}│{C.RESET}"
            for x in range(world.width):
                lfs = occupancy.get((x, y), [])
                if lfs:
                    # Show the most viable life form at this cell
                    best = max(lfs, key=lambda l: l.viability)
                    row += _life_form_char(best)
                else:
                    sub_a = world.resources[MoleculeType.SUBSTRATE_A].get(x, y)
                    sub_b = world.resources[MoleculeType.SUBSTRATE_B].get(x, y)
                    total = sub_a + sub_b
                    if total > 7:
                        row += f"{C.CYAN}░{C.RESET}"
                    elif total > 4:
                        row += f"{C.BLUE}·{C.RESET}"
                    else:
                        row += f"{C.DIM} {C.RESET}"
            row += f"{C.DIM}│{C.RESET}"
            lines.append(row)
        lines.append(f"  {C.DIM}└{'─' * world.width}┘{C.RESET}")

        # Stats panel
        lines.append("")
        pop = summary["population"]
        auto = summary["autopoietic"]
        lines.append(f"  {C.BOLD}Tick{C.RESET} {summary['tick']:>5}  "
                      f"{C.BOLD}Pop{C.RESET} {pop:>3}  "
                      f"{C.BOLD}Autopoietic{C.RESET} {auto:>3} "
                      f"({auto/pop*100:.0f}%)" if pop > 0 else
                      f"  {C.BOLD}Tick{C.RESET} {summary['tick']:>5}  "
                      f"{C.BRIGHT_RED}EXTINCTION{C.RESET}")

        lines.append(f"  {C.BOLD}Births{C.RESET} {summary['total_births']:>4}  "
                      f"{C.BOLD}Deaths{C.RESET} {summary['total_deaths']:>4}  "
                      f"{C.BOLD}Peak{C.RESET} {summary['peak_population']:>3}  "
                      f"{C.BOLD}MaxGen{C.RESET} {summary['max_generation']:>3}")

        lines.append(f"  {C.BOLD}Viability{C.RESET} {summary['avg_viability']:.2f}  "
                      f"{C.BOLD}Energy{C.RESET} {summary['avg_energy']:.1f}  "
                      f"{C.BOLD}Events{C.RESET} {summary['events_processed']:>6}  "
                      f"{C.BOLD}Subs{C.RESET} {summary['active_subscribers']:>2}")

        # Population sparkline
        pop_hist = self.sim.stats.population_history
        if pop_hist:
            spark = _sparkline([float(p) for p in pop_hist], width=40)
            lines.append(f"  {C.BOLD}Population{C.RESET} {C.GREEN}{spark}{C.RESET}")

        viab_hist = self.sim.stats.avg_viability_history
        if viab_hist:
            spark = _sparkline(viab_hist, width=40)
            lines.append(f"  {C.BOLD}Viability {C.RESET} {C.CYAN}{spark}{C.RESET}")

        # Event log
        if self.event_log:
            lines.append("")
            lines.append(f"  {C.BOLD}{C.DIM}── Event Log ──{C.RESET}")
            for entry in self.event_log[-self.event_log_size:]:
                lines.append(entry)

        # Legend
        lines.append("")
        lines.append(f"  {C.DIM}Legend: "
                      f"{C.BRIGHT_GREEN}○{C.DIM}=healthy "
                      f"{C.YELLOW}○{C.DIM}=stressed "
                      f"{C.RED}○{C.DIM}=non-autopoietic "
                      f"{C.BRIGHT_CYAN}◉{C.DIM}=ready to divide "
                      f"{C.CYAN}░{C.DIM}=resources{C.RESET}")
        lines.append(f"  {C.DIM}Press Ctrl+C to stop{C.RESET}")
        lines.append("")

        return "\n".join(lines)

    def display(self):
        """Clear terminal and render current frame."""
        sys.stdout.write("\033[H\033[J")  # clear screen
        sys.stdout.write(self.render())
        sys.stdout.flush()
