import asyncio
import logging
from store import store
import os
from datetime import datetime

__version__: str = "v0.11.0"
__author__: str = "Henry West <hernaizhenry@gmail.com>"

logger = logging.getLogger(__name__)


def main() -> None:
    """
    Main entry point of the iot-bms-link driver
    """

    logger.info(f"Starting version {__version__}")

    with open("version.txt", "w+") as f:
        try:
            _ = f.write(
                f"Version {__version__} - started at {datetime.now().isoformat()}"
            )
        except Exception as e:
            logger.error(f"Cannot write version file: {e}")

    try:
        asyncio.run(store.mainloop())
    except KeyboardInterrupt:
        logger.info("You stopped the program (KeyboardInterrupt)")
        os._exit(1)
    except Exception as e:
        logger.critical(f"Unexpected exception: {e}", exc_info=True)
    finally:
        logger.info(f"Exiting application.")
        os._exit(1)


if __name__ == "__main__":
    main()
