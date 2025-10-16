import srcpath
import pytest
from azure_connection.IoTDevice import IoTDevice
import asyncio


def test_valid_device():
    dev = IoTDevice()
    dev.valid_device = False
    result = asyncio.run(dev.connect())
    assert result is False


def test_valid_denormalize_dict():
    dev = IoTDevice()
    dev.valid_device = True
    data = {"@nodetype": "0", "array": [{"f1": "v1"}]}
    result = dev.denormalize_dict(data)
    assert isinstance(result, dict)


def test_empty_denormalize_dict():
    dev = IoTDevice()
    dev.valid_device = True
    data = {}
    result = dev.denormalize_dict(data)
    assert isinstance(result, dict)


def test_invalid_denormalize_dict():
    dev = IoTDevice()
    dev.valid_device = True
    data = 1
    result = dev.denormalize_dict(data)
    assert result is None


def test_connect():
    dev = IoTDevice()
    asyncio.run(dev.connect())
    assert dev.connected
