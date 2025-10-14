import asyncio
import logging
import core
from store import store
import database
from pprint import pprint

__version__: str = "v0.0.1"
__author__: str = "Henry Hernaiz <hernaizhenry@gmail.com>"

if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logger.info(f"Starting version {__version__}")

    asyncio.run(store.mainloop())
