import srcpath
import pytest
import pytest_asyncio
from azure_connection.IoTDevice import IoTDevice
from core.files import PARENT_DIRECTORY, GENERAL_SETTINGS
import asyncio
import os
import json
from azure.iot.device import Message


@pytest_asyncio.fixture(scope="module")
async def shared_device():
    dev = IoTDevice()
    await dev.connect()
    return dev


@pytest.mark.asyncio
async def test_valid_device():
    dev = IoTDevice()
    dev.valid_device = False
    result = await dev.connect()
    assert result is False


@pytest.mark.asyncio
async def test_connect():
    dev = IoTDevice()
    await dev.connect()
    assert dev.connected


# @pytest.mark.asyncio
# async def test_oversized_message(shared_device):
#     large_record = ["sensor", "node1", "modA", "pointX", "keyY", "X" * 5000]
#     records = [large_record for _ in range(60)]
#     payload = {
#         "device": "test-device",
#         "schema": ["nodetype", "node", "mod", "point", "key", "value"],
#         "records": records,
#     }
#
#     message = Message(json.dumps([payload]))
#     size = message.get_size()
#     print(f"Test message size: {size} bytes")
#
#     try:
#         await shared_device.device_client.send_message(message)
#         print("Oversized message sent successfully (unexpected)")
#         assert False
#     except Exception as e:
#         print(f"Expected failure: {e}")
#         assert True


@pytest.mark.asyncio
async def test_send_oversize_message(shared_device):
    large_record = ["sensor", "node1", "modA", "pointX", "keyY", "X" * 5000]
    records = [large_record for _ in range(60)]  # ~300 KB total
    payload = [
        {
            "device": "test-device",
            "schema": ["nodetype", "node", "mod", "point", "key", "value"],
            "records": records,
        }
    ]

    try:
        await shared_device.send_message(payload)
        print("Oversized message sent successfully!")
        assert True
    except Exception as e:
        print(f"Unexpected failure: {e}")
        assert False


# @pytest.mark.asyncio
# async def test_err_files():
#     with open(GENERAL_SETTINGS, "r") as f:
#         general_settings = json.load(f)
#
#     if not general_settings.get("useErrFiles", False):
#         assert True
#         return
#
#     dev.hostname = "dummy"
#     await dev.connect()
#
#     err_path = PARENT_DIRECTORY / "IOTHUB.err"
#     if os.path.exists(err_path):
#         os.remove(err_path)
#         assert True
#     else:
#         assert False
#     await dev.disconnect()
