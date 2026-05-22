import json
import functools
import hashlib
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Iterable, Optional

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


def cache_data(ttl=60, key_prefix="", strip_keys: Optional[Iterable[str]] = None):
    """
    Decorator to cache the result of an async function in Redis.
    It handles SQLAlchemy RowMapping conversion to dict for serialization.

    Cache keys are namespaced by ``module.qualname`` to avoid collisions
    between same-named functions across modules.

    ``strip_keys`` removes the specified keys from dict/row results before
    they are cached AND before they are returned, so sensitive columns
    (e.g. ``password``) never enter Redis or reach unintended callers.
    """

    strip_set = frozenset(strip_keys or ())

    def decorator(func):
        prefix = key_prefix or f"{func.__module__}.{func.__qualname__}"

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                cache_key = _build_cache_key(prefix, args, kwargs)

                cached_data = await redis_client.get(cache_key)
                if cached_data:
                    return json.loads(cached_data)
            except Exception as e:
                logger.warning(f"Cache get error: {e}")

            result = await func(*args, **kwargs)

            to_cache = _normalize_for_cache(result, strip_set)
            if to_cache is not None:
                try:
                    await redis_client.setex(
                        cache_key, ttl, json.dumps(to_cache, cls=CustomJSONEncoder)
                    )
                except Exception as e:
                    logger.warning(f"Cache set error: {e}")
                return to_cache

            return result

        wrapper._cache_prefix = prefix  # type: ignore[attr-defined]
        return wrapper

    return decorator


def _normalize_for_cache(result, strip_set: frozenset):
    if result is None:
        return None
    if isinstance(result, list):
        return [_strip_dict(_to_dict(r), strip_set) for r in result]
    if hasattr(result, "keys"):
        return _strip_dict(_to_dict(result), strip_set)
    return result


def _to_dict(row):
    if hasattr(row, "keys") and not isinstance(row, dict):
        return dict(row)
    return row


def _strip_dict(value, strip_set: frozenset):
    if not strip_set or not isinstance(value, dict):
        return value
    return {k: v for k, v in value.items() if k not in strip_set}


def _build_cache_key(key_prefix: str, args, kwargs) -> str:
    arg_data = [args, kwargs]
    arg_str = json.dumps(arg_data, sort_keys=True, default=str)
    key_hash = hashlib.md5(arg_str.encode()).hexdigest()  # noqa: S324
    return f"db_cache:{key_prefix}:{key_hash}"


def _resolve_prefix(func_or_prefix) -> str:
    """Accept either a cache_data-wrapped function or a raw prefix string."""
    if callable(func_or_prefix):
        prefix = getattr(func_or_prefix, "_cache_prefix", None)
        if prefix:
            return prefix
        return f"{func_or_prefix.__module__}.{func_or_prefix.__qualname__}"
    return str(func_or_prefix)


async def invalidate_cache_entry(key_prefix, *args, **kwargs) -> None:
    prefix = _resolve_prefix(key_prefix)
    cache_key = _build_cache_key(prefix, args, kwargs)
    try:
        await redis_client.delete(cache_key)
    except Exception as e:
        logger.warning(f"Cache delete error: {e}")


async def invalidate_cache_prefix(key_prefix) -> None:
    prefix = _resolve_prefix(key_prefix)
    pattern = f"db_cache:{prefix}:*"
    try:
        keys = [key async for key in redis_client.scan_iter(match=pattern)]
        if keys:
            await redis_client.delete(*keys)
    except Exception as e:
        logger.warning(f"Cache prefix delete error: {e}")
