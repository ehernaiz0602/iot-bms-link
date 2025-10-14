from dataclasses import dataclass, field
import core
import json
import bms
import azure_connection
import asyncio
import logging

with open(core.IP_SETTINGS, "r") as f:
    ip_settings = json.load(f)

with open(core.GENERAL_SETTINGS, "r") as f:
    general_settings = json.load(f)

logger = logging.getLogger(__name__)


@dataclass
class Store:
    """
    A representation of the store the program is running in.
    Contains all panels as per the configuration file in Settings-IP.json

    methods:
        mainloop(): start the main execution of the program
    """

    store_id: str = ip_settings.get("store_id", "default_store_name")
    danfoss_panels: list[bms.DanfossBox] = field(default_factory=list)
    emerson2_panels: list = field(default_factory=list)
    emerson3_panels: list = field(default_factory=list)
    edge_device: azure_connection.IoTDevice = azure_connection.IoTDevice()

    def __post_init__(self):
        danfoss = ip_settings.get("danfoss", {})
        for panel in danfoss:
            panel_ip = panel.get("ip", "")
            panel_name = panel.get("name", "")
            if panel_ip:
                self.danfoss_panels.append(bms.DanfossBox(panel_ip, panel_name))

    async def upload_danfoss_forever(self, danfoss_dev):
        await asyncio.sleep(30)  # Initial delay
        while True:
            logger.info(f"Gather Danfoss data to send to IoTHub")
            data = danfoss_dev.get_data()
            await self.edge_device.send_message(data, danfoss_dev.ip)
            logger.info(
                f"Data sent to IoTHub. Waiting {general_settings.get('publishIntervalSeconds', 30)} seconds until next publish"
            )
            await asyncio.sleep(general_settings.get("publishIntervalSeconds", 30))

    async def mainloop(self):
        await self.edge_device.connect()
        tasks = []

        # Add danfoss polling tasks
        for danfoss in self.danfoss_panels:
            tasks.append(danfoss.poll_forever())
            tasks.append(self.upload_danfoss_forever(danfoss))

        # TODO: Add emerson2 polling tasks

        # TODO: Add emerson3 polling tasks

        await asyncio.gather(*tasks)
