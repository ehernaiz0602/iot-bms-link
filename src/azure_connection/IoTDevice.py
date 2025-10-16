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

logger = logging.getLogger(__name__)

with open(core.AZURE_SETTINGS, "r") as f:
    azure_settings = json.load(f)

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
    except Exception as e:
        logger.error(f"Could not load the certificate file: {e}")


def check_valid_device(func):
    """
    Decorator to check whether the IoTDevice is properly defined.
    Works with both async and sync methods.
    """
    if inspect.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(self, *args, **kwargs):
            if not self.valid_device:
                logger.warning("The IoTDevice definition is not valid.")
                return self.valid_device
            return await func(self, *args, **kwargs)

        return async_wrapper
    else:

        @functools.wraps(func)
        def sync_wrapper(self, *args, **kwargs):
            if not self.valid_device:
                logger.warning("The IoTDevice definition is not valid.")
                return self.valid_device
            return func(self, *args, **kwargs)

        return sync_wrapper


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
                    raise Exception()

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
        except Exception as e:
            self.connected = False
            logger.debug(f"Not able to connect to IoTHub. Error: {e}")

    @check_valid_device
    async def send_message(self, data: list[dict]):
        if not self.connected:
            await self.connect()

        if not self.connected:
            logger.warning("Could not send message to IoTHub: failure to connect.")
            return

        frames = [f for d in data if (f := self.denormalize_dict(d)) is not None]
        send_buf = []

        for frame in frames:
            keys = frame["keys"]
            values = frame["values"]
            frame_id = frame["id"]
            start = 0

            while start < len(keys):
                low, high = 1, len(keys) - start
                best_chunk = 1

                while low <= high:
                    mid = (low + high) // 2
                    chunk = {
                        "id": frame_id,
                        "keys": keys[start : start + mid],
                        "values": values[start : start + mid],
                    }
                    test_buf = send_buf + [chunk]
                    message = Message(json.dumps(test_buf))
                    size = message.get_size()

                    if size < 261_632:
                        best_chunk = mid
                        low = mid + 1
                    else:
                        high = mid - 1

                # Add the best chunk to the buffer
                chunk = {
                    "id": frame_id,
                    "keys": keys[start : start + best_chunk],
                    "values": values[start : start + best_chunk],
                }
                send_buf.append(chunk)
                start += best_chunk

                # Check if buffer is full
                message = Message(json.dumps(send_buf))
                if message.get_size() >= 261_632:
                    await self.device_client.send_message(message)
                    pass
                    logger.info(
                        f"Sent batch of {len(send_buf)} frames, size {message.get_size()}"
                    )
                    send_buf = []

        if send_buf:
            message = Message(json.dumps(send_buf))
            await self.device_client.send_message(message)
            pass
            logger.info(
                f"Sent final batch of {len(send_buf)} frames, size {message.get_size()}"
            )

    @check_valid_device
    async def disconnect(self):
        logging.info(f"Disconnecting from IoTHub")
        if self.connected:
            await self.device_client.disconnect()
            logging.info(f"Disconnected from IoTHub")
        else:
            logging.debug(f"Device was not connected to IoTHub")

    @check_valid_device
    def denormalize_dict(self, ret: dict) -> dict | None:
        def walk(obj, prefix=""):
            if isinstance(obj, Mapping):
                for k, v in obj.items():
                    new_prefix = f"{prefix}__{k}" if prefix else k
                    walk(v, new_prefix)
            elif isinstance(obj, Sequence) and not isinstance(
                obj, (str, bytes, bytearray)
            ):
                for idx, v in enumerate(obj):
                    new_prefix = f"{prefix}[{idx}]"
                    walk(v, new_prefix)
            else:
                keys.append(prefix)
                values.append(obj)

        try:
            id_fields = ["@nodetype", "@node", "@mod", "@point", "ip"]
            id_block = {k: ret.get(k) for k in id_fields if k in ret}

            keys: list[str] = []
            values: list[str] = []

            walk({k: v for k, v in ret.items() if k not in id_fields})
        except Exception as e:
            logger.error(f"Could not denormalize data: {e}")
            return None

        return {
            "id": id_block,
            "keys": keys,
            "values": values,
        }

    def __repr__(self):
        return f"IoTDevice(device_id={self.device_id}, connected={self.connected})"
