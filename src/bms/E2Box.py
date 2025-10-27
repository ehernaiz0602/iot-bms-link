import logging
from typing import override
from .E2SocketInterface import E2SocketInterface
from dataclasses import dataclass, field


logger = logging.getLogger(__name__)


@dataclass
class Application:
    name: str


@dataclass
class Cell:
    name: str
    celltype: str
    applications: list[Application] = field(default_factory=list, repr=False)


@dataclass
class Controller:
    name: str
    controller_number: int
    cells: list[Cell] = field(default_factory=list, repr=False)


class E2Box:
    def __init__(self, ip: str, name: str) -> None:
        self.ip: str = ip
        self.name: str = name
        self.socket_interface: E2SocketInterface = E2SocketInterface(ip)
        self.controllers: list[Controller] = []

    def get_controllers(self):
        logger.info(f"{self.name} is getting controllers")
        result = self.socket_interface.get_controllers()

        self.controllers: list[Controller] = []
        if isinstance(result, bytes):
            logger.info(f"{self.name} is updating controller list")
            snippet = result[32:]
            i: int = 0
            while i < len(snippet):
                controller_section = snippet[i : i + 23]  # Each entry is 22 bytes long
                name = "".join(
                    chr(b) if 32 <= b < 127 else "" for b in controller_section[:10]
                )  # First 10 bytes are name of controller
                controller_number = controller_section[
                    15
                ]  # 16th byte is controller number
                self.controllers.append(
                    Controller(name=name, controller_number=controller_number)
                )
                i += 23
            logger.info(f"{self.name} finished updating controller list!")
            logger.info(f"{self.name} found controllers: {self.controllers}")
        else:
            logger.error(f"{self.name} could not update controller list")

    def split_by_ascii_delimiters_keep(
        self, data_struct: list[tuple[str, int]], delimiters: set[str]
    ) -> list[list[tuple[str, int]]]:
        """
        Split a list of (ascii_char, byte) tuples by multi-character delimiters in the ASCII view.
        The delimiters are *included* at the start of each group.
        """
        ascii_view = "".join(ch for ch, _ in data_struct)
        result = []

        # find all delimiter positions
        positions = []
        for d in delimiters:
            start = 0
            while True:
                idx = ascii_view.find(d, start)
                if idx == -1:
                    break
                positions.append((idx, d))
                start = idx + len(d)

        # sort delimiters by position
        positions.sort(key=lambda x: x[0])

        if not positions:
            return [data_struct]

        # handle text before the first delimiter (if any)
        first_pos, first_delim = positions[0]
        if first_pos > 0:
            pre = data_struct[:first_pos]
            if pre:
                result.append(pre)

        # now chunk from delimiter to next delimiter
        for i, (pos, delim) in enumerate(positions):
            start = pos
            end = positions[i + 1][0] if i + 1 < len(positions) else len(ascii_view)
            group = data_struct[start:end]
            if group:
                result.append(group)

        return result

    def get_cells_and_apps(self, controller: Controller):

        if self.controllers == []:
            self.get_controllers()

        result = self.socket_interface.get_cells_and_apps(controller.controller_number)

        if isinstance(result, bytes):
            logger.info(f"{self.name} is updating cells and apps")

            delimiters = {
                "Physical DO",
                "Physical DI",
                "Physical AI",
                "Analog Combiner",
                "Flexible Combine",
                "Log Group",
                "Area Controller",
                "Time Schedule",
                "Power Monitor",
                "Device Status",
                "Global Data",
                "Sensor AV",
                "Sensor DV",
                "Loop/Seq Ctrl",
                "Conversion Cell",
                "Condenser",
                "Circuits (Std)",
                "Enhanced Suct",
                "16 Analog Inputs",
                "8 Relay Outputs",
                "Note Pad",
                "ALARM SETUP",
                "User Access",
                "General Config",
                "Time and Date",
                "Network Setup",
                "NV Handler",
                "Remote Dial",
                "Advisory Log",
                "Access Log",
                "Override Log",
                "App Defaults",
            }

            ascii_data = "".join(chr(b) if 32 <= b < 127 else f"`" for b in result)
            data_struct = list(zip(ascii_data, result))

            groups = self.split_by_ascii_delimiters_keep(data_struct, delimiters)
            groups = groups[1:]
            return groups

    @override
    def __repr__(self) -> str:
        return f"E2Box(controllers={self.controllers})"
