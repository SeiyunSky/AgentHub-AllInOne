"""Shared test utilities (not fixtures).

队伍：咕嘎一辈子队
修改者：Musuyin
修改日期：2026-05-23
"""


async def collect_stream(gen) -> list:
    """Drain an async generator into a list of events."""
    events = []
    async for event in gen:
        events.append(event)
    return events
