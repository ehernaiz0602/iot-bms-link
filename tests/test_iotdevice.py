import srcpath
import pytest
from azure_connection.IoTDevice import IoTDevice
from core.files import PARENT_DIRECTORY, GENERAL_SETTINGS
import asyncio
import os
import json


def test_valid_device():
    dev = IoTDevice()
    dev.valid_device = False
    result = asyncio.run(dev.connect())
    assert result is False


def test_connect():
    dev = IoTDevice()
    asyncio.run(dev.connect())
    assert dev.connected


def test_err_files():
    with open(GENERAL_SETTINGS, "r") as f:
        general_settings = json.load(f)

    if not general_settings.get("useErrFiles", False):
        assert True
        return

    dev = IoTDevice()
    dev.hostname = "dummy"
    asyncio.run(dev.connect())

    if os.path.exists(PARENT_DIRECTORY / "IOTHUB.err"):
        os.remove(PARENT_DIRECTORY / "IOTHUB.err")
        assert True
    else:
        assert False
