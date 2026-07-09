"""Run the scheduler unattended: python -m beacon.scheduler.

Started by launchd on the home Mac (deploy/com.beacon.scheduler.plist). RunAtLoad +
KeepAlive means a reboot relaunches it and the next interval poll runs hands-off (SPEC §9).
"""

import asyncio
import logging

from beacon.config import Settings
from beacon.scheduler.schedule import build_scheduler

logger = logging.getLogger(__name__)


async def _run_forever() -> None:
    scheduler = build_scheduler(Settings.from_env())
    scheduler.start()
    logger.info("scheduler_started jobs=%d", len(scheduler.get_jobs()))
    await asyncio.Event().wait()  # block until the process is signalled


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    try:
        asyncio.run(_run_forever())
    except (KeyboardInterrupt, SystemExit):
        logger.info("scheduler_stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
