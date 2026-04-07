"""
Environment / World for the autopoietic life simulation.

The environment provides:
- A 2D toroidal grid with continuous coordinates
- Resource fields that diffuse and regenerate
- Spatial locality for life form interactions
- Structural coupling between life forms and their medium
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from ..core.chemistry import MoleculeType
from ..core.life_form import LifeForm
from ..subscriptions.event_bus import EventBus, EventType


@dataclass
class ResourceField:
    """A spatial field of a particular molecule type."""
    molecule: MoleculeType
    grid: list[list[float]] = field(default_factory=list)
    regen_rate: float = 0.05
    diffusion_rate: float = 0.1
    max_density: float = 10.0

    def init_grid(self, width: int, height: int, initial_density: float = 3.0):
        self.grid = [
            [initial_density + random.uniform(-1, 1) for _ in range(width)]
            for _ in range(height)
        ]

    def get(self, x: int, y: int) -> float:
        if not self.grid:
            return 0.0
        h, w = len(self.grid), len(self.grid[0])
        return self.grid[y % h][x % w]

    def consume(self, x: int, y: int, amount: float) -> float:
        h, w = len(self.grid), len(self.grid[0])
        gy, gx = y % h, x % w
        actual = min(self.grid[gy][gx], amount)
        self.grid[gy][gx] -= actual
        return actual

    def deposit(self, x: int, y: int, amount: float):
        h, w = len(self.grid), len(self.grid[0])
        self.grid[y % h][x % w] = min(
            self.max_density, self.grid[y % h][x % w] + amount
        )

    def regenerate(self):
        """Natural resource regeneration."""
        for row in self.grid:
            for i in range(len(row)):
                if row[i] < self.max_density:
                    row[i] = min(self.max_density, row[i] + self.regen_rate * random.uniform(0.5, 1.5))

    def diffuse(self):
        """Simple diffusion: each cell averages slightly with neighbors."""
        if not self.grid:
            return
        h, w = len(self.grid), len(self.grid[0])
        new_grid = [[0.0] * w for _ in range(h)]
        dr = self.diffusion_rate
        for y in range(h):
            for x in range(w):
                neighbors_avg = (
                    self.grid[(y - 1) % h][x] +
                    self.grid[(y + 1) % h][x] +
                    self.grid[y][(x - 1) % w] +
                    self.grid[y][(x + 1) % w]
                ) / 4.0
                new_grid[y][x] = self.grid[y][x] * (1 - dr) + neighbors_avg * dr
        self.grid = new_grid


@dataclass
class World:
    """
    The medium in which autopoietic life forms exist.

    Implements structural coupling: life forms perturb the environment,
    and the environment perturbs life forms, but neither "instructs" the other.
    """

    width: int = 40
    height: int = 25
    life_forms: list[LifeForm] = field(default_factory=list)
    resources: dict[MoleculeType, ResourceField] = field(default_factory=dict)
    tick_count: int = 0

    # Spatial grid for fast neighbor lookups
    _spatial_grid: dict[tuple[int, int], list[LifeForm]] = field(default_factory=lambda: defaultdict(list))

    def __post_init__(self):
        # Initialize resource fields
        for mol, (regen, diffuse, density) in {
            MoleculeType.SUBSTRATE_A: (0.15, 0.15, 5.0),
            MoleculeType.SUBSTRATE_B: (0.10, 0.10, 4.0),
            MoleculeType.CATALYST:    (0.02, 0.05, 0.8),
        }.items():
            rf = ResourceField(molecule=mol, regen_rate=regen, diffusion_rate=diffuse)
            rf.init_grid(self.width, self.height, density)
            self.resources[mol] = rf

        # Create random resource hotspots
        for _ in range(3):
            hx, hy = random.randint(0, self.width - 1), random.randint(0, self.height - 1)
            for mol_field in self.resources.values():
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        mol_field.deposit(hx + dx, hy + dy, random.uniform(2, 5))

    def _rebuild_spatial_grid(self):
        self._spatial_grid.clear()
        for lf in self.life_forms:
            if lf.alive:
                key = (int(lf.x) % self.width, int(lf.y) % self.height)
                self._spatial_grid[key].append(lf)

    def neighbors_of(self, lf: LifeForm, radius: float = 2.0) -> list[LifeForm]:
        """Find nearby life forms within radius."""
        result = []
        cx, cy = int(lf.x), int(lf.y)
        r = int(radius) + 1
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                key = ((cx + dx) % self.width, (cy + dy) % self.height)
                for other in self._spatial_grid.get(key, []):
                    if other.id != lf.id and other.alive:
                        dist = math.sqrt((lf.x - other.x) ** 2 + (lf.y - other.y) ** 2)
                        if dist <= radius:
                            result.append(other)
        return result

    def spawn_life_form(self, bus: EventBus, x: Optional[float] = None, y: Optional[float] = None, **kwargs) -> LifeForm:
        """Create a new life form in the world."""
        lf = LifeForm(
            x=x if x is not None else random.uniform(0, self.width),
            y=y if y is not None else random.uniform(0, self.height),
            **kwargs,
        )
        self.life_forms.append(lf)
        bus.emit(EventType.LIFE_FORM_SPAWNED, lf.id,
                 x=lf.x, y=lf.y, generation=lf.generation)
        return lf

    def resource_at(self, x: float, y: float) -> dict[MoleculeType, float]:
        """Get available resources at a position."""
        gx, gy = int(x) % self.width, int(y) % self.height
        return {mol: field.get(gx, gy) for mol, field in self.resources.items()}

    def consume_at(self, x: float, y: float, amounts: dict[MoleculeType, float]):
        """Remove resources from a position."""
        gx, gy = int(x) % self.width, int(y) % self.height
        for mol, amount in amounts.items():
            if mol in self.resources:
                self.resources[mol].consume(gx, gy, amount)

    def deposit_at(self, x: float, y: float, materials: dict[MoleculeType, float]):
        """Add materials to a position (e.g. when a cell dies)."""
        gx, gy = int(x) % self.width, int(y) % self.height
        for mol, amount in materials.items():
            if mol in self.resources:
                self.resources[mol].deposit(gx, gy, amount)

    def _move_life_form(self, lf: LifeForm):
        """Brownian motion + gradient following."""
        # Random walk
        lf.x += random.gauss(0, 0.3)
        lf.y += random.gauss(0, 0.3)

        # Chemotaxis: move toward substrate_a gradient
        gx, gy = int(lf.x) % self.width, int(lf.y) % self.height
        best_dx, best_dy = 0, 0
        best_val = self.resources[MoleculeType.SUBSTRATE_A].get(gx, gy)
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            val = self.resources[MoleculeType.SUBSTRATE_A].get(gx + dx, gy + dy)
            if val > best_val:
                best_val = val
                best_dx, best_dy = dx, dy
        lf.x += best_dx * 0.15
        lf.y += best_dy * 0.15

        # Wrap (toroidal)
        lf.x = lf.x % self.width
        lf.y = lf.y % self.height

    def _handle_interactions(self, bus: EventBus):
        """Handle interactions between nearby life forms."""
        for lf in self.life_forms:
            if not lf.alive:
                continue
            neighbors = self.neighbors_of(lf, radius=2.0)
            for other in neighbors:
                # Signal exchange
                if lf.inventory.get(MoleculeType.SIGNAL, 0) > 0.5:
                    transfer = min(0.3, lf.inventory[MoleculeType.SIGNAL])
                    lf.inventory[MoleculeType.SIGNAL] -= transfer
                    other.inventory[MoleculeType.SIGNAL] += transfer * other.genome.signal_sensitivity
                    bus.emit(EventType.RESOURCE_EXCHANGED, lf.id,
                             target_id=other.id, molecule="signal", amount=transfer)

                # Structural coupling notification
                dist = math.sqrt((lf.x - other.x) ** 2 + (lf.y - other.y) ** 2)
                if dist < 1.0:
                    bus.emit(EventType.COUPLING_FORMED, lf.id,
                             partner_id=other.id, distance=dist)

    def tick(self, bus: EventBus) -> dict:
        """Advance the world by one step."""
        self.tick_count += 1
        self._rebuild_spatial_grid()

        alive_before = sum(1 for lf in self.life_forms if lf.alive)

        # 1. Resource dynamics
        for rf in self.resources.values():
            rf.regenerate()
            rf.diffuse()

        # 2. Life form actions
        new_life_forms = []
        for lf in self.life_forms:
            if not lf.alive:
                continue

            # Movement
            self._move_life_form(lf)

            # Import resources from environment
            available = self.resource_at(lf.x, lf.y)
            consumed = lf.import_resources(available, bus)
            self.consume_at(lf.x, lf.y, consumed)

            # Internal tick (metabolism + membrane maintenance)
            lf.tick(bus)

            # Division check
            if lf.alive and lf.can_divide():
                daughter = lf.divide(bus)
                if daughter:
                    daughter.x = daughter.x % self.width
                    daughter.y = daughter.y % self.height
                    new_life_forms.append(daughter)

            # Return waste to environment
            waste = lf.inventory.get(MoleculeType.WASTE, 0)
            if waste > 0:
                self.deposit_at(lf.x, lf.y, {MoleculeType.WASTE: waste})
                lf.inventory[MoleculeType.WASTE] = 0

        # 3. Handle deaths — release materials
        for lf in self.life_forms:
            if not lf.alive:
                released = {k: v for k, v in lf.inventory.items() if v > 0}
                if released:
                    self.deposit_at(lf.x, lf.y, released)
                    lf.inventory = defaultdict(float)

        # 4. Add new life forms
        self.life_forms.extend(new_life_forms)

        # 5. Interactions
        self._handle_interactions(bus)

        # Clean up dead (keep recent for history, remove very old dead)
        self.life_forms = [
            lf for lf in self.life_forms
            if lf.alive or (self.tick_count - lf.age < 50)
        ]

        alive_after = sum(1 for lf in self.life_forms if lf.alive)

        bus.emit(EventType.ENVIRONMENT_TICK, source_id=None,
                 tick=self.tick_count, alive=alive_after,
                 born=len(new_life_forms), died=alive_before - alive_after + len(new_life_forms))

        return {
            "tick": self.tick_count,
            "alive": alive_after,
            "born": len(new_life_forms),
            "died": alive_before - alive_after + len(new_life_forms),
        }
