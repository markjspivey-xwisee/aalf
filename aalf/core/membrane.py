"""
Membrane model for autopoietic life forms.

The membrane is the defining boundary of an autopoietic system — it is both
produced by the internal network AND enables that network to function by
maintaining organizational closure.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

from .chemistry import MoleculeType


@dataclass
class Membrane:
    """
    Semi-permeable boundary of an autopoietic unit.

    Properties:
    - integrity: 0.0 (destroyed) → 1.0 (perfect)
    - permeability: controls import/export rates
    - lipid_count: structural molecules composing the membrane
    - transporter_count: channels for selective transport
    """

    integrity: float = 1.0
    permeability: float = 0.3
    lipid_count: float = 20.0
    transporter_count: float = 3.0

    # Thresholds
    MIN_LIPIDS_VIABLE: float = 5.0
    LIPIDS_FOR_FULL_INTEGRITY: float = 25.0
    DECAY_RATE: float = 0.02
    DAMAGE_THRESHOLD: float = 0.4
    BREACH_THRESHOLD: float = 0.15

    @property
    def is_viable(self) -> bool:
        return self.integrity > self.BREACH_THRESHOLD and self.lipid_count >= self.MIN_LIPIDS_VIABLE

    @property
    def is_damaged(self) -> bool:
        return self.integrity < self.DAMAGE_THRESHOLD

    @property
    def transport_capacity(self) -> float:
        """How much material can cross per tick."""
        base = self.permeability * self.integrity
        channel_bonus = min(self.transporter_count * 0.1, 0.5)
        return base + channel_bonus

    def decay(self) -> float:
        """Natural decay of membrane components. Returns damage amount."""
        lipid_loss = self.DECAY_RATE * (1.0 + random.uniform(0, 0.5))
        self.lipid_count = max(0, self.lipid_count - lipid_loss)
        self.transporter_count = max(0, self.transporter_count - self.DECAY_RATE * 0.3)

        # Recalculate integrity from lipid count
        self.integrity = min(1.0, self.lipid_count / self.LIPIDS_FOR_FULL_INTEGRITY)
        return lipid_loss

    def repair(self, lipids_available: float, transporters_available: float) -> tuple[float, float]:
        """
        Incorporate new lipids/transporters into the membrane.
        Allows growth beyond full integrity for eventual division.
        Returns (lipids_used, transporters_used).
        """
        # Allow growth up to 2x full integrity (needed for division)
        max_lipids = self.LIPIDS_FOR_FULL_INTEGRITY * 2.0
        lipid_capacity = max_lipids - self.lipid_count
        lipids_used = min(lipids_available, max(0, lipid_capacity))
        self.lipid_count += lipids_used

        trans_used = min(transporters_available, max(0, 10.0 - self.transporter_count))
        self.transporter_count += trans_used

        self.integrity = min(1.0, self.lipid_count / self.LIPIDS_FOR_FULL_INTEGRITY)
        return lipids_used, trans_used

    def environmental_damage(self, severity: float = 0.1) -> None:
        """External damage (toxins, collisions, etc.)."""
        loss = severity * random.uniform(0.5, 1.5)
        self.lipid_count = max(0, self.lipid_count - loss)
        self.integrity = min(1.0, self.lipid_count / self.LIPIDS_FOR_FULL_INTEGRITY)

    def can_divide(self) -> bool:
        """Enough membrane material to split into two viable cells."""
        return self.lipid_count >= self.LIPIDS_FOR_FULL_INTEGRITY * 1.2 and self.integrity > 0.7

    def divide(self) -> Membrane:
        """Split membrane roughly in half, returning the daughter membrane."""
        half_lipids = self.lipid_count / 2.0
        half_trans = self.transporter_count / 2.0
        self.lipid_count = half_lipids
        self.transporter_count = half_trans
        self.integrity = min(1.0, self.lipid_count / self.LIPIDS_FOR_FULL_INTEGRITY)
        return Membrane(
            lipid_count=half_lipids,
            transporter_count=half_trans,
            integrity=min(1.0, half_lipids / self.LIPIDS_FOR_FULL_INTEGRITY),
            permeability=self.permeability + random.uniform(-0.05, 0.05),
        )
