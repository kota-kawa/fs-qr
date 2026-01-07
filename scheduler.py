import asyncio
import logging
import os
from functools import wraps
from urllib.parse import urlparse

import redis
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.schedulers.blocking import BlockingScheduler

import log_config
from database import db_session
from FSQR import fsqr_data
from Group import group_data
from Note import note_data
from settings import REDIS_URL

logger = logging.getLogger(__name__)

# Redis configuration for locking
r_lock = redis.from_url(REDIS_URL)


def exclusive_job(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        lock_name = f"scheduler:lock:{func.__name__}"
        # Lock expires in 1 hour
        lock = r_lock.lock(lock_name, timeout=3600, blocking=False)
        acquired = lock.acquire()
        if acquired:
            try:
                logger.info(f"Acquired lock for {func.__name__}, running job.")
                return func(*args, **kwargs)
            finally:
                try:
                    lock.release()
                except redis.LockError:
                    pass  # Lock might have expired or been released
        else:
            logger.info(f"Could not acquire lock for {func.__name__}, skipping execution.")
    return wrapper


async def _remove_expired_fsqr_async():
    try:
        await fsqr_data.remove_expired_files()
    finally:
        await db_session.remove()


@exclusive_job
def _remove_expired_fsqr():
    asyncio.run(_remove_expired_fsqr_async())


async def _remove_expired_group_rooms_async():
    try:
        await group_data.remove_expired_rooms()
    finally:
        await db_session.remove()


@exclusive_job
def _remove_expired_group_rooms():
    asyncio.run(_remove_expired_group_rooms_async())


async def _remove_expired_note_rooms_async():
    try:
        await note_data.remove_expired_rooms()
    finally:
        await db_session.remove()


@exclusive_job
def _remove_expired_note_rooms():
    asyncio.run(_remove_expired_note_rooms_async())


def run_scheduler():
    # Parse REDIS_URL for RedisJobStore
    url = urlparse(REDIS_URL)
    jobstores = {
        'default': RedisJobStore(
            host=url.hostname,
            port=url.port,
            db=int(url.path.strip('/')) if url.path else 0,
            password=url.password
        )
    }

    scheduler = BlockingScheduler(jobstores=jobstores)
    
    # Use replace_existing=True to update job definition if it exists
    scheduler.add_job(
        _remove_expired_fsqr, 
        trigger="interval", 
        days=1, 
        id="remove_expired_fsqr",
        replace_existing=True
    )
    scheduler.add_job(
        _remove_expired_group_rooms,
        trigger="interval",
        days=1,
        id="remove_expired_group_rooms",
        replace_existing=True
    )
    scheduler.add_job(
        _remove_expired_note_rooms,
        trigger="interval",
        days=1,
        id="remove_expired_note_rooms",
        replace_existing=True
    )

    logger.info("scheduler started with RedisJobStore and Exclusive Locking")
    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("scheduler stopped by keyboard interrupt")


if __name__ == "__main__":
    run_scheduler()