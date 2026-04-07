"""
Autopoietic Artificial Life Form.

An autopoietic system is defined by:
1. A boundary (membrane) that distinguishes self from environment
2. A network of processes that continuously regenerate the boundary
   and all internal components
3. The system exists as a unity only as long as this self-producing
   organization is maintained

This module implements these principles as a computational entity.
"""

from __future__ import annotations

import random
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from ..subscriptions.event_bus import EventBus, EventType
from .chemistry import MoleculeType, attempt_reactions
from .membrane import Membrane


@dataclass
class Genome:
    """Simple genome controlling life form parameters."""
    metabolic_efficiency: float = 1.0   # reaction rate bonus
    membrane_investment: float = 0.5    # priority for membrane repair vs growth
    division_threshold: float = 50.0    # internal energy needed to divide
    permeability_gene: float = 0.3      # base membrane permeability
    signal_sensitivity: float = 0.5     # responsiveness to external signals
    aggression: float = 0.1             # tendency to compete for resources

    def mutate(self, rate: float = 0.05) -> Genome:
        """Return a mutated copy."""
        def _m(val: float) -> float:
            if random.random() < rate:
                return max(0.01, min(2.0, val + random.gauss(0, 0.1)))
            return val

        return Genome(
            metabolic_efficiency=_m(self.metabolic_efficiency),
            membrane_investment=_m(self.membrane_investment),
            division_threshold=max(20, self.division_threshold + random.gauss(0, 3) if random.random() < rate else self.division_threshold),
            permeability_gene=max(0.05, min(0.9, _m(self.permeability_gene))),
            signal_sensitivity=_m(self.signal_sensitivity),
            aggression=max(0, min(1.0, _m(self.aggression))),
        )


@dataclass
class LifeForm:
    """
    An autopoietic artificial life form.

    Maintains itself through continuous self-production:
    - Imports substrates through its membrane
    - Metabolizes them into internal components
    - Uses components to repair/extend its membrane
    - Achieves operational closure: the process network that produces
      the boundary is itself enabled by that boundary
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    genome: Genome = field(default_factory=Genome)
    membrane: Membrane = field(default_factory=Membrane)
    age: int = 0
    generation: int = 0
    parent_id: Optional[str] = None

    # Position in environment
    x: float = 0.0
    y: float = 0.0

    # Internal chemistry
    inventory: dict[MoleculeType, float] = field(default_factory=lambda: defaultdict(float))
    energy: float = 15.0

    # State tracking
    alive: bool = True
    autopoietic: bool = True  # is self-production loop intact?
    _ticks_without_production: int = 0
    _total_components_produced: int = 0
    _division_cooldown: int = 0

    def __post_init__(self):
        self.membrane.permeability = self.genome.permeability_gene
        # Seed with minimal starting components
        if not self.inventory:
            self.inventory = defaultdict(float, {
                MoleculeType.ENZYME: 3.0,
                MoleculeType.MEMBRANE_LIPID: 8.0,
                MoleculeType.TRANSPORTER: 2.0,
            })

    @property
    def viability(self) -> float:
        """Overall health score 0-1."""
        if not self.alive:
            return 0.0
        membrane_score = self.membrane.integrity
        energy_score = min(1.0, self.energy / 20.0)
        enzyme_score = min(1.0, self.inventory.get(MoleculeType.ENZYME, 0) / 3.0)
        return (membrane_score * 0.4 + energy_score * 0.3 + enzyme_score * 0.3)

    @property
    def size(self) -> float:
        """Approximate size based on membrane and contents."""
        return 1.0 + self.membrane.lipid_count * 0.05

    def metabolize(self, bus: EventBus) -> None:
        """Run one metabolic tick: attempt reactions, manage components."""
        if not self.alive:
            return

        has_catalyst = self.inventory.get(MoleculeType.CATALYST, 0) > 0
        enzyme_bonus = min(0.3, self.inventory.get(MoleculeType.ENZYME, 0) * 0.05)

        energy_delta, completed = attempt_reactions(
            self.inventory, self.energy, has_catalyst,
            enzyme_bonus * self.genome.metabolic_efficiency,
        )
        self.energy += energy_delta

        if completed:
            self._ticks_without_production = 0
            self._total_components_produced += len(completed)
            for rxn_name in completed:
                bus.emit(EventType.COMPONENT_PRODUCED, self.id, reaction=rxn_name)
        else:
            self._ticks_without_production += 1

        bus.emit(EventType.METABOLISM_TICK, self.id,
                 energy=self.energy, viability=self.viability)

    def maintain_membrane(self, bus: EventBus) -> None:
        """Self-repair: the defining act of autopoiesis."""
        if not self.alive:
            return

        # Decay
        damage = self.membrane.decay()
        if damage > 0.05:
            bus.emit(EventType.MEMBRANE_DAMAGED, self.id, damage=damage)

        # Repair with produced lipids and transporters
        # membrane_investment gene controls how aggressively to build membrane
        # Always repair damage; invest surplus based on gene
        lipids_in_inv = self.inventory.get(MoleculeType.MEMBRANE_LIPID, 0)
        if self.membrane.is_damaged:
            lipids_avail = lipids_in_inv  # use everything when damaged
        else:
            lipids_avail = lipids_in_inv * (0.3 + self.genome.membrane_investment * 0.7)
        trans_avail = self.inventory.get(MoleculeType.TRANSPORTER, 0) * 0.7

        lipids_used, trans_used = self.membrane.repair(lipids_avail, trans_avail)
        self.inventory[MoleculeType.MEMBRANE_LIPID] -= lipids_used
        self.inventory[MoleculeType.TRANSPORTER] -= trans_used

        if lipids_used > 0 or trans_used > 0:
            bus.emit(EventType.MEMBRANE_REPAIRED, self.id,
                     lipids_used=lipids_used, trans_used=trans_used,
                     integrity=self.membrane.integrity)

        # Check autopoietic status
        if self._ticks_without_production > 15:
            if self.autopoietic:
                self.autopoietic = False
                bus.emit(EventType.AUTOPOIESIS_LOST, self.id)
        elif not self.autopoietic and self._ticks_without_production == 0:
            self.autopoietic = True
            bus.emit(EventType.AUTOPOIESIS_SUSTAINED, self.id)

        # Death check
        if not self.membrane.is_viable or self.energy <= 0:
            self.die(bus)
        elif self.membrane.integrity < self.membrane.BREACH_THRESHOLD:
            bus.emit(EventType.MEMBRANE_BREACHED, self.id)
            self.die(bus)

    def import_resources(self, available: dict[MoleculeType, float], bus: EventBus) -> dict[MoleculeType, float]:
        """
        Import substrates through the membrane.
        Returns dict of amounts actually consumed from environment.
        """
        consumed: dict[MoleculeType, float] = {}
        if not self.alive:
            return consumed

        capacity = self.membrane.transport_capacity
        importable = [MoleculeType.SUBSTRATE_A, MoleculeType.SUBSTRATE_B, MoleculeType.CATALYST]

        for mol in importable:
            env_amount = available.get(mol, 0)
            if env_amount <= 0:
                continue
            transfer = min(env_amount, capacity * 0.4)
            if transfer > 0.01:
                self.inventory[mol] += transfer
                consumed[mol] = transfer
                bus.emit(EventType.RESOURCE_CONSUMED, self.id,
                         molecule=mol.value, amount=transfer)

        return consumed

    def can_divide(self) -> bool:
        if self._division_cooldown > 0:
            return False
        return (
            self.energy >= self.genome.division_threshold
            and self.membrane.can_divide()
            and self.autopoietic
            and self.inventory.get(MoleculeType.ENZYME, 0) >= 0.5
        )

    def divide(self, bus: EventBus) -> Optional[LifeForm]:
        """Reproduce by division, producing a daughter cell."""
        if not self.can_divide():
            return None

        daughter_membrane = self.membrane.divide()
        daughter_genome = self.genome.mutate()

        # Split resources
        daughter_inventory: dict[MoleculeType, float] = defaultdict(float)
        for mol, amount in self.inventory.items():
            share = amount * random.uniform(0.35, 0.55)
            daughter_inventory[mol] = share
            self.inventory[mol] -= share

        daughter_energy = self.energy * 0.45
        self.energy -= daughter_energy

        daughter = LifeForm(
            genome=daughter_genome,
            membrane=daughter_membrane,
            generation=self.generation + 1,
            parent_id=self.id,
            x=self.x + random.uniform(-1.5, 1.5),
            y=self.y + random.uniform(-1.5, 1.5),
            inventory=daughter_inventory,
            energy=daughter_energy,
        )

        self._division_cooldown = 20
        bus.emit(EventType.LIFE_FORM_DIVIDED, self.id,
                 daughter_id=daughter.id, generation=daughter.generation)
        bus.emit(EventType.LIFE_FORM_SPAWNED, daughter.id,
                 parent_id=self.id, generation=daughter.generation)
        return daughter

    def die(self, bus: EventBus) -> dict[MoleculeType, float]:
        """Death: release all components back to the environment."""
        self.alive = False
        self.autopoietic = False
        released = dict(self.inventory)
        # Membrane components also return
        released[MoleculeType.MEMBRANE_LIPID] = released.get(MoleculeType.MEMBRANE_LIPID, 0) + self.membrane.lipid_count
        self.inventory = defaultdict(float)
        bus.emit(EventType.LIFE_FORM_DIED, self.id,
                 age=self.age, generation=self.generation, released=str(released))
        return released

    def tick(self, bus: EventBus) -> None:
        """One full simulation step for this life form."""
        if not self.alive:
            return
        self.age += 1
        if self._division_cooldown > 0:
            self._division_cooldown -= 1

        # Basal energy cost of being alive
        self.energy -= 0.15 + self.size * 0.02

        # Enzyme decay
        if self.inventory[MoleculeType.ENZYME] > 0:
            self.inventory[MoleculeType.ENZYME] = max(
                0, self.inventory[MoleculeType.ENZYME] - 0.04
            )

        # Age-related stress (old age increases energy cost)
        if self.age > 300:
            self.energy -= (self.age - 300) * 0.002

        self.metabolize(bus)
        self.maintain_membrane(bus)
