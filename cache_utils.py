import json
import functools
import hashlib
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
import redis.asyncio as redis
from settings import REDIS_URL

logger = logging.getLogger(__name__)

# Initialize Redis client
redis_client = redis.from_url(REDIS_URL, decode_responses=True)


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, timedelta):
            return str(obj)
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def cache_data(ttl=60, key_prefix=""):
    """
    Decorator to cache the result of an async function in Redis.
    It handles SQLAlchemy RowMapping conversion to dict for serialization.
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                prefix = key_prefix or func.__name__
                cache_key = _build_cache_key(prefix, args, kwargs)

                # Try to get from cache
                cached_data = await redis_client.get(cache_key)
                if cached_data:
                    # logger.debug(f"Cache hit for {cache_key}")
                    return json.loads(cached_data)
            except Exception as e:
                logger.warning(f"Cache get error: {e}")

            # Execute function
            result = await func(*args, **kwargs)

            # Serialize and Cache the result
            try:
                to_cache = result
                # Handle SQLAlchemy RowMapping or list of them
                if result is not None:
                    if isinstance(result, list):
                        # List of rows
                        to_cache = [
                            dict(r) if hasattr(r, "keys") else r for r in result
                        ]
                    elif hasattr(result, "keys"):
                        # Single row
                        to_cache = dict(result)

                    await redis_client.setex(
                        cache_key, ttl, json.dumps(to_cache, cls=CustomJSONEncoder)
                    )
            except Exception as e:
                logger.warning(f"Cache set error: {e}")

            return result

        return wrapper

    return decorator


def _build_cache_key(key_prefix: str, args, kwargs) -> str:
    arg_data = [args, kwargs]
    arg_str = json.dumps(arg_data, sort_keys=True, default=str)
    key_hash = hashlib.md5(arg_str.encode()).hexdigest()
    return f"db_cache:{key_prefix}:{key_hash}"


async def invalidate_cache_entry(key_prefix: str, *args, **kwargs) -> None:
    cache_key = _build_cache_key(key_prefix, args, kwargs)
    try:
        await redis_client.delete(cache_key)
    except Exception as e:
        logger.warning(f"Cache delete error: {e}")


async def invalidate_cache_prefix(key_prefix: str) -> None:
    pattern = f"db_cache:{key_prefix}:*"
    try:
        keys = [key async for key in redis_client.scan_iter(match=pattern)]
        if keys:
            await redis_client.delete(*keys)
    except Exception as e:
        logger.warning(f"Cache prefix delete error: {e}")
