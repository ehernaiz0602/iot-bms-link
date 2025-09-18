import asyncio
import logging
import core
import bms
import database
from pprint import pprint

__version__: str = "v0.0.1"
__author__: str = "Henry Hernaiz <hernaizhenry@gmail.com>"

if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logger.info(f"Starting version {__version__}")

    box = bms.DanfossBox("10.169.3.181")
    # asyncio.run(box.update_alarms())
    # box.print_hierarchy()
    # pprint(box.get_point(2, 7, 1, 19).meta)
