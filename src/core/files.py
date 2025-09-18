from pathlib import Path
import logging

logger = logging.getLogger(__name__)


# Folder structure
SRC_DIRECTORY = Path(__file__).resolve().parent.parent
PARENT_DIRECTORY = SRC_DIRECTORY.parent
CONFIG_DIRECTORY = PARENT_DIRECTORY / "config"
DATA_DIRECTORY = PARENT_DIRECTORY / "data"
LOG_DIRECTORY = PARENT_DIRECTORY / "logs"

# config files
AZURE_SETTINGS = CONFIG_DIRECTORY / "Settings-Azure.json"
IP_SETTINGS = CONFIG_DIRECTORY / "Settings-IP.json"

# data files
DATABASE = DATA_DIRECTORY / "database.db"
CERTIFICATE = DATA_DIRECTORY / "certificate.pfx"

# log files
LOG = LOG_DIRECTORY / "log.jsonl"

DIRECTORIES = {
    "src": SRC_DIRECTORY,
    "parent": PARENT_DIRECTORY,
    "config": CONFIG_DIRECTORY,
    "data": DATA_DIRECTORY,
    "logs": LOG_DIRECTORY,
}

FILES = {
    "azure_settings": AZURE_SETTINGS,
    "ip_settings": IP_SETTINGS,
    "database": DATABASE,
    "certificate": CERTIFICATE,
    "log": LOG,
}


def setup_files():
    logger.debug("Checking files...")

    for file, path in FILES.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if (not path.exists()) and (file != "certificate"):
            path.touch()
            logger.info(f"Created file at {str(path)}")

    logger.debug("All files verified")
