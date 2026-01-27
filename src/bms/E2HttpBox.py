from pprint import pprint
import logging
import asyncio
from .E2HttpInterface import E2HttpInterface, CELLTYPE_MAPPINGS_TABLE
from dataclasses import dataclass, field, fields, asdict
import json
import core


logger = logging.getLogger(__name__)

with open(core.GENERAL_SETTINGS, "r") as f:
    general_settings = json.load(f)


@dataclass
class Point:
    bypasstime: str
    dataType: str
    engUnits: str
    fail: bool
    notice: bool
    override: bool
    ovtime: str
    ovtype: str
    name: str
    value: str
    alarm: bool


@dataclass
class Alarm:
    acked: bool
    acktimestamp: str
    ackuser: str
    advcode: int
    advid: int
    alarm: bool
    engUnits: str
    fail: bool
    limit: str
    notice: bool
    priority: int
    reportvalue: str
    reset: bool
    rtn: bool
    rtntimestamp: str
    source: str
    state: str
    text: str
    timestamp: str
    unacked: bool


@dataclass
class Cell:
    celllongname: str
    cellname: str
    celltypename: str
    controller: str
    celltype: int
    points: dict[str, Point] = field(default_factory=dict)


@dataclass
class Controller:
    model: str
    name: str
    node: int
    revision: str
    type: str
    subnet: int
    cells: list[Cell] = field(default_factory=list)
    alarms: list[Alarm] = field(default_factory=list)


class E2HttpBox:
    def __init__(self, ip: str, name: str) -> None:
        self.ip: str = ip
        self.name: str = name
        self.http_interface: E2HttpInterface = E2HttpInterface(ip)
        self.controllers: list[Controller] = []
        self.initialized: bool = False
        self.max_buffer_size: int = general_settings.get("e2_buffer_length", 75)

    async def initialize(self):
        await self.get_cells()
        self.initialized = True

    def get_data(self):
        logger.info(f"Fetching data")
        data = []
        for controller in self.controllers:
            for cell in controller.cells:
                record = {
                    "@nodetype": "E2",
                    "@node": controller.name,
                    "@mod": controller.revision,
                    "@point": cell.cellname,
                    "ip": self.ip,
                }
                for k, v in cell.points.items():
                    record[k] = asdict(v)
                data.append(record)

            for alarm in controller.alarms:
                record = {
                    "@nodetype": "E2",
                    "@node": controller.name,
                    "@mod": controller.revision,
                    "@point": f"alarm_{alarm.advid}",
                    "ip": self.ip,
                }
                for k, v in asdict(alarm).items():
                    record[k] = v
                data.append(record)
        return data

    async def get_controllers(self):
        logger.info(f"Getting controllers...")
        x = await self.http_interface.get_controller_list()
        controller_fields = {f.name for f in fields(Controller)}
        controllers = x.get("result", [])
        if len(controllers) > 0:
            self.controllers = [
                Controller(**{k: v for k, v in y.items() if k in controller_fields})
                for y in controllers
            ]

    async def get_cells(self):
        logger.info(f"Getting cells...")
        if len(self.controllers) == 0:
            logger.info(f"No controllers are known! Auto discovering controllers...")
            await self.get_controllers()

        for controller in self.controllers:
            resp = await self.http_interface.get_cell_list(controller.name)
            celldata = resp.get("result", {}).get("data", [])
            for cell in celldata:
                controller.cells.append(Cell(**cell))

    async def poll_all_buffered(self):
        if len(self.controllers) == 0:
            await self.get_cells()

        logger.info(f"Polling all data points using buffered requests")
        request_list = []
        for controller in self.controllers:
            # Get alarms
            controller.alarms = []
            try:
                resp = await self.http_interface.get_alarm_list(controller.name)
                result = resp.get("result", {}).get("data", [])
                for each in result:
                    controller.alarms.append(Alarm(**each))
            except Exception as e:
                logger.error(f"{e}")

            # Get request list for all properties for all cells
            for cell in controller.cells:
                table = CELLTYPE_MAPPINGS_TABLE[
                    CELLTYPE_MAPPINGS_TABLE.celltype == str(cell.celltype)
                ]
                request_list.extend(
                    [
                        f"{controller.name}:{cell.cellname}:{idx}"
                        for idx in table.property_index.tolist()
                    ]
                )

        # re-normalize (THIS IS REALLY JANKY, NEED TO FIX LATER)
        for i in range(0, len(request_list), self.max_buffer_size):
            logger.info(
                f"{(i/len(request_list))*100:.2f}% done with fetching point data"
            )
            try:
                resp = await self.http_interface.get_multi_expanded_status_buffer(
                    request_list[i : i + self.max_buffer_size]
                )
                result = resp.get("result", {}).get("data", [])
                for entry in result:
                    prop_split = entry["prop"].split(":")

                    for controller in self.controllers:
                        if prop_split[0] == controller.name:
                            for cell in controller.cells:
                                if prop_split[1] == cell.cellname:
                                    mapping = CELLTYPE_MAPPINGS_TABLE[
                                        (
                                            CELLTYPE_MAPPINGS_TABLE.property_index
                                            == prop_split[2]
                                        )
                                    ]
                                    mapping_specific = mapping[
                                        mapping.celltype == str(cell.celltype)
                                    ]
                                    property_name = mapping_specific[
                                        "property_name"
                                    ].iloc[0]
                                    point_data = {
                                        k: v
                                        for k, v in entry.items()
                                        if k
                                        in (
                                            "alarm",
                                            "bypasstime",
                                            "dataType",
                                            "engUnits",
                                            "fail",
                                            "notice",
                                            "override",
                                            "ovtime",
                                            "ovtype",
                                            "value",
                                        )
                                    }
                                    point_data["name"] = property_name
                                    cell.points[property_name] = Point(**point_data)
                                    break

            except Exception as e:
                print(e)
                logger.error(f"Error: {e}")

    async def poll_all(self):
        if len(self.controllers) == 0:
            await self.get_cells()

        logger.info(f"Getting expanded statuses for all cells")
        for controller in self.controllers:
            controller.alarms = []
            for cell in controller.cells:
                try:
                    resp = await self.http_interface.get_multi_expanded_status(
                        controller=cell.controller,
                        cellname=cell.cellname,
                        celltype=str(cell.celltype),
                    )
                    result = resp.get("result", {}).get("data", [])

                    for each in result:
                        propval = each["prop"].split(":")
                        mapping = CELLTYPE_MAPPINGS_TABLE[
                            (CELLTYPE_MAPPINGS_TABLE.property_index == propval[-1])
                        ]
                        mapping_specific = mapping[
                            mapping.celltype == str(cell.celltype)
                        ]
                        property_name = mapping_specific["property_name"].iloc[0]
                        point_data = {
                            k: v
                            for k, v in each.items()
                            if k
                            in (
                                "alarm",
                                "bypasstime",
                                "dataType",
                                "engUnits",
                                "fail",
                                "notice",
                                "override",
                                "ovtime",
                                "ovtype",
                                "value",
                            )
                        }
                        point_data["name"] = property_name
                        cell.points[property_name] = Point(**point_data)
                except Exception as e:
                    logger.error(f"{e}")

            logging.info(f"Getting alarms for controller {controller.name}")
            try:
                resp = await self.http_interface.get_alarm_list(controller.name)
                result = resp.get("result", {}).get("data", [])
                for each in result:
                    controller.alarms.append(Alarm(**each))
            except Exception as e:
                logger.error(f"{e}")
