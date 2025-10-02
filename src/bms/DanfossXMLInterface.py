import xml.etree.ElementTree as ET
import xmltodict as xtd
import core
import json
from typing import Any
from tenacity import (
    retry,
    stop_after_attempt,
    wait_fixed,
    retry_if_exception_type,
)
import asyncio
import aiohttp
from aiohttp_socks import ProxyConnector
import platform
import logging

logger = logging.getLogger(__name__)

with open(core.GENERAL_SETTINGS, "r") as f:
    general_settings = json.load(f)


def process_command(func):
    async def wrapper(self, *args, **kwargs):
        sleep = general_settings.get("httpRequestDelay", 3)
        element: ET.Element = func(self, *args, **kwargs)
        action: str = element.attrib.get("action", "unknown")
        element_string: str = ET.tostring(element, encoding="unicode")

        logger.debug(f"Sending action {action} to {self.endpoint}")

        connector = (
            ProxyConnector.from_url("socks5://localhost:1080")
            if platform.system() == "Linux"
            else None
        )
        timeout = aiohttp.ClientTimeout(total=self.timeout)

        @retry(
            stop=stop_after_attempt(self.retries),
            wait=wait_fixed(sleep),
            retry=retry_if_exception_type(aiohttp.ClientError),
        )
        async def send_request(connector, timeout):

            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(
                    url=self.endpoint,
                    data=element_string,
                    headers=self.http_headers,
                    timeout=timeout,
                ) as response:
                    response.raise_for_status()
                    return await response.text()

        try:
            response_text = await send_request(connector, timeout)
            logger.debug(f"Response received from {self.endpoint}")
        except Exception as e:
            logger.warning(f"Final failure after {self.retries} retries: {e}")
            await asyncio.sleep(sleep)
            return {
                "@action": action,
                "@error": "Connection Error",
            }

        try:
            await asyncio.sleep(sleep)
            return xtd.parse(response_text)["resp"]
        except Exception as e:
            logger.error(f"Parsing error: {e}")
            return {
                "@action": action,
                "@error": "Software parsing error",
            }

    return wrapper


class DanfossXMLInterface:
    def __init__(
        self,
        ip: str,
        timeout: int = 3,
        retries: int = 3,
    ):
        self.ip = ip
        self.endpoint = f"http://{ip}/http/xml.cgi"
        self.timeout = general_settings.get("httpTimeoutDelay", 3)
        self.retries = general_settings.get("httpRetryCount", 3)

        self.http_headers = {
            "Connection": "close",
            "Content-Type": "application/xml",
        }

        self.required_params: dict[str, str] = {
            "lang": "e",
            "units": "U",
        }

    @process_command
    def read_dummy(self) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_dummy",
        )

    @process_command
    def read_units(self) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_units",
        )

    @process_command
    def read_devices(self) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_devices",
        )

    @process_command
    def read_date_time(self) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_date_time",
        )

    @process_command
    def read_meters(self) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_meters",
        )

    @process_command
    def read_parm_versions(self) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_parm_versions",
        )

    @process_command
    def read_dyn_list_info(self, device_id: str) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_dyn_list_info",
            device_id=device_id,
        )

    @process_command
    def read_menu_groups(self, device_id: str) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_menu_groups",
            device_id=device_id,
        )

    @process_command
    def read_device_summary(self, node: int) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_device_summary",
            node=str(node),
        )

    @process_command
    def read_parm_info(self, device_id: str) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_parm_info",
            device_id=device_id,
        )

    @process_command
    def schedule_detail(self, id: int) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="schedule_detail",
            id=str(id),
        )

    @process_command
    def schedule_summary(self) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="schedule_summary",
        )

    @process_command
    def read_store_schedule(self) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_store_schedule",
        )

    @process_command
    def read_hvac_service(self, ahindex: int) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_hvac_service",
            ahindex=str(ahindex),
        )

    @process_command
    def read_hvacs(self) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_hvacs",
        )

    @process_command
    def read_hvac(self) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_hvac",
        )

    @process_command
    def read_hvac_unit(self, ahindex: int) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_hvac_unit",
            ahindex=str(ahindex),
        )

    @process_command
    def read_lighting(self) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_lighting",
        )

    @process_command
    def read_lighting_zone(self, index: int) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_lighting_zone",
            index=str(index),
        )

    @process_command
    def read_holidays(self) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_holidays",
        )

    @process_command
    def read_suction_group(self, rack_id: int, suction_id: int) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_suction_group",
            rack_id=str(rack_id),
            suction_id=str(suction_id),
        )

    @process_command
    def read_circuit(
        self, rack_id: int, suction_id: int, circuit_id: int
    ) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_circuit",
            rack_id=str(rack_id),
            suction_id=str(suction_id),
            circuit_id=str(circuit_id),
        )

    @process_command
    def read_condenser(self, rack_id: int) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_condenser",
            rack_id=str(rack_id),
        )

    @process_command
    def read_inputs(self) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_inputs",
        )

    @process_command
    def read_relays(self) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_relays",
        )

    @process_command
    def read_alarm_relays(self) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_alarm_relays",
        )

    @process_command
    def read_sensors(self) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_sensors",
        )

    @process_command
    def read_var_outs(self) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_var_outs",
        )

    @process_command
    def read_input(self, addresses: list[dict[str, int]]) -> ET.Element:
        root = ET.Element(
            "cmd",
            self.required_params,
            action="read_input",
            valid_only="1",
            num_only="1",
        )

        for address in addresses:
            _ = ET.SubElement(
                root,
                "input",
                {k: str(v) for k, v in address.items()},
            )

        return root

    @process_command
    def read_relay(self, addresses: list[dict[str, int]]) -> ET.Element:
        root = ET.Element(
            "cmd",
            self.required_params,
            action="read_relay",
            valid_only="1",
            num_only="1",
        )

        for address in addresses:
            _ = ET.SubElement(
                root,
                "relay",
                {k: str(v) for k, v in address.items()},
            )

        return root

    @process_command
    def read_sensor(self, addresses: list[dict[str, int]]) -> ET.Element:
        root = ET.Element(
            "cmd",
            self.required_params,
            action="read_sensor",
            valid_only="1",
        )

        for address in addresses:
            _ = ET.SubElement(
                root,
                "sensor",
                {k: str(v) for k, v in address.items()},
            )

        return root

    @process_command
    def read_var_out(self, addresses: list[dict[str, int]]) -> ET.Element:
        root = ET.Element(
            "cmd",
            self.required_params,
            action="read_var_out",
            valid_only="1",
        )

        for address in addresses:
            _ = ET.SubElement(
                root,
                "var_output",
                {k: str(v) for k, v in address.items()},
            )

        return root

    @process_command
    def read_monitor_summary(self) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_monitor_summary",
        )

    @process_command
    def read_monitor_detail(self, addresses: list[dict[str, int]]) -> ET.Element:
        root = ET.Element(
            "cmd",
            self.required_params,
            action="read_monitor_detail",
        )

        for address in addresses:
            _ = ET.SubElement(
                root,
                "monitor",
                {k: str(v) for k, v in address.items()},
                valid_only="1",
            )

        return root

    @process_command
    def read_system_status(self) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_system_status",
        )

    @process_command
    def read_license_data(self) -> ET.Element:
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_license_data",
        )

    @process_command
    def alarm_summary(self):
        return ET.Element(
            "cmd",
            self.required_params,
            action="alarm_summary",
            day="0",
            date_format="2",
            time_format="1",
        )

    @process_command
    def alarm_detail(self, current: int | str):
        return ET.Element(
            "cmd",
            self.required_params,
            action="alarm_detail",
            only="any",
            current=str(current),
            expanded="2",
            date_format="2",
            time_format="1",
        )

    @process_command
    def read_cs_device_value(self, device_num: int | str, zone_num: int | str):
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_cs_device_value",
            nodetype="255",
            arg1=str(device_num),  # Leak device selector arg
            arg2=str(zone_num),  # Zone selector arg
            arg3="undefined",
            combo="13",
            bpidx="45",
            stype="13",
        )

    @process_command
    def read_points_si(self):
        return ET.Element(
            "cmd",
            self.required_params,
            action="read_points_si",
        )
