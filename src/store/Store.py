from dataclasses import dataclass, field
import core
import json
import bms
import azure_connection
import asyncio
import logging
import time
import database

with open(core.IP_SETTINGS, "r") as f:
    ip_settings = json.load(f)

with open(core.GENERAL_SETTINGS, "r") as f:
    general_settings = json.load(f)

logger = logging.getLogger(__name__)


@dataclass
class Store:
    """
    Representation of the store program. Handles panels and IoT communication.
    """

    danfoss_panels: list = field(default_factory=list)
    emerson3_panels: list = field(default_factory=list)
    edge_device: "azure_connection.IoTDevice" = field(
        default_factory=lambda: azure_connection.IoTDevice()
    )
    db_interface: "database.DBInterface" = field(
        default_factory=lambda: database.DBInterface()
    )

    full_restart_interval: float = 12 * 60 * 60  # 12 hours
    cov_poll_interval: float = general_settings.get(
        "publishInvervalSeconds", 30
    )  # minimum seconds between publishes

    last_full_restart: float = field(default=0.0)

    def add_danfoss(self):
        self.danfoss_panels = []
        danfoss_config = ip_settings.get("danfoss", [])
        if len(danfoss_config) > 0:
            for panel in danfoss_config:
                panel_ip = panel.get("ip", "")
                panel_name = panel.get("name", "")
                if panel_ip:
                    self.danfoss_panels.append(bms.DanfossBox(panel_ip, panel_name))

    def add_emerson3(self):
        self.emerson3_panels = []
        emerson_config = ip_settings.get("emerson_e3", [])
        if len(emerson_config) > 0:
            for panel in emerson_config:
                panel_ip = panel.get("ip", "")
                panel_name = panel.get("name", "")
                if panel_ip:
                    self.emerson3_panels.append(bms.E3Box(panel_ip, panel_name))

    def add_emerson2(self):
        self.emerson2_panels = []
        emerson_config = ip_settings.get("emerson_e2", [])
        if len(emerson_config) > 0:
            for panel in emerson_config:
                panel_ip = panel.get("ip", "")
                panel_name = panel.get("name", "")
                if panel_ip:
                    self.emerson2_panels.append(bms.E2Box(panel_ip, panel_name))

    async def mainloop(self):
        """Main execution loop: full restart every 12 hours, CoV updates otherwise."""
        await self.edge_device.connect()
        await self.db_interface.initialize()

        # Initial panel setup
        self.add_danfoss()
        self.add_emerson3()
        self.add_emerson2()
        self.last_full_restart = time.monotonic()

        while True:
            now = time.monotonic()
            try:
                # Check if it's time for a full restart
                if now - self.last_full_restart >= self.full_restart_interval:
                    logger.info(
                        "Performing full restart: clearing DB and sending full frames"
                    )
                    await self.full_restart()
                    self.last_full_restart = time.monotonic()
                else:
                    await self.send_cov_frames()

            except Exception as e:
                logger.error(f"Error in main loop: {e}")

            elapsed_time = time.monotonic() - now
            # Sleep until next CoV poll
            sleep_time = self.cov_poll_interval - elapsed_time
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

    async def full_restart(self):
        """Perform a full restart: clear DB, refresh panels, send all data."""
        await self.db_interface.clear_table("data_table")
        self.add_danfoss()
        self.add_emerson3()
        self.add_emerson2()

        try:
            await self.gather_and_send_danfoss(full_frame=True)
        except:
            logger.debug(f"No danfoss")
        try:
            await self.gather_and_send_emerson3(full_frame=True)
        except:
            logger.debug(f"No emerson 3")
        try:
            self.gather_and_send_emerson2(full_frame=True)
        except:
            logger.debug(f"No emerson 2")

    async def send_cov_frames(self):
        """Send only CoV (change-of-value) data."""
        try:
            await self.gather_and_send_danfoss(full_frame=False)
        except:
            logger.debug(f"No danfoss")
        try:
            await self.gather_and_send_emerson3(full_frame=False)
        except:
            logger.debug(f"No emerson3")
        try:
            self.gather_and_send_emerson2(full_frame=False)
        except:
            logger.debug(f"No emerson 2")

    def gather_and_send_emerson2(self, full_frame=False):
        # Temporary test to try test stability of emerson e2
        # TODO: MAKE E2 ASYNC!!! Probably not necessary immediately because 1 panel sees all others
        logger.debug(f"TESTING EMERSON 2 FUNCTIONALITY")
        for panel in self.emerson2_panels:
            panel.get_controllers()

    async def gather_and_send_danfoss(self, full_frame=False):
        """Gather and send data from Danfoss panels."""
        init_tasks = [
            panel.initialize() for panel in self.danfoss_panels if not panel.initialized
        ]
        if init_tasks:
            await asyncio.gather(*init_tasks)

        update_tasks = [panel.update_all() for panel in self.danfoss_panels]
        if update_tasks:
            await asyncio.gather(*update_tasks)

        # Collect data from panels
        data = []
        for panel in self.danfoss_panels:
            data.extend(panel.get_data())

        # Fetch CoV data or full data
        iot_data = await self.db_interface.fetch_cov_data(data, full_frame=full_frame)
        await self.edge_device.send_message(iot_data)

    async def gather_and_send_emerson3(self, full_frame=False):
        """Gather and send data from Emerson3 panels."""
        update_tasks = [panel.update_all() for panel in self.emerson3_panels]
        if update_tasks:
            await asyncio.gather(*update_tasks)

        data = []
        for panel in self.emerson3_panels:
            data.extend(panel.get_data())

        iot_data = await self.db_interface.fetch_cov_data(data, full_frame=full_frame)
        await self.edge_device.send_message(iot_data)
