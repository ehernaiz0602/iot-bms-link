from dataclasses import dataclass, field
import core
import json
import bms
import azure_connection
import asyncio
import logging
import time

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

    danfoss_panels: list[bms.DanfossBox] = field(default_factory=list)
    emerson2_panels: list = field(default_factory=list)
    emerson3_panels: list = field(default_factory=list)
    edge_device: azure_connection.IoTDevice = azure_connection.IoTDevice()

    def __post_init__(self):
        # Add danfoss
        danfoss = ip_settings.get("danfoss", {})
        for panel in danfoss:
            panel_ip = panel.get("ip", "")
            panel_name = panel.get("name", "")
            if panel_ip:
                self.danfoss_panels.append(bms.DanfossBox(panel_ip, panel_name))

        # Add emerson e3
        emerson3 = ip_settings.get("emerson_e3", {})
        for panel in emerson3:
            panel_ip = panel.get("ip", "")
            panel_name = panel.get("name", "")
            if panel_ip:
                self.emerson3_panels.append(bms.E3Box(panel_ip, panel_name))

    async def mainloop(self):
        await self.edge_device.connect()
        while True:
            start_t = time.monotonic()
            logger.info(f"Starting next loop")
            try:
                await self.danfoss_tasks()
                await self.emerson_e3_tasks()
            except Exception as e:
                logger.error(f"Error: {e}")

            elapsed_t = time.monotonic() - start_t
            sleep_t = max(
                0, general_settings.get("publishIntervalSeconds", 30) - elapsed_t
            )

            logger.info(f"Finished loop in {elapsed_t} seconds")
            if sleep_t > 0:
                logger.debug(f"Sleeping for {sleep_t} seconds")
                await asyncio.sleep(sleep_t)

    async def danfoss_tasks(self):
        async def update_danfoss():
            init_tasks = []
            tasks = []

            for panel in self.danfoss_panels:
                if not panel.initialized:
                    init_tasks.append(panel.initialize())
                tasks.append(panel.update_all())

            if len(init_tasks) != 0:
                await asyncio.gather(*init_tasks)

            await asyncio.gather(*tasks)

        async def send_danfoss():
            data = []

            for panel in self.danfoss_panels:
                this_data = panel.get_data()
                for entry in this_data:
                    entry["ip"] = panel.ip
                data.extend(this_data)

            await self.edge_device.send_message(data)

        if len(self.danfoss_panels) != 0:
            await update_danfoss()
            await send_danfoss()

    async def emerson_e3_tasks(self):
        async def update_e3():
            for panel in self.emerson3_panels:
                await panel.update_all()

        async def send_e3():
            data = []

            for panel in self.emerson3_panels:
                this_data = panel.get_data()
                data.extend(this_data)

            await self.edge_device.send_message(data)

        if len(self.emerson3_panels) != 0:
            await update_e3()
            await send_e3()
