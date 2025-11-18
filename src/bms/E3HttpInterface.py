import logging
import json
import core
import asyncio
from tenacity import (
    retry,
    stop_after_attempt,
    wait_fixed,
)
import aiohttp
from aiohttp_socks import ProxyConnector
import platform
from typing import Optional
import os

logger = logging.getLogger(__name__)

with open(core.GENERAL_SETTINGS, "r") as f:
    general_settings = json.load(f)


def verify_session(func):
    async def wrapper(self, *args, **kwargs):
        if self.session is None or not self.session_id:
            await self._init_session()

        if self.permissions is None:
            await self.login()

        data = await func(self, *args, **kwargs)

        if (
            data
            and data.get("error", {}).get("data", "")
            == "Session has been closed, please refresh"
        ):
            await self._close_session()
            await self._init_session()
            data = await func(self, *args, **kwargs)

        await asyncio.sleep(self.request_delay)
        return data

    return wrapper


class E3HttpInterface:
    def __init__(
        self,
        ip: str,
        name: str = "unit1",
        username: str = "system.default",
        password="",
    ):
        self.ip: str = ip
        self.endpoint: str = f"http://{ip}/cgi-bin/mgw.cgi"
        self.timeout = general_settings.get("http_timeout_delay", 3)
        self.retries = general_settings.get("http_retry_count", 3)
        self.request_delay = general_settings.get("http_request_delay", 3)
        self.id: int = 1
        self.session: Optional[aiohttp.ClientSession] = None
        self.session_id: Optional[str] = None
        self.username: str = username
        self.password: str = password
        self.failed_requests: int = 0
        self.http_headers = {
            "Accept": "*/*",
        }
        self.permissions: Optional[dict[str, bool]] = None

    async def _init_session(self):
        if self.session is None:
            connector = (
                ProxyConnector.from_url("socks5://localhost:1080")
                if platform.system() == "Linux"
                else None
            )

            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(connector=connector, timeout=timeout)

            resp = await self.get_session_id()
            self.session_id = (
                resp.get("result", {}).get("sid", "") if resp is not None else ""
            )

    async def _close_session(self):
        if self.session:
            await self.session.close()
            self.session = None
            self.permissions = None
            self.session_id = None
            self.id = 1

    def _build_payload(self, method: str, params: Optional[dict] = None) -> dict:
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "id": str(self.id),
        }

        if params:
            payload["params"] = params
        self.id = self.id + 1 if self.id < 1000 else 1
        return {"m": json.dumps(payload)}

    async def _send_get(
        self, method: str, params: Optional[dict] = None
    ) -> Optional[dict]:
        query = self._build_payload(method=method, params=params)
        logger.debug(f"Sending {query} to {self.ip}")

        @retry(
            wait=wait_fixed(self.request_delay),
            stop=stop_after_attempt(self.retries),
        )
        async def try_send():
            async with self.session.get(
                self.endpoint, params=query, headers=self.http_headers
            ) as s:
                try:
                    s.raise_for_status()
                    text = await s.text()
                    self.failed_requests = 0

                    if os.path.exists(core.PARENT_DIRECTORY / f"{self.ip}_BMS.err"):
                        logger.info(f"Removing {self.ip}_BMS.err")
                        try:
                            os.remove(core.PARENT_DIRECTORY / f"{self.ip}_BMS.err")
                        except Exception as e:
                            logger.error(f"Cannot delete {self.ip}_BMS.err file: {e}")

                    return json.loads(text)
                except json.JSONDecodeError:
                    logger.error(f"Failed to decode JSON from request")
                    return None
                except aiohttp.ClientResponseError as e:
                    logger.error(f"GET request at {self.ip} failed: {e}")
                    self.failed_requests += 1
                except Exception as e:
                    self.failed_requests += 1
                    logger.error(f"Unexpected error: {e}")

                if general_settings.get(
                    "use_err_files", False
                ) and self.failed_requests > general_settings.get(
                    f"fail_connection_number"
                ):
                    logger.warning(f"Writing {self.ip}_BMS.err")
                    path_obj = core.PARENT_DIRECTORY / f"{self.ip}_BMS.err"
                    try:
                        path_obj.touch()
                    except Exception as e:
                        logger.error(f"Cannot touch {self.ip}_BMS.err file: {e}")

                return None

        return await try_send()

    async def _send_post(
        self, method: str, params: Optional[dict] = None
    ) -> Optional[dict]:
        query = self._build_payload(method=method, params=params)
        logger.debug(f"Sending {query} to {self.ip}")

        @retry(
            wait=wait_fixed(self.request_delay),
            stop=stop_after_attempt(self.retries),
        )
        async def try_send():
            async with self.session.post(
                self.endpoint, params=query, headers=self.http_headers
            ) as s:
                try:
                    s.raise_for_status()
                    text = await s.text()

                    if os.path.exists(core.PARENT_DIRECTORY / f"{self.ip}_BMS.err"):
                        logger.info(f"Removing {self.ip}_BMS.err")
                        try:
                            os.remove(core.PARENT_DIRECTORY / f"{self.ip}_BMS.err")
                        except Exception as e:
                            logger.error(f"Cannot delete {self.ip}_BMS.err file: {e}")

                    return json.loads(text)
                except json.JSONDecodeError:
                    logger.error(f"Failed to decode JSON from request")
                    self.failed_requests = 0
                    return None
                except aiohttp.ClientResponseError as e:
                    self.failed_requests += 1
                    logger.error(f"GET request at {self.ip} failed: {e}")
                except Exception as e:
                    self.failed_requests += 1
                    logger.error(f"Unexpected error: {e}")

                if general_settings.get(
                    "use_err_files", False
                ) and self.failed_requests > general_settings.get(
                    f"fail_connection_number"
                ):
                    logger.warning(f"Writing {self.ip}_BMS.err")
                    path_obj = core.PARENT_DIRECTORY / f"{self.ip}_BMS.err"
                    try:
                        path_obj.touch()
                    except Exception as e:
                        logger.error(f"Cannot touch {self.ip}_BMS.err file: {e}")

                return None

        return await try_send()

    async def get_session_id(self):
        return await self._send_get("GetSessionID")

    async def login(self):
        if not self.session:
            await self._init_session()

        resp = await self._send_post(
            "Login",
            {"key": self.username, "value": self.password, "sid": self.session_id},
        )

        if resp:
            self.permissions = {
                k: bool(v)
                for k, v in resp.get("result", {}).get("permissions", {}).items()
            }

        return resp

    @verify_session
    async def get_network_summary(self):
        return await self._send_post("GetNetworkSummary", {"sid": self.session_id})

    @verify_session
    async def get_licenses(self):
        return await self._send_post("GetLicenses", {"sid": self.session_id})

    @verify_session
    async def get_app_types(self):
        return await self._send_post("GetAppTypes", {"sid": self.session_id})

    @verify_session
    async def get_setup_wizard_status(self):
        return await self._send_post("GetSetupWizardStatus", {"sid": self.session_id})

    @verify_session
    async def get_system_inventory(self):
        return await self._send_post("GetSystemInventory", {"sid": self.session_id})

    @verify_session
    async def get_alarms(self):
        return await self._send_post("GetAlarms", {"sid": self.session_id})

    @verify_session
    async def get_groups(self):
        return await self._send_post(
            "GetGroups", {"user": self.username, "sid": self.session_id}
        )

    @verify_session
    async def get_app_description(self, iid: str):
        return await self._send_post(
            "GetAppDescription", {"iid": iid, "sid": self.session_id}
        )

    @verify_session
    async def get_system_information(self):
        return await self._send_post("GetSystemInformation", {"sid": self.session_id})

    @verify_session
    async def get_app_commands(self, iid: str):
        return await self._send_post(
            "GetAppCommands", {"iid": iid, "sid": self.session_id}
        )

    @verify_session
    async def get_default_log_group(self):
        return await self._send_post("GetDefaultLogGroup", {"sid": self.session_id})

    @verify_session
    async def get_point_values(self, points: list[dict[str, str]]):
        return await self._send_post(
            "GetPointValues", {"points": points, "sid": self.session_id}
        )

    @verify_session
    async def get_dashboard_summary_props(self, apptype: str):
        return await self._send_post(
            "GetDashboardSummaryProps", {"apptype": apptype, "sid": self.session_id}
        )

    @verify_session
    async def get_apps_for_log_group(self, lgiid: str):
        return await self._send_post(
            "GetAppsForLogGroup", {"lgiid": lgiid, "sid": self.session_id}
        )

    @verify_session
    async def get_points_for_log_group(self, lgiid: str):
        return await self._send_post(
            "GetPointsForLogGroup", {"lgiid": lgiid, "sid": self.session_id}
        )
