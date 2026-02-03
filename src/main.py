import asyncio
import logging
from store import store
import os
from datetime import datetime
import json
import core
import time

__version__: str = "v0.15.0"
__author__: str = "Henry West <west.henrymiles@gmail.com>"

logger = logging.getLogger(__name__)

with open(core.GENERAL_SETTINGS, "r") as f:
    general_settings = json.load(f)

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
        with open("lock.json", "r") as f:
            contents = json.load(f)
            timeobj = datetime.fromisoformat(contents["timestamp"])
            current_time = datetime.now()
            time_diff = current_time - timeobj
            seconds_elapsed = time_diff.total_seconds()
            if seconds_elapsed < general_settings.get("lock_reset_seconds", 43_200):
                logger.critical(f"lock file exists with a young timestamp. shutting down the driver immediately.")
                time.sleep(1)
                os._exit(1)
    except FileNotFoundError:
        logger.warning(f"lock file does not exist. it is probably okay to continue...")
    except Exception as e:
        logger.error(f"Could not check lock file: {e}")


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
