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
from datetime import datetime, timezone
import copy

logger = logging.getLogger(__name__)

if platform.system() == "Linux":
    certificate = core.PARENT_DIRECTORY / "development_keys" / "CertificateTest.pfx"
else:
    certificate = None
    raise NotImplementedError("Only Linux is supported right now")

with open(core.AZURE_SETTINGS, "r") as f:
    azure_settings = json.load(f)


class IoTDevice:
    def __init__(self):
        logger.info(f"Creating IoTDevice instance")
        self.hostname: str = ""
        self.device_key: str = ""
        self.connected: bool = False
        self.device_client: IoTHubDeviceClient | None = None
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
        self.sas_ttl: int = azure_settings.get("sas_ttl", 0) * 24 * 60 * 60

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

    async def send_message(self, data: list[dict], ip: str):
        if not self.connected:
            await self.connect()

        if not self.connected:
            logger.warning("Could not send message to IoTHub: Failure to connect.")
            return

        frames = [self.denormalize_dict(d, ip) for d in data]
        frames = [f for f in frames if f is not None]

        master_frame = {
            "packets": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        for frame in frames:
            base_packet = {
                "id": frame["id"],
                "keys": [],
                "values": [],
            }

            for k, v in zip(frame["keys"], frame["values"]):
                base_packet["keys"].append(k)
                base_packet["values"].append(v)

                packet_copy = copy.deepcopy(base_packet)
                master_frame["packets"].append(packet_copy)

                payload = json.dumps(master_frame)
                message = Message(payload)
                size = message.get_size()

                if size >= (256 * 1024) - 512:
                    # Remove last packet and send
                    master_frame["packets"].pop()
                    base_packet["keys"].pop()
                    base_packet["values"].pop()

                    payload = json.dumps(master_frame)
                    message = Message(payload)
                    await self.device_client.send_message(message)
                    logger.info(
                        f"Sent message to IoTHub with size {message.get_size()}"
                    )

                    # Reset master_frame and continue with current base_packet
                    master_frame = {
                        "packets": [],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    master_frame["packets"].append(copy.deepcopy(base_packet))

        # Final send if master_frame has leftover packets
        if master_frame["packets"]:
            payload = json.dumps(master_frame)
            message = Message(payload)
            await self.device_client.send_message(message)
            logger.info(f"Sent final message to IoTHub with size {message.get_size()}")

    def disconnect(self):
        logging.info(f"Disconnecting from IoTHub")
        if self.connected:
            asyncio.run(self.device_client.disconnect())
            logging.info(f"Disconnected from IoTHub")
        else:
            logging.debug(f"Device was not connected to IoTHub")

    def denormalize_dict(self, ret: dict, ip: str) -> dict | None:
        id_fields = ["@nodetype", "@node", "@mod", "@point"]
        id_block = {k: ret.get(k) for k in id_fields if k in ret}
        id_block["ip"] = ip

        keys = []
        values = []

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
            walk(
                {
                    k: v
                    for k, v in ret.items()
                    if k not in ("nodetype", "node", "mod", "point")
                }
            )
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
