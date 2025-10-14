import asyncio
import logging
import core
from store import store

__version__: str = "v0.0.1"
__author__: str = "Henry Hernaiz <hernaizhenry@gmail.com>"

logger = logging.getLogger(__name__)


def main() -> None:
    """
    Main entry point of the iot-bms-link driver
    """

    logger.info(f"Starting version {__version__}")
    asyncio.run(store.mainloop())


if __name__ == "__main__":
    main()
