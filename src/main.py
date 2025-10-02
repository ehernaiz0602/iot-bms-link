import asyncio
import logging
import core
from store import Store
import database
from pprint import pprint

__version__: str = "v0.0.1"
__author__: str = "Henry Hernaiz <hernaizhenry@gmail.com>"

if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logger.info(f"Starting version {__version__}")

    store = Store("0215")
    pprint(store)

    asyncio.run(store.danfoss_panels[0].discover_hvacs())
    store.danfoss_panels[0].print_hierarchy()
    pprint(store.danfoss_panels[0].get_denormalized_data())

    # asyncio.run(
    #     store.edge_device.send_message(
    #         {
    #             "test_array": ["1", "2", "3"],
    #             "test_dict": {"field1": "1", "field2": "2"},
    #             "test_value": "myvalue",
    #         }
    #     )
    # )
