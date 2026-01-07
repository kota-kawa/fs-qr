import logging

import log_config
from apscheduler.schedulers.blocking import BlockingScheduler

from FSQR import fsqr_data
from Group import group_data
from Note import note_data

logger = logging.getLogger(__name__)


def _remove_expired_fsqr():
    fsqr_data.remove_expired_files()


def _remove_expired_group_rooms():
    group_data.remove_expired_rooms()


def _remove_expired_note_rooms():
    note_data.remove_expired_rooms()


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
