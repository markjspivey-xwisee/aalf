"""
Simulation engine orchestrating the autopoietic life simulation.

Manages the world tick loop, population dynamics, statistical tracking,
and exposes subscription hooks for observers.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from ..environment.world import World
from ..subscriptions.event_bus import EventBus, EventType
from .life_form import Genome, LifeForm


@dataclass
class SimulationStats:
    """Running statistics for the simulation."""
    total_ticks: int = 0
    total_births: int = 0
    total_deaths: int = 0
    peak_population: int = 0
    max_generation: int = 0
    total_autopoietic_events: int = 0
    total_autopoietic_losses: int = 0
    population_history: list[int] = field(default_factory=list)
    avg_viability_history: list[float] = field(default_factory=list)
    avg_energy_history: list[float] = field(default_factory=list)

    def record_tick(self, alive: list[LifeForm]):
        self.total_ticks += 1
        pop = len(alive)
        self.population_history.append(pop)
        if pop > self.peak_population:
            self.peak_population = pop

        if alive:
            self.avg_viability_history.append(
                sum(lf.viability for lf in alive) / len(alive)
            )
            self.avg_energy_history.append(
                sum(lf.energy for lf in alive) / len(alive)
            )
            max_gen = max(lf.generation for lf in alive)
            if max_gen > self.max_generation:
                self.max_generation = max_gen
        else:
            self.avg_viability_history.append(0)
            self.avg_energy_history.append(0)

        # Keep history bounded
        max_hist = 500
        if len(self.population_history) > max_hist:
            self.population_history = self.population_history[-max_hist:]
            self.avg_viability_history = self.avg_viability_history[-max_hist:]
            self.avg_energy_history = self.avg_energy_history[-max_hist:]


class Simulation:
    """
    Main simulation controller.

    Provides:
    - World initialization with configurable parameters
    - Step-by-step or continuous execution
    - Event bus for subscription-driven observation
    - Population management (seeding, culling, carrying capacity)
    - Statistics collection
    """

    def __init__(
        self,
        width: int = 40,
        height: int = 25,
        initial_population: int = 12,
        carrying_capacity: int = 80,
        seed: Optional[int] = None,
    ):
        import random as _random
        if seed is not None:
            _random.seed(seed)

        self.bus = EventBus()
        self.world = World(width=width, height=height)
        self.stats = SimulationStats()
        self.carrying_capacity = carrying_capacity
        self.running = False
        self.paused = False

        # Wire up internal event subscriptions
        self._setup_internal_subscriptions()

        # Seed initial population
        for _ in range(initial_population):
            genome = Genome(
                metabolic_efficiency=_random.uniform(0.7, 1.3),
                membrane_investment=_random.uniform(0.3, 0.7),
                division_threshold=_random.uniform(30, 60),
                permeability_gene=_random.uniform(0.2, 0.5),
                signal_sensitivity=_random.uniform(0.2, 0.8),
            )
            self.world.spawn_life_form(self.bus, genome=genome)

    def _setup_internal_subscriptions(self):
        """Subscribe to events for stats tracking."""
        self.bus.subscribe(EventType.LIFE_FORM_SPAWNED,
                           lambda e: setattr(self.stats, 'total_births', self.stats.total_births + 1))
        self.bus.subscribe(EventType.LIFE_FORM_DIED,
                           lambda e: setattr(self.stats, 'total_deaths', self.stats.total_deaths + 1))
        self.bus.subscribe(EventType.AUTOPOIESIS_SUSTAINED,
                           lambda e: setattr(self.stats, 'total_autopoietic_events', self.stats.total_autopoietic_events + 1))
        self.bus.subscribe(EventType.AUTOPOIESIS_LOST,
                           lambda e: setattr(self.stats, 'total_autopoietic_losses', self.stats.total_autopoietic_losses + 1))

    def step(self) -> dict:
        """Advance simulation by one tick."""
        result = self.world.tick(self.bus)

        alive = [lf for lf in self.world.life_forms if lf.alive]
        self.stats.record_tick(alive)

        # Soft carrying capacity — reduce resources if overpopulated
        if len(alive) > self.carrying_capacity:
            for rf in self.world.resources.values():
                rf.regen_rate *= 0.95

        self.bus.emit(EventType.SIMULATION_STEP, source_id=None,
                      tick=self.world.tick_count,
                      population=len(alive),
                      avg_viability=self.stats.avg_viability_history[-1] if self.stats.avg_viability_history else 0)

        return result

    def run(self, max_ticks: int = 1000, tick_callback=None, tick_delay: float = 0.0):
        """Run the simulation for up to max_ticks steps."""
        self.running = True
        self.bus.emit(EventType.SIMULATION_STARTED, source_id=None, max_ticks=max_ticks)

        for _ in range(max_ticks):
            if not self.running:
                break
            if self.paused:
                time.sleep(0.1)
                continue

            result = self.step()

            if tick_callback:
                tick_callback(self, result)

            # Check extinction
            alive = sum(1 for lf in self.world.life_forms if lf.alive)
            if alive == 0:
                break

            if tick_delay > 0:
                time.sleep(tick_delay)

        self.running = False
        self.bus.emit(EventType.SIMULATION_ENDED, source_id=None,
                      total_ticks=self.world.tick_count)

    def stop(self):
        self.running = False

    def get_alive(self) -> list[LifeForm]:
        return [lf for lf in self.world.life_forms if lf.alive]

    def get_summary(self) -> dict:
        alive = self.get_alive()
        autopoietic = [lf for lf in alive if lf.autopoietic]
        return {
            "tick": self.world.tick_count,
            "population": len(alive),
            "autopoietic": len(autopoietic),
            "peak_population": self.stats.peak_population,
            "total_births": self.stats.total_births,
            "total_deaths": self.stats.total_deaths,
            "max_generation": self.stats.max_generation,
            "avg_viability": self.stats.avg_viability_history[-1] if self.stats.avg_viability_history else 0,
            "avg_energy": self.stats.avg_energy_history[-1] if self.stats.avg_energy_history else 0,
            "events_processed": self.bus.event_count,
            "active_subscribers": self.bus.subscriber_count,
        }
