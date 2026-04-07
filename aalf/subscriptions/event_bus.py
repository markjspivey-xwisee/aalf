"""
Subscription-driven event bus for the autopoietic life simulation.

Implements a publish/subscribe pattern where simulation components emit events
and subscribers react to them — mirroring the structural coupling of autopoietic
systems with their environment.
"""

from __future__ import annotations

import enum
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


class EventType(enum.Enum):
    # Life form lifecycle
    LIFE_FORM_SPAWNED = "life_form.spawned"
    LIFE_FORM_DIED = "life_form.died"
    LIFE_FORM_DIVIDED = "life_form.divided"

    # Metabolism
    METABOLISM_TICK = "metabolism.tick"
    RESOURCE_CONSUMED = "resource.consumed"
    COMPONENT_PRODUCED = "component.produced"
    COMPONENT_DECAYED = "component.decayed"

    # Membrane
    MEMBRANE_REPAIRED = "membrane.repaired"
    MEMBRANE_DAMAGED = "membrane.damaged"
    MEMBRANE_BREACHED = "membrane.breached"

    # Environment
    RESOURCE_SPAWNED = "resource.spawned"
    RESOURCE_DEPLETED = "resource.depleted"
    ENVIRONMENT_TICK = "environment.tick"

    # Interaction
    COUPLING_FORMED = "coupling.formed"
    COUPLING_BROKEN = "coupling.broken"
    RESOURCE_EXCHANGED = "resource.exchanged"

    # Simulation
    SIMULATION_STARTED = "simulation.started"
    SIMULATION_PAUSED = "simulation.paused"
    SIMULATION_STEP = "simulation.step"
    SIMULATION_ENDED = "simulation.ended"

    # Emergent phenomena
    CLUSTER_FORMED = "cluster.formed"
    CLUSTER_DISSOLVED = "cluster.dissolved"
    AUTOPOIESIS_SUSTAINED = "autopoiesis.sustained"
    AUTOPOIESIS_LOST = "autopoiesis.lost"


@dataclass
class Event:
    """An immutable simulation event."""
    event_type: EventType
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    source_id: Optional[str] = None
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def __repr__(self) -> str:
        return f"Event({self.event_type.value}, src={self.source_id})"


@dataclass
class Subscription:
    """A subscription binding a callback to event types."""
    subscription_id: str
    event_types: set[EventType]
    callback: Callable[[Event], None]
    filter_fn: Optional[Callable[[Event], bool]] = None
    active: bool = True
    created_at: float = field(default_factory=time.time)

    def matches(self, event: Event) -> bool:
        if not self.active:
            return False
        if event.event_type not in self.event_types:
            return False
        if self.filter_fn and not self.filter_fn(event):
            return False
        return True


class EventBus:
    """
    Central event bus for the simulation.

    Supports:
    - Topic-based subscriptions (by EventType)
    - Filtered subscriptions (custom predicate)
    - Wildcard subscriptions (all events)
    - Event history / replay
    - Subscription lifecycle management
    """

    def __init__(self, history_limit: int = 10000):
        self._subscriptions: dict[EventType, list[Subscription]] = defaultdict(list)
        self._wildcard_subscriptions: list[Subscription] = []
        self._history: list[Event] = []
        self._history_limit = history_limit
        self._event_count = 0

    def subscribe(
        self,
        event_types: EventType | list[EventType] | None = None,
        callback: Callable[[Event], None] = lambda e: None,
        filter_fn: Optional[Callable[[Event], bool]] = None,
    ) -> Subscription:
        """Subscribe to one or more event types. Pass None for wildcard."""
        if event_types is None:
            types = set()
        elif isinstance(event_types, EventType):
            types = {event_types}
        else:
            types = set(event_types)

        sub = Subscription(
            subscription_id=uuid.uuid4().hex[:10],
            event_types=types,
            callback=callback,
            filter_fn=filter_fn,
        )

        if not types:
            self._wildcard_subscriptions.append(sub)
        else:
            for et in types:
                self._subscriptions[et].append(sub)
        return sub

    def unsubscribe(self, subscription: Subscription) -> None:
        subscription.active = False

    def publish(self, event: Event) -> int:
        """Publish an event, returns number of subscribers notified."""
        self._event_count += 1
        self._history.append(event)
        if len(self._history) > self._history_limit:
            self._history = self._history[-self._history_limit:]

        notified = 0
        # Topic subscribers
        for sub in self._subscriptions.get(event.event_type, []):
            if sub.matches(event):
                sub.callback(event)
                notified += 1
        # Wildcard subscribers
        for sub in self._wildcard_subscriptions:
            if sub.active and (sub.filter_fn is None or sub.filter_fn(event)):
                sub.callback(event)
                notified += 1
        return notified

    def emit(self, event_type: EventType, source_id: Optional[str] = None, **data) -> Event:
        """Convenience: create and publish an event in one call."""
        event = Event(event_type=event_type, data=data, source_id=source_id)
        self.publish(event)
        return event

    def replay(
        self,
        event_types: Optional[set[EventType]] = None,
        since: Optional[float] = None,
        limit: int = 100,
    ) -> list[Event]:
        """Replay historical events matching criteria."""
        results = []
        for e in reversed(self._history):
            if event_types and e.event_type not in event_types:
                continue
            if since and e.timestamp < since:
                break
            results.append(e)
            if len(results) >= limit:
                break
        return list(reversed(results))

    @property
    def event_count(self) -> int:
        return self._event_count

    @property
    def subscriber_count(self) -> int:
        seen = set()
        for subs in self._subscriptions.values():
            for s in subs:
                if s.active:
                    seen.add(s.subscription_id)
        for s in self._wildcard_subscriptions:
            if s.active:
                seen.add(s.subscription_id)
        return len(seen)
