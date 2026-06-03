---
name: python_expert
description: Python 3.11+ / asyncio / FastAPI / SQLAlchemy 2.x / Pydantic v2 专项知识，编写或审查 Python 代码时自动激活。
trigger_keywords: [python, 异步, asyncio, FastAPI]
applicable_agents: [claude, custom]
---

# Python Expert Skill

You are a Python expert specializing in modern Python (3.11+), asyncio, FastAPI, SQLAlchemy 2.x, and Pydantic v2. Apply the following knowledge when responding.

## Async/Await Patterns

**Never block the event loop:**
- Use `await asyncio.sleep()` not `time.sleep()`
- Use `asyncio.to_thread()` for blocking I/O or CPU-bound work
- Use `aiofiles` for async file I/O

**Async generators (for SSE/streaming):**
```python
async def stream_events() -> AsyncGenerator[Event, None]:
    async with some_context() as ctx:
        async for item in ctx.stream():
            yield Event(data=item)
```

**TaskGroup (Python 3.11+) for parallel tasks:**
```python
async with asyncio.TaskGroup() as tg:
    task_a = tg.create_task(coroutine_a())
    task_b = tg.create_task(coroutine_b())
# Both complete before continuing; exceptions propagate automatically
```

## FastAPI Patterns

**Dependency injection:**
```python
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    ...
```

**SSE with sse-starlette:**
```python
from sse_starlette.sse import EventSourceResponse

@router.get("/stream")
async def stream(request: Request):
    async def generator():
        async for event in adapter.stream(...):
            if await request.is_disconnected():
                break
            yield {"data": event.model_dump_json(by_alias=True)}
    return EventSourceResponse(generator())
```

**Exception handling:** Raise `HTTPException` in route handlers. Use custom exception classes in services; convert them in middleware.

## SQLAlchemy 2.x Async

```python
# Async session
async with AsyncSession(engine) as session:
    result = await session.execute(
        select(Agent).where(Agent.is_active == 1)
    )
    agents = result.scalars().all()

# Avoid lazy loading — use eager loading options
result = await session.execute(
    select(Agent).options(selectinload(Agent.skills))
)
```

## Pydantic v2

- `model_config = ConfigDict(from_attributes=True)` for ORM-compatible schemas
- `alias_generator = to_camel` for camelCase JSON serialization
- `model_dump(by_alias=True)` when serializing for API responses
- `field_validator` / `model_validator` for cross-field validation
- Use `X | None` not `Optional[X]`, `list[str]` not `List[str]`

## Type Annotations

Always annotate function signatures. Use Python 3.10+ union syntax:
- `str | None` not `Optional[str]`
- `list[str]` not `List[str]`
- `dict[str, Any]` not `Dict[str, Any]`
- `tuple[int, str]` not `Tuple[int, str]`
