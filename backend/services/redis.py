import redis.asyncio as redis
import os
from dotenv import load_dotenv
import asyncio
from utils.logger import logger
from typing import List, Any
from utils.retry import retry

# Redis client
client: redis.Redis | None = None
_initialized = False
_init_lock = asyncio.Lock()

# Constants
REDIS_KEY_TTL = 3600 * 24  # 24 hour TTL as safety mechanism


def initialize():
    """Initialize Redis connection using environment variables, adapted for Railway."""
    global client

    # No need for load_dotenv() on Railway, but it doesn't hurt
    load_dotenv()

    # --- Start of Changes ---

    # Get Redis URL from Railway's environment variables
    # On Railway, this variable is essential. If it's missing, we can't proceed.
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        raise ValueError("REDIS_URL environment variable is not set. Please check your Railway service variables.")

    logger.info(f"Initializing Redis connection using URL from environment")

    # Create Redis client directly from the URL provided by Railway.
    # The from_url() method automatically handles host, port, password, and SSL.
    client = redis.from_url(
        redis_url,
        # You can keep all your other custom settings here
        decode_responses=True,
        socket_timeout=5.0,
        socket_connect_timeout=5.0,
        retry_on_timeout=True,
        health_check_interval=30,
    )

    # --- End of Changes ---

    return client


async def initialize_async():
    """Initialize Redis connection asynchronously."""
    global client, _initialized

    async with _init_lock:
        if not _initialized:
            logger.info("Initializing Redis connection")
            initialize()

        try:
            await client.ping()
            logger.info("Successfully connected to Redis")
            _initialized = True
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            client = None
            _initialized = False
            raise

    return client


async def close():
    """Close Redis connection."""
    global client, _initialized
    if client:
        logger.info("Closing Redis connection")
        await client.aclose()
        client = None
    
    _initialized = False
    logger.info("Redis connection closed")


async def get_client():
    """Get the Redis client, initializing if necessary."""
    global client, _initialized
    if client is None or not _initialized:
        await retry(lambda: initialize_async())
    return client


# Basic Redis operations
async def set(key: str, value: str, ex: int = None, nx: bool = False):
    """Set a Redis key."""
    redis_client = await get_client()
    return await redis_client.set(key, value, ex=ex, nx=nx)


async def get(key: str, default: str = None):
    """Get a Redis key."""
    redis_client = await get_client()
    result = await redis_client.get(key)
    return result if result is not None else default


async def delete(key: str):
    """Delete a Redis key."""
    redis_client = await get_client()
    return await redis_client.delete(key)


async def publish(channel: str, message: str):
    """Publish a message to a Redis channel."""
    redis_client = await get_client()
    return await redis_client.publish(channel, message)


async def create_pubsub():
    """Create a Redis pubsub object."""
    redis_client = await get_client()
    return redis_client.pubsub()


# List operations
async def rpush(key: str, *values: Any):
    """Append one or more values to a list."""
    redis_client = await get_client()
    return await redis_client.rpush(key, *values)


async def lrange(key: str, start: int, end: int) -> List[str]:
    """Get a range of elements from a list."""
    redis_client = await get_client()
    return await redis_client.lrange(key, start, end)


# Key management


async def keys(pattern: str) -> List[str]:
    """Get keys matching a pattern."""
    redis_client = await get_client()
    return await redis_client.keys(pattern)
