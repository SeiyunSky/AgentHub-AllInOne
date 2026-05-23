"""Shared test utilities (not fixtures)."""


async def collect_stream(gen) -> list:
    """Drain an async generator into a list of events."""
    events = []
    async for event in gen:
        events.append(event)
    return events
