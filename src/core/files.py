from pathlib import Path
import logging
import json
import sys

logger = logging.getLogger(__name__)


def get_root_directory():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent.parent.parent


PARENT_DIRECTORY = get_root_directory()

# Folder structure
CONFIG_DIRECTORY = PARENT_DIRECTORY / "config"
DATA_DIRECTORY = PARENT_DIRECTORY / "data"
LOG_DIRECTORY = PARENT_DIRECTORY / "logs"

# config files
AZURE_SETTINGS = CONFIG_DIRECTORY / "Settings-Azure.json"
IP_SETTINGS = CONFIG_DIRECTORY / "Settings-IP.json"
GENERAL_SETTINGS = CONFIG_DIRECTORY / "Settings-General.json"

# data files
DATABASE = DATA_DIRECTORY / "database.db"
CERTIFICATE = DATA_DIRECTORY / "certificate.pfx"

# log files
LOG = LOG_DIRECTORY / "log.jsonl"

DIRECTORIES = {
    "parent": PARENT_DIRECTORY,
    "config": CONFIG_DIRECTORY,
    "data": DATA_DIRECTORY,
    "logs": LOG_DIRECTORY,
}

FILES = {
    "azure_settings": AZURE_SETTINGS,
    "ip_settings": IP_SETTINGS,
    "general_settings": GENERAL_SETTINGS,
    "database": DATABASE,
    "certificate": CERTIFICATE,
    "log": LOG,
}

# default files
default_azure = {
    "tenant_id": "",
    "client_id": "",
    "store_id": "",
    "scope_id": "",
    "secret_name": "",
    "certificate_subject": "",
    "vault_name": "",
    "sas_ttl": 90,
}

default_general = {
    "loggingLevel": "info",
    "httpRequestDelay": 3,
    "httpTimeoutDelay": 3,
    "httpRetryCount": 3,
    "publishIntervalSeconds": 30,
}

default_ip = {
    "danfoss": [
        {
            "ip": "1.1.1.1",
            "name": "panel_01",
        },
        {
            "ip": "2.2.2.2",
            "name": "panel_02",
        },
    ],
    "emerson_e2": [
        {
            "ip": "1.1.1.1",
            "name": "panel_01",
        },
        {
            "ip": "2.2.2.2",
            "name": "panel_02",
        },
    ],
    "emerson_e3": [
        {
            "ip": "1.1.1.1",
            "name": "panel_01",
        },
        {
            "ip": "2.2.2.2",
            "name": "panel_02",
        },
    ],
}


def setup_files():
    logger.debug("Checking files...")

    def dump_default(default, path) -> None:
        with open(path, "w+") as f:
            json.dump(default, f, indent=2)

    for file, path in FILES.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if (not path.exists()) and (file != "certificate"):

            path.touch()

            match file:
                case "ip_settings":
                    dump_default(default_ip, path)
                case "azure_settings":
                    dump_default(default_azure, path)
                case "general_settings":
                    dump_default(default_general, path)
                case _:
                    pass

            logger.info(f"Created file at {str(path)}")

    logger.debug("All files verified")
