import asyncio
import logging

import log_config
from apscheduler.schedulers.blocking import BlockingScheduler

from database import db_session
from FSQR import fsqr_data
from Group import group_data
from Note import note_data

logger = logging.getLogger(__name__)


async def _remove_expired_fsqr_async():
    try:
        await fsqr_data.remove_expired_files()
    finally:
        await db_session.remove()


def _remove_expired_fsqr():
    asyncio.run(_remove_expired_fsqr_async())


async def _remove_expired_group_rooms_async():
    try:
        await group_data.remove_expired_rooms()
    finally:
        await db_session.remove()


def _remove_expired_group_rooms():
    asyncio.run(_remove_expired_group_rooms_async())


async def _remove_expired_note_rooms_async():
    try:
        await note_data.remove_expired_rooms()
    finally:
        await db_session.remove()


def _remove_expired_note_rooms():
    asyncio.run(_remove_expired_note_rooms_async())


def run_scheduler():
    scheduler = BlockingScheduler()
    scheduler.add_job(_remove_expired_fsqr, trigger="interval", days=1, id="remove_expired_fsqr")
    scheduler.add_job(
        _remove_expired_group_rooms,
        trigger="interval",
        days=1,
        id="remove_expired_group_rooms",
    )
    scheduler.add_job(
        _remove_expired_note_rooms,
        trigger="interval",
        days=1,
        id="remove_expired_note_rooms",
    )

    logger.info("scheduler started")
    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("scheduler stopped by keyboard interrupt")


if __name__ == "__main__":
    run_scheduler()
