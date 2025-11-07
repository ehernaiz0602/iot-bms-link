from dataclasses import dataclass
import platform
import core
import asyncio
from azure.iot.device import ProvisioningDeviceClient
from azure.iot.device.aio import IoTHubDeviceClient
from azure.iot.device import Message
from azure.identity import CertificateCredential
from azure.keyvault.secrets import SecretClient
import base64
import hashlib
import hmac
import logging
import json
from collections.abc import Mapping, Sequence
import subprocess
import sys
from pathlib import Path
import functools
import inspect
import os
import time

logger = logging.getLogger(__name__)

with open(core.AZURE_SETTINGS, "r") as f:
    azure_settings = json.load(f)

with open(core.GENERAL_SETTINGS, "r") as f:
    general_settings = json.load(f)

if platform.system() == "Linux":
    certificate = core.PARENT_DIRECTORY / "development_keys" / "CertificateTest.pfx"
else:
    if getattr(sys, "frozen", False):
        script_dir = Path(sys._MEIPASS) / "export_pfx.ps1"
    else:
        script_dir = Path(__file__).parent / "export_pfx.ps1"

    try:
        subprocess.run(
            [
                "powershell",
                str(script_dir),
                "-Subject",
                f"*{azure_settings.get('certificate_subject')}*",
                "-OutputPath",
                str(core.CERTIFICATE),
            ],
            check=True,
        )
        certificate = core.CERTIFICATE
        if not certificate.exists():
            logger.error(f"Couldn't export certificate file.")
            logger.critical(f"HARD STOP: Shutting down")
            os._exit(1)
    except Exception as e:
        logger.error(f"Could not load the certificate file: {e}")
        logger.critical(f"HARD STOP: Shutting down")
        os._exit(1)


def check_valid_device(func):
    """
    Decorator to check whether the IoTDevice is properly defined.
    Works with both async and sync methods.
    """
    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(self, *args, **kwargs):
            if not self.valid_device:
                logger.error("The IoTDevice definition is not valid.")
                os._exit(1)
                # return self.valid_device
            return await func(self, *args, **kwargs)

        return async_wrapper
    else:

        @functools.wraps(func)
        def sync_wrapper(self, *args, **kwargs):
            if not self.valid_device:
                logger.error("The IoTDevice definition is not valid.")
                os._exit(1)
                # return self.valid_device
            return func(self, *args, **kwargs)

        return sync_wrapper


@dataclass
class IoTWatchdog:
    time_down: float = time.monotonic()
    has_been_offline: bool = False
    number_retries: int = 0
    state: int = 1

    """
    state 1: connection failed
    state 2: connection success
    state 3: final state - shutting down
    """

    def transition_function(self, success_state: bool):
        now = time.monotonic()

        match self.state:
            case 1:
                if (
                    (self.number_retries > 10)
                    and (not self.has_been_offline)
                    and (not success_state)
                ):
                    self.state = 3
                    logger.debug("IOT transition to STOP")
                elif (
                    (self.number_retries > 10)
                    and (self.has_been_offline)
                    and (now - self.time_down > 1800)
                    and (not success_state)
                ):
                    self.state = 3
                    logger.debug("IOT transition to STOP")
                elif success_state:
                    self.number_retries = 0
                    self.time_down = now
                    self.has_been_offline = True
                    self.state = 2
                    logger.debug("IOT transition to CONNECTED")
                else:
                    self.number_retries += 1
                    logger.debug("IOT transition to DISCONNECTED")
            case 2:
                if not success_state:
                    self.number_retries += 1
                    self.state = 1
                    logger.debug("IOT transition to DISCONNECTED")
                else:
                    self.time_down = now
                    self.number_retries = 0
                    logger.debug("IOT transition to CONNECTED")

        if self.state == 3:
            logger.critical("Unrecoverable state for IoTHub connection, shutting down")
            os._exit(1)


class IoTDevice:
    """
    The edge device class. Responsible for provisioning and connecting to IoTHub
    As well as denormalizing and sending data to IoTHub from the bms

    Methods:
        connect(): connect the device to IoTHub
        send_message(data: list[dict]): send a semi-denormalized series of messages
    """

    def __init__(self) -> None:
        logger.info(f"Creating IoTDevice instance")
        self.hostname: str = ""
        self.device_key: str = ""
        self.connected: bool = False
        self.valid_device: bool = False
        self.device_client: IoTHubDeviceClient | None = None
        self.watchdog = IoTWatchdog()
        try:
            self.device_id: str = azure_settings.get("store_id")
            self.scope_id: str = azure_settings.get("scope_id")
            self.secret_name: str = azure_settings.get("secret_name")
            keyvault_url: str = (
                f"https://{azure_settings.get('vault_name')}.vault.azure.net/"
            )
            self.credential: CertificateCredential = CertificateCredential(
                azure_settings.get("tenant_id"),
                azure_settings.get("client_id"),
                certificate,
            )
            self.secret_client: SecretClient = SecretClient(
                vault_url=keyvault_url, credential=self.credential
            )
            self.valid_device = True
        except Exception as e:
            logger.warning(
                f"Could not initialize edge device. Check azure settings file: {e}"
            )
        self.sas_ttl: int = azure_settings.get("sas_ttl", 0) * 24 * 60 * 60

    @check_valid_device
    async def provision_device(self):
        try:
            logger.debug(f"Trying to provision device")
            group_key = self.secret_client.get_secret(self.secret_name).value
            logger.debug(f"the dps enrollment key is: {group_key}")

            keybytes = base64.b64decode(group_key)
            hmac_sha256 = hmac.new(keybytes, self.device_id.encode(), hashlib.sha256)
            self.device_key = base64.b64encode(hmac_sha256.digest()).decode()

            provisioning_device_client = (
                ProvisioningDeviceClient.create_from_symmetric_key(
                    provisioning_host="global.azure-devices-provisioning.net",
                    registration_id=self.device_id,
                    id_scope=self.scope_id,
                    symmetric_key=self.device_key,
                )
            )

            registration_result = provisioning_device_client.register()
            self.hostname = registration_result.registration_state.assigned_hub
            self.device_id = registration_result.registration_state.device_id
            logger.info(f"Provisioned device {self.device_id}")
        except Exception as e:
            logger.warning(f"Could not provision device: {e}")

    @check_valid_device
    async def connect(self):
        try:
            if self.hostname == "":
                try:
                    await self.provision_device()
                except:
                    self.watchdog.transition_function(False)
                    raise

            self.device_client = IoTHubDeviceClient.create_from_symmetric_key(
                symmetric_key=self.device_key,
                hostname=self.hostname,
                device_id=self.device_id,
                sastoken_ttl=self.sas_ttl,
            )
            await self.device_client.connect()
            logger.info(
                f"Device {self.device_id} is ready to receive messages in IoTHub"
            )
            self.connected = True
            self.watchdog.transition_function(True)
            await asyncio.sleep(0.5)

            if os.path.exists(core.PARENT_DIRECTORY / "IOTHUB.err"):
                logger.info(f"Removing IOTHUB.err")
                try:
                    os.remove(core.PARENT_DIRECTORY / "IOTHUB.err")
                except Exception as e:
                    logger.error(f"Cannot delete IOTHUB.err file: {e}")

        except Exception as e:
            self.connected = False
            logger.error(f"Not able to connect to IoTHub. Error: {e}")

            if general_settings.get("useErrFiles", False):
                logger.warning(f"Writing IOTHUB.err")
                path_obj = core.PARENT_DIRECTORY / "IOTHUB.err"
                try:
                    path_obj.touch()
                except Exception as e:
                    logger.error(f"Cannot touch IOTHUB.err file: {e}")

    @check_valid_device
    async def send_message(self, data: list[dict]):
        """
        Send IoT data in the new schema:
        [
            {
                "device": str,
                "schema": [...],
                "records": [[...], [...], ...]
            },
            ...
        ]
        Batches multiple devices into a single message, as long as total size < 230 KB.
        """
        if not self.connected:
            await self.connect()

        if not self.connected:
            logger.warning("Could not send message to IoTHub: failure to connect.")
            return

        batch = []
        for device_data in data:
            device_id = device_data.get("device") or device_data.get("id", {}).get(
                "ip", "unknown"
            )
            records = device_data.get("records", [])
            schema = device_data.get("schema", [])

            if not records or not schema:
                continue

            start = 0
            while start < len(records):
                # Binary search to find max chunk size for this device
                low, high = 1, len(records) - start
                best_chunk = 1

                while low <= high:
                    mid = (low + high) // 2
                    chunk = {
                        "device": device_id,
                        "schema": schema,
                        "records": records[start : start + mid],
                    }
                    test_batch = batch + [chunk]
                    message = Message(json.dumps(test_batch))
                    if message.get_size() < 230_000:
                        best_chunk = mid
                        low = mid + 1
                    else:
                        high = mid - 1

                # Add the best chunk to the batch
                chunk = {
                    "device": device_id,
                    "schema": schema,
                    "records": records[start : start + best_chunk],
                }
                batch.append(chunk)
                start += best_chunk

                # If batch is near full, send it
                message = Message(json.dumps(batch))
                if message.get_size() >= 230_000:
                    try:
                        await self.device_client.send_message(message)
                        logger.info(
                            f"Sent batch of {len(batch)} device chunks, size {message.get_size()} bytes"
                        )
                        await asyncio.sleep(0.5)
                    except Exception as e:
                        logger.error(f"Could not send to IoTHub: {e}")
                        self.connected = False
                        self.watchdog.transition_function(False)
                        return
                    batch = []

        # Send any remaining data
        if batch:
            message = Message(json.dumps(batch))
            try:
                await self.device_client.send_message(message)
                logger.info(
                    f"Sent final batch of {len(batch)} device chunks, size {message.get_size()} bytes"
                )
            except Exception as e:
                logger.error(f"Could not send final batch to IoTHub: {e}")
                self.connected = False

    @check_valid_device
    async def disconnect(self):
        logging.info(f"Disconnecting from IoTHub")
        if self.connected:
            await self.device_client.disconnect()
            logging.info(f"Disconnected from IoTHub")
        else:
            logging.debug(f"Device was not connected to IoTHub")

    def __repr__(self):
        return f"IoTDevice(device_id={self.device_id}, connected={self.connected})"
