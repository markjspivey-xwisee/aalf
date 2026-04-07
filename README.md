# AALF — Autopoietic Artificial Life Forms

A subscription-driven simulation of self-producing, self-maintaining artificial life forms based on the theory of **autopoiesis**.

## What is Autopoiesis?

Autopoiesis (Greek: *auto* = self, *poiesis* = creation) is a theoretical framework originated by Maturana and Varela describing systems that continuously produce and maintain themselves. An autopoietic system:

1. Has a **semi-permeable boundary** (membrane) that distinguishes self from environment
2. Contains a **network of processes** that continuously regenerate all components
3. The boundary is **itself a product** of the internal network
4. Achieves **operational closure** — the system defines its own identity through circular self-production

## Architecture

```
aalf/
├── core/
│   ├── chemistry.py      # Molecular types, reactions, metabolism
│   ├── membrane.py        # Semi-permeable boundary model
│   ├── life_form.py       # Autopoietic life form entity
│   └── simulation.py      # Simulation engine & statistics
├── environment/
│   └── world.py           # 2D toroidal world with resource fields
├── subscriptions/
│   └── event_bus.py       # Publish/subscribe event system
├── visualization/
│   └── renderer.py        # Terminal Unicode renderer
└── __main__.py            # CLI entry point
```

### Subscription-Driven Design

The simulation is built around an **event bus** (publish/subscribe pattern) that mirrors the structural coupling of autopoietic systems:

- **Life forms emit events** as they metabolize, repair, divide, and die
- **Subscribers react** to events for visualization, statistics, and inter-organism signaling
- **Event types** span the full lifecycle: spawning, metabolism, membrane dynamics, division, death, and emergent phenomena
- **Filtered subscriptions** allow observers to watch specific organisms or event categories
- **Event replay** enables historical analysis of simulation runs

```python
from aalf.subscriptions import EventBus, EventType

bus = EventBus()

# Subscribe to division events
bus.subscribe(EventType.LIFE_FORM_DIVIDED, lambda e: print(f"Division! {e.data}"))

# Subscribe to all events with a filter
bus.subscribe(None, my_callback, filter_fn=lambda e: e.source_id == "abc123")

# Replay recent history
recent_deaths = bus.replay(event_types={EventType.LIFE_FORM_DIED}, limit=10)
```

## How It Works

### Chemistry
Each life form has an internal inventory of molecules and runs metabolic reactions:
- **Substrates A & B** are imported from the environment through the membrane
- **Energy production**: substrate_a → energy + waste
- **Lipid synthesis**: substrate_b + energy → membrane lipids
- **Enzyme synthesis**: substrates + energy + catalyst → enzymes (boost reaction rates)
- **Transporter synthesis**: substrate_b + energy → membrane channels
- **Waste export**: waste is expelled back to the environment

### Membrane (The Autopoietic Boundary)
- Composed of lipids and transporter molecules
- **Decays naturally** each tick — must be continuously rebuilt
- **Integrity** determines viability and transport capacity
- **Growth beyond full integrity** enables cell division
- If integrity drops below breach threshold → death

### Life Cycle
1. **Import** substrates from local environment
2. **Metabolize** — run chemical reactions to produce components
3. **Maintain membrane** — repair and grow the boundary
4. **Age** — basal energy cost increases over time
5. **Divide** — when energy, membrane, and enzyme thresholds are met
6. **Die** — when membrane breaches or energy depletes; materials return to environment

### Environment
- **2D toroidal grid** with continuous coordinates
- **Resource fields** for each substrate type with regeneration and diffusion
- **Hotspots** — randomly placed areas of high resource density
- **Chemotaxis** — life forms drift toward resource gradients

### Emergent Behaviors
- **Population dynamics** — carrying capacity emerges from resource competition
- **Generational evolution** — genomes mutate on division, conferring different strategies
- **Niche formation** — organisms cluster near resource hotspots
- **Aging and turnover** — old organisms gradually decline, making room for descendants

## Running

```bash
# Visual mode (terminal animation)
python -m aalf

# With custom parameters
python -m aalf --width 60 --height 30 --population 20 --ticks 1000

# Headless mode (text output)
python -m aalf --headless --ticks 500

# Stats only
python -m aalf --stats-only --ticks 1000 --seed 42

# Reproducible run
python -m aalf --seed 12345
```

### CLI Options

| Flag | Default | Description |
|------|---------|-------------|
| `--width` | 40 | World width |
| `--height` | 25 | World height |
| `--population` | 12 | Initial population |
| `--capacity` | 80 | Soft carrying capacity |
| `--ticks` | 2000 | Maximum simulation steps |
| `--delay` | 0.08 | Seconds between visual frames |
| `--seed` | random | Random seed for reproducibility |
| `--headless` | false | Run without visualization |
| `--stats-only` | false | Only print final statistics |

## Requirements

- Python 3.10+
- No external dependencies (stdlib only)

## Visual Legend

```
○  Healthy life form (green = thriving, yellow = stressed)
●  Elder (generation 5+)
◎  Established (generation 2-4)
◉  Ready to divide
○  Non-autopoietic (red — self-production loop broken)
░  Resource-rich area
·  Resource-poor area
```

## License

MIT
