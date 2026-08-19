import asyncio
import logging

from . import consumer, outbox_relay

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


async def main() -> None:
    # Two independent long-running tasks in one process for Phase 3 --
    # simplest thing that demonstrates the pattern correctly. Nothing
    # here prevents running consumer.run() and outbox_relay.run() as
    # separate processes/deployments later if their scaling needs
    # diverge; that's an operational split, not a code one.
    await asyncio.gather(consumer.run(), outbox_relay.run())


if __name__ == "__main__":
    asyncio.run(main())
