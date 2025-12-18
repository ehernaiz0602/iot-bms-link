from collections.abc import Callable
import logging
import socks
import socket
import platform
import json
import core
import asyncio
from tenacity import Retrying, stop_after_attempt, wait_fixed
import atexit
import time

logger = logging.getLogger(__name__)

CPCR: str = f"43 50 43 52 00 01 19 00 00 00"
CONTROLLER_SELECT: str = f"01 00 00 09 00 00 00"

with open(core.GENERAL_SETTINGS, "r") as f:
    general_settings: dict[str, int | str] = json.load(f)


def socket_retry(method: Callable[..., bytes]) -> Callable[..., bytes | None]:
    def wrapper(self, *args, **kwargs):
        if not self.socket_open:
            self.connect()

        def attempt():
            return method(self, *args, **kwargs)

        # hook to log each failure
        def log_retry(retry_state):
            exc = retry_state.outcome.exception()
            logging.warning(
                f"Retry {retry_state.attempt_number} failed: {exc.__class__.__name__}: {exc}"
            )
            logger.debug(f"Resetting the socket object just in case")
            self.close()
            self.connect()

        retryer = Retrying(
            stop=stop_after_attempt(self.retries),
            wait=wait_fixed(self.request_delay),
            reraise=True,
            before_sleep=log_retry,  # called before sleeping after a failed attempt
        )

        try:
            tcp_delay = int(general_settings.get("e2_tcp_delay_milliseconds", 300))
        except:
            tcp_delay = 300

        tcp_delay = tcp_delay / 1000

        result = retryer(attempt) if self.socket_open else None

        self.close()

        if tcp_delay >= 0:
            time.sleep(tcp_delay)

        return result

    return wrapper


class E2SocketInterface:
    def __init__(self, ip: str, port: int = 1025, recv_size: int = 4096) -> None:
        self.ip: str = ip
        self.port: int = port
        self.recv_size: int = recv_size
        self.timeout: int = general_settings.get("http_timeout_delay", 3)
        self.retries: int = general_settings.get("http_retry_count", 3)
        self.request_delay: int = general_settings.get(
            "http_request_delay", 3
        )  # Not using HTTP but good enough descriptor
        self.socket_open: bool = False
        s = socks.socksocket()
        if platform.system() == "Linux":
            s.set_proxy(socks.SOCKS5, "127.0.0.1", 1080)
        s.settimeout(5)
        self.socket: socks.socksocket = s
        atexit.register(self.close)

    def connect(self):
        s = socks.socksocket()
        if platform.system() == "Linux":
            s.set_proxy(socks.SOCKS5, "127.0.0.1", 1080)
        s.settimeout(5)

        self.socket: socks.socksocket = s

        try:
            self.socket.connect((self.ip, self.port))
            self.socket_open = True
            logger.info(f"Connected to E2 communication socket")
        except Exception as e:
            logger.error(f"Could not open socket: {e}")

    def close(self):
        if self.socket_open:
            logger.info(f"Closing E2 communication socket")
            self.socket.close()
        self.socket_open = False

    def recv_all(self):
        data = b""
        while True:
            try:
                chunk = self.socket.recv(self.recv_size)
                if not chunk:
                    break
                data += chunk
            except socket.timeout:
                break
            except Exception as e:
                logger.error(f"Unhandled exception: {e}")
                self.socket_open = False
                raise e
        time.sleep(self.request_delay)
        return data

    def hex_dump(self, data: bytes):
        for i in range(0, len(data), 16):
            chunk = data[i : i + 16]
            hex_part = " ".join(f"{b:02X}" for b in chunk)
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "`" for b in chunk)
            print(f"{i:08X}  {hex_part:<48}  {ascii_part}")

    @socket_retry
    def get_controllers(self):
        logger.debug(f"Sending GetControllerList to {self.ip}")
        command = bytes.fromhex(
            f"{CPCR} 1a 00 00 00 01 00 00 00 00 00 00 00 32 00 00 02"
        )
        self.socket.sendall(command)
        response: bytes = self.socket.recv(self.recv_size)
        time.sleep(self.request_delay)
        if not response:
            self.socket_open = False
            raise ValueError("Invalid response received")
        return response

    @socket_retry
    def get_alarms(self, controller_number: int):
        command = bytes.fromhex(
            f"{CPCR} 2e 00 00 00 15 00 00 00 {controller_number:02X} {CONTROLLER_SELECT} 01 00 00 00 37 00 00 00 08 00 00 00 01 00 00 00 02 00 00 00"
        )
        self.socket.sendall(command)
        response: bytes = self.recv_all()
        if not response:
            self.socket_open = False
            raise ValueError("Invalid response received")
        return response

    @socket_retry
    def get_cells_and_apps(self, controller_number: int):
        logger.debug(f"Sending get celltypes and cells to controller")
        command = bytes.fromhex(
            f"{CPCR} 2e 00 00 00 15 00 00 00 {controller_number:02X} {CONTROLLER_SELECT} 01 00 00 00 20 00 00 00 08 00 00 00 02 00 00 00 01 00 00 00"
        )
        self.socket.sendall(command)
        response: bytes = self.recv_all()
        if not response:
            self.socket_open = False
            raise ValueError("Invalid response received")
        return response

    @socket_retry
    def get_cell_status(
        self, controller_number: int, cell_tag: str, properties: list[int]
    ):
        logger.debug(f"Reading property {properties[0]} at address {cell_tag}")

        def encode_property_index(p: int) -> str:
            return f"{p & 0xFF:02X} {(p >> 8) & 0xFF:02X}"

        query = [
            f"01 00 00 00 {cell_tag} 04 {encode_property_index(p)}" for p in properties
        ]
        query_string = " ".join(query)

        command = bytes.fromhex(
            f"{CPCR} 39 00 00 00 20 00 00 00 {controller_number:02X} {CONTROLLER_SELECT} "
            f"01 00 00 00 41 00 00 00 13 00 00 00 01 00 00 00 {len(properties):02X} 00 00 00 {query_string}"
        )
        self.socket.sendall(command)
        response: bytes = self.socket.recv(4096)
        if not response:
            raise ValueError("Invalid response received")
        return response
