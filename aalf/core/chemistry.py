"""
Chemical substrate for autopoietic life.

Defines the molecules, reactions, and thermodynamics that underpin
metabolism and self-production in the simulation.
"""

from __future__ import annotations

import enum
import random
from dataclasses import dataclass, field


class MoleculeType(enum.Enum):
    """Fundamental molecule types in the simulation chemistry."""
    # Raw substrates (available in environment)
    SUBSTRATE_A = "sub_a"      # Energy-rich substrate
    SUBSTRATE_B = "sub_b"      # Structural substrate
    CATALYST = "catalyst"      # Rare catalyst

    # Internal components (produced by metabolism)
    MEMBRANE_LIPID = "lipid"   # Membrane building block
    ENZYME = "enzyme"          # Catalyzes internal reactions
    TRANSPORTER = "transport"  # Membrane channel for import/export
    SIGNAL = "signal"          # Inter-cell signaling molecule
    ENERGY = "energy"          # Internal energy currency (like ATP)
    WASTE = "waste"            # Metabolic byproduct


@dataclass(frozen=True)
class Reaction:
    """A chemical reaction: inputs → outputs with energy cost/yield."""
    name: str
    inputs: dict[MoleculeType, int]
    outputs: dict[MoleculeType, int]
    energy_cost: float = 0.0
    catalyst_required: bool = False
    rate: float = 1.0  # probability of occurring per tick when substrates available

    def can_proceed(self, inventory: dict[MoleculeType, float], energy: float) -> bool:
        if energy < self.energy_cost:
            return False
        for mol, amount in self.inputs.items():
            if inventory.get(mol, 0) < amount:
                return False
        return True

    def execute(self, inventory: dict[MoleculeType, float]) -> float:
        """Execute reaction, modifying inventory in-place. Returns energy delta."""
        for mol, amount in self.inputs.items():
            inventory[mol] = inventory.get(mol, 0) - amount
        for mol, amount in self.outputs.items():
            inventory[mol] = inventory.get(mol, 0) + amount
        return -self.energy_cost


# ─── Core metabolic reactions ───────────────────────────────────────

REACTIONS = {
    "energy_production": Reaction(
        name="energy_production",
        inputs={MoleculeType.SUBSTRATE_A: 1},
        outputs={MoleculeType.ENERGY: 4, MoleculeType.WASTE: 1},
        energy_cost=-4.0,  # net gain
        rate=0.95,
    ),
    "lipid_synthesis": Reaction(
        name="lipid_synthesis",
        inputs={MoleculeType.SUBSTRATE_B: 1, MoleculeType.ENERGY: 1},
        outputs={MoleculeType.MEMBRANE_LIPID: 3},
        energy_cost=1.0,
        rate=0.85,
    ),
    "enzyme_synthesis": Reaction(
        name="enzyme_synthesis",
        inputs={MoleculeType.SUBSTRATE_A: 1, MoleculeType.SUBSTRATE_B: 1, MoleculeType.ENERGY: 2},
        outputs={MoleculeType.ENZYME: 1},
        energy_cost=2.0,
        catalyst_required=True,
        rate=0.4,
    ),
    "transporter_synthesis": Reaction(
        name="transporter_synthesis",
        inputs={MoleculeType.SUBSTRATE_B: 2, MoleculeType.ENERGY: 1},
        outputs={MoleculeType.TRANSPORTER: 1},
        energy_cost=1.5,
        rate=0.5,
    ),
    "signal_synthesis": Reaction(
        name="signal_synthesis",
        inputs={MoleculeType.SUBSTRATE_A: 1, MoleculeType.ENERGY: 1},
        outputs={MoleculeType.SIGNAL: 2},
        energy_cost=1.0,
        rate=0.3,
    ),
    "waste_export": Reaction(
        name="waste_export",
        inputs={MoleculeType.WASTE: 3},
        outputs={},  # expelled to environment
        energy_cost=0.5,
        rate=0.8,
    ),
}


def attempt_reactions(
    inventory: dict[MoleculeType, float],
    energy: float,
    has_catalyst: bool = False,
    enzyme_bonus: float = 0.0,
) -> tuple[float, list[str]]:
    """
    Attempt all applicable reactions for one metabolic tick.
    Returns (energy_delta, list_of_completed_reaction_names).
    """
    completed = []
    energy_delta = 0.0

    # Prioritize energy production, then maintenance, then growth
    priority_order = [
        "energy_production",
        "waste_export",
        "lipid_synthesis",
        "transporter_synthesis",
        "enzyme_synthesis",
        "signal_synthesis",
    ]

    for rxn_name in priority_order:
        rxn = REACTIONS[rxn_name]
        if rxn.catalyst_required and not has_catalyst:
            continue
        effective_rate = min(1.0, rxn.rate + enzyme_bonus)
        if rxn.can_proceed(inventory, energy + energy_delta) and random.random() < effective_rate:
            delta = rxn.execute(inventory)
            energy_delta += delta
            completed.append(rxn_name)

    return energy_delta, completed
