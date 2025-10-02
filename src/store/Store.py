from dataclasses import dataclass, field
import core
import json
import bms
import azure_connection

with open(core.IP_SETTINGS, "r") as f:
    ip_settings = json.load(f)


@dataclass
class Store:
    store_id: str = ip_settings.get("store_id", "default_store_name")
    danfoss_panels: list[bms.DanfossBox] = field(default_factory=list)
    emerson2_panels: list = field(default_factory=list)
    emerson3_panels: list = field(default_factory=list)
    edge_device: azure_connection.IoTDevice = azure_connection.IoTDevice()

    def __post_init__(self):
        # Add danfoss panels
        danfoss = ip_settings.get("danfoss", {})
        if danfoss != {}:
            for panel in danfoss:
                panel_ip = panel.get("ip", "")
                panel_name = panel.get("name", "")
                if panel_ip != "":
                    self.danfoss_panels.append(bms.DanfossBox(panel_ip, panel_name))
