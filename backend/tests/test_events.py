"""Phase 4 — event bus conformance."""
import asyncio

from app.core.events import EventBus, Event, event_bus, CUSTOMER_CREATED


def test_event_roundtrip_fires_handler():
    bus = EventBus()
    received = []

    async def handler(e: Event):
        received.append(e)

    bus.subscribe(CUSTOMER_CREATED, handler)

    async def run():
        await bus.publish(Event(type=CUSTOMER_CREATED, business_id="b1",
                               payload={"x": 1}))

    asyncio.get_event_loop().run_until_complete(run())
    assert len(received) == 1
    assert received[0].type == CUSTOMER_CREATED
    assert received[0].payload == {"x": 1}
    assert received[0].event_id
    assert received[0].business_id == "b1"


def test_wildcard_receives_all():
    bus = EventBus()
    seen = []

    async def handler(e: Event):
        seen.append(e.type)

    bus.subscribe("*", handler)

    async def run():
        await bus.publish(Event(type="a.b", business_id="b"))
        await bus.publish(Event(type="c.d", business_id="b"))

    asyncio.get_event_loop().run_until_complete(run())
    assert seen == ["a.b", "c.d"]


def test_handler_failure_does_not_raise():
    bus = EventBus()
    calls = []

    async def bad(e: Event):
        calls.append(1)
        raise RuntimeError("boom")

    async def good(e: Event):
        calls.append(2)

    bus.subscribe("x.y", bad)
    bus.subscribe("x.y", good)

    async def run():
        await bus.publish(Event(type="x.y", business_id="b"))

    # publish must not propagate the handler error
    asyncio.get_event_loop().run_until_complete(run())
    assert calls == [1, 2]
