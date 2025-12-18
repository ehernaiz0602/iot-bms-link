from __future__ import annotations
import logging
from typing import override
from .E2SocketInterface import E2SocketInterface
from dataclasses import dataclass, field
from rich.tree import Tree
from rich import print as rprint
import struct
from .E2Properties import E2_PROPERTIES


logger = logging.getLogger(__name__)


from dataclasses import dataclass, field


@dataclass
class Cell:
    name: str
    parent_controller: Controller
    parent_cell_type: CellType
    cell_address: str
    data: dict[str, str] = field(default_factory=dict)


@dataclass
class CellType:
    name: str
    parent_controller: Controller
    cells: dict[str, Cell] = field(default_factory=dict)

    def add_cell(self, data: dict):
        cell_name = data.get("cell_name")
        if not cell_name:
            return  # skip invalid
        if cell_name not in self.cells:
            self.cells[cell_name] = Cell(
                name=cell_name,
                parent_controller=self.parent_controller,
                parent_cell_type=self,
                cell_address=data.get("cell_address", "invalid"),
            )


@dataclass
class Controller:
    name: str
    controller_number: int
    cell_types: dict[str, CellType] = field(default_factory=dict)

    def add_celltype(self, data: dict):
        cell_type_name = data.get("cell_type")
        if not cell_type_name:
            return  # skip invalid
        if cell_type_name not in self.cell_types:
            self.cell_types[cell_type_name] = CellType(
                name=cell_type_name,
                parent_controller=self,
            )
        self.cell_types[cell_type_name].add_cell(data)


class E2Box:
    def __init__(self, ip: str, name: str) -> None:
        self.ip: str = ip
        self.name: str = name
        self.socket_interface: E2SocketInterface = E2SocketInterface(ip)
        self.controllers: list[Controller] = []
        self.initialized: bool = False

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

    def get_cells_and_apps(self, controller: Controller):

        if self.controllers == []:
            self.get_controllers()

        result = self.socket_interface.get_cells_and_apps(controller.controller_number)

        if not isinstance(result, bytes):
            return []

        logger.info(f"{self.name} is updating {controller.name}'s cells and apps")

        delimiter = bytes.fromhex("02 00 00 00 01 00 00 00")
        valid_prefix = bytes.fromhex("01 00 00 00")

        chunks = result.split(delimiter)
        chunked = [chunk for chunk in chunks if chunk.startswith(valid_prefix)]

        for data in chunked:
            chunk_delimiter = bytes.fromhex("00 00 00")
            data_chunks = data.split(chunk_delimiter)

            if len(data_chunks) == 6:
                parsed_data = {
                    "a": data_chunks[1],
                    "cell_type": data_chunks[2],
                    "b": data_chunks[3],
                    "c": data_chunks[4],
                    "cell_name": data_chunks[5][:-9],
                    "cell_address": data_chunks[5][-6:-2],
                    "d": data_chunks[5][:3],
                }

                parsed_data = {
                    **parsed_data,
                    "cell_type": parsed_data["cell_type"].decode(
                        "utf-8", errors="ignore"
                    ),
                    "cell_name": parsed_data["cell_name"].decode(
                        "utf-8", errors="ignore"
                    ),
                    "cell_address": " ".join(
                        f"{b:02X}" for b in parsed_data["cell_address"]
                    ),
                }
                controller.add_celltype(parsed_data)

    def get_data(self) -> list[dict]:
        data: list[dict] = []
        for controller in self.controllers:
            for celltype in controller.cell_types.values():
                for cell in celltype.cells.values():
                    record = {
                        "@nodetype": "E2",
                        "@node": controller.name,
                        "@mod": celltype.name,
                        "@point": cell.name,
                        "ip": self.ip,
                        **cell.data,
                    }
                    data.append(record)
        return data

    def get_cell_statuses(self):
        all_cells = [
            cell
            for controller in self.controllers
            for cell_type in controller.cell_types.values()
            for cell in cell_type.cells.values()
        ]

        for cell in all_cells:
            self.get_cell_status(cell)

    def get_cell_status(self, cell: Cell):
        for k, v in E2_PROPERTIES.get(cell.parent_cell_type.name, {}).items():
            if k in cell.data.keys() and str(cell.data[k])[0:4] == "-858":
                logger.debug(f"Skipping {k}, not active")
                continue

            logger.info(f"Getting {v} for cell {cell.name}")
            resp = self.socket_interface.get_cell_status(
                cell.parent_controller.controller_number,
                cell.cell_address,
                [k],
            )
            try:
                res = struct.unpack("<f", resp[61:65])
                res_round = round(res[0], 5)
                cell.data[v] = res_round
                logger.debug(f"result: {res_round}")
            except Exception as e:
                logger.error(f"Could not read data: {e}")

    def initialize(self):
        logger.info(f"Initializing E2 controllers")
        self.get_controllers()
        for controller in self.controllers:
            self.get_cells_and_apps(controller)
        self.initialized = True

    def print_hierarchy(self):
        root = Tree(f"[bold]{self.name}[/bold] @ {self.ip}")

        for controller in self.controllers:
            c_branch = root.add(
                f"[magenta]Controller[/magenta] {controller.controller_number} ({controller.name})"
            )

            for ct_name, ct in controller.cell_types.items():
                ct_branch = c_branch.add(f"[cyan]CellType[/cyan] {ct_name}")

                for cell_name, cell in ct.cells.items():
                    cell_branch = ct_branch.add(f"[green]Cell[/green] {cell_name}")
                    cell_branch.add(f"[yellow]Address[/yellow]: {cell.cell_address}")
                    for k, v in cell.data.items():
                        cell_branch.add(f"{k}: {v}")

        rprint(root)

    @override
    def __repr__(self) -> str:
        return f"E2Box(controllers={self.controllers})"
