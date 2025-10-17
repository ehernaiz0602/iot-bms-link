import asyncio
import logging
import core
from store import store
import json
import bms

__version__: str = "v0.2.0"
__author__: str = "Henry Hernaiz <hernaizhenry@gmail.com>"

logger = logging.getLogger(__name__)


def main() -> None:
    """
    Main entry point of the iot-bms-link driver
    """

    logger.info(f"Starting version {__version__}")

    # If err files enabled, write txt file with version in it.
    with open(core.GENERAL_SETTINGS, "r") as f:
        general_settings = json.load(f)

    if general_settings.get("useErrFiles", False):
        with open("version.txt", "w+") as f:
            try:
                f.write(f"Version {__version__}")
            except Exception as e:
                logger.error(f"Cannot write version file: {e}")

    asyncio.run(store.mainloop())


if __name__ == "__main__":
    main()
