"""Redis-based distributed locks for multi-worker safety.

Every browser-automation task must acquire both an account lock and a
profile lock before starting.  Locks are released automatically when the
context manager exits.

Usage::

    async with account_lock("acc_123") as held:
        if not held:
            return  # another worker is already running this account
        # safe to proceed

Redis key layout::

    nanobot:lock:account:{account_id}
    nanobot:lock:adspower:{profile_id}
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as aioredis

from app.config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_LOCK_TTL_SECONDS = 600  # 10 minutes — matches typical publish job
LOCK_PREFIX = "nanobot:lock"


def _worker_id() -> str:
    host = os.environ.get("HOSTNAME", os.environ.get("COMPUTERNAME", "unknown"))
    pid = os.getpid()
    raw = f"{host}:{pid}"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


async def _get_redis() -> aioredis.Redis:
    settings = get_settings()
    return aioredis.from_url(settings.redis_url, decode_responses=True)


# Lua script: delete *key* only if its value equals *owner*.
_RELEASE_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


@asynccontextmanager
async def account_lock(
    account_id: str,
    *,
    ttl: int = DEFAULT_LOCK_TTL_SECONDS,
) -> AsyncGenerator[bool, None]:
    key = f"{LOCK_PREFIX}:account:{account_id}"
    owner = _worker_id()
    redis = await _get_redis()
    acquired = False
    try:
        acquired = await redis.set(key, owner, nx=True, ex=ttl)
        if acquired:
            logger.debug("account lock acquired account=%s owner=%s", account_id, owner)
        else:
            current = await redis.get(key)
            logger.debug(
                "account lock skipped account=%s held_by=%s",
                account_id,
                current,
            )
        yield bool(acquired)
    finally:
        if acquired:
            await redis.eval(_RELEASE_SCRIPT, 1, key, owner)
            logger.debug("account lock released account=%s owner=%s", account_id, owner)
        await redis.aclose()


@asynccontextmanager
async def profile_lock(
    profile_id: str,
    *,
    ttl: int = DEFAULT_LOCK_TTL_SECONDS,
) -> AsyncGenerator[bool, None]:
    key = f"{LOCK_PREFIX}:adspower:{profile_id}"
    owner = _worker_id()
    redis = await _get_redis()
    acquired = False
    try:
        acquired = await redis.set(key, owner, nx=True, ex=ttl)
        if acquired:
            logger.debug("profile lock acquired profile=%s owner=%s", profile_id, owner)
        else:
            current = await redis.get(key)
            logger.debug(
                "profile lock skipped profile=%s held_by=%s",
                profile_id,
                current,
            )
        yield bool(acquired)
    finally:
        if acquired:
            await redis.eval(_RELEASE_SCRIPT, 1, key, owner)
            logger.debug("profile lock released profile=%s owner=%s", profile_id, owner)
        await redis.aclose()


# Lua script: for each key, if value matches owner, renew TTL.
_RENEW_SCRIPT = """
for i = 1, #KEYS do
    if redis.call("get", KEYS[i]) == ARGV[1] then
        redis.call("expire", KEYS[i], ARGV[2])
    end
end
return 1
"""


async def renew_locks(
    account_id: str,
    profile_id: str,
    *,
    ttl: int = DEFAULT_LOCK_TTL_SECONDS,
    interval: float = 60.0,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Background coroutine that renews lock TTLs every *interval* seconds.

    Callers should cancel this task once the protected operation finishes.
    """
    if stop_event is None:
        stop_event = asyncio.Event()
    redis = await _get_redis()
    owner = _worker_id()
    account_key = f"{LOCK_PREFIX}:account:{account_id}"
    profile_key = f"{LOCK_PREFIX}:adspower:{profile_id}"
    try:
        while not stop_event.is_set():
            await asyncio.sleep(interval)
            if stop_event.is_set():
                break
            await redis.eval(
                _RENEW_SCRIPT, 2, account_key, profile_key, owner, str(ttl)
            )
            logger.debug("locks renewed account=%s profile=%s", account_id, profile_id)
    finally:
        await redis.aclose()
