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

# Test files
IOTPAYLOADS = PARENT_DIRECTORY / "IOTPAYLOAD.json"

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
    "iotpayloads": IOTPAYLOADS,
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
    "logging_level": "debug",
    "log_file_max_size_mb": 2,
    "log_file_backup_count": 3,
    "http_request_delay": 2,
    "http_timeout_delay": 3,
    "http_retry_count": 5,
    "publish_interval_seconds": 30,
    "publish_all_interval_hours": 4,
    "soft_reset_interval_hours": 12,
    "use_err_files": False,
    "write_iot_payload_to_local_file": False,
    "fail_connection_number": 100,
    "allowable_azure_downtime_minutes": 60,
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
