import asyncio
from functools import wraps

def async_timeout(seconds: float):
    """Decorator to add a timeout to an asyncio coroutine.
    Takes a float for how long to wait for the coroutine to finish."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async with asyncio.timeout(seconds):
                return await func(*args, **kwargs)
        return wrapper
    return decorator