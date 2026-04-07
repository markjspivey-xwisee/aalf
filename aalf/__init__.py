"""
AALF — Autopoietic Artificial Life Forms

A subscription-driven simulation of self-producing, self-maintaining
artificial life forms based on the theory of autopoiesis.

Autopoiesis (from Greek: auto = self, poiesis = creation) describes systems
that continuously produce and maintain themselves. An autopoietic system:

  1. Has a semi-permeable boundary (membrane)
  2. Contains a network of processes that regenerate all components
  3. The boundary is itself a product of the internal network
  4. Operational closure: the system defines its own identity

This simulation implements these principles with:
  - Chemical metabolism (substrate → components → membrane)
  - Event-driven architecture (publish/subscribe observation)
  - Emergent population dynamics (division, mutation, selection)
  - Spatial environment with resource fields and diffusion
"""

__version__ = "0.1.0"
