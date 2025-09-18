import asyncio
from .DanfossXMLInterface import DanfossXMLInterface
from core import aobject
from rich.tree import Tree
from rich import print as rprint
import logging
from pprint import pprint
from tenacity import retry, stop_after_attempt
from datetime import datetime, timezone
import time

logger = logging.getLogger(__name__)


def logtimer(func):
    async def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        await func(*args, **kwargs)
        duration = time.perf_counter() - start_time
        logging.info(f"Took {duration:.3f}s")

    return wrapper


class DanfossBox:
    def __init__(self, ip: str) -> None:
        self.xml_interface = DanfossXMLInterface(ip)
        self.nodetypes: dict[str, Nodetype] = {}
        self.hvacs: dict = {}  # Address table of ahindex: Point
        self.lighting: dict = {}  # Address table of index: Point

        # Shared metadata:
        self.read_suction_group: dict = {}
        self.read_condenser: dict = {}
        self.read_circuit: dict = {}

    @logtimer
    async def initialize(self):
        logging.info("Starting initial discovery")
        for each in [
            "discover_devices",
            "discover_relays",
            # "discover_additional_metadata",
            "discover_var_outs",
            "discover_lighting",
            "discover_hvacs",
            "discover_points_si",
        ]:
            try:
                await getattr(self, each)()
            except:
                pass
        logging.info("Finished initial discovery")

    async def add_nodetype(self, data: dict):
        try:
            nodetype_id = data.get("@nodetype", "null")
            if nodetype_id not in self.nodetypes:
                self.nodetypes[nodetype_id] = Nodetype(nodetype_id, self)
            await self.nodetypes[nodetype_id].add_node(data)
        except Exception as e:
            logger.warning(f"Could not add nodetype: {e}")

    @retry(stop=stop_after_attempt(3))
    async def discover_devices(self):
        logger.info("Starting device discovery")
        devices = await self.xml_interface.read_devices()
        devices = devices.get("device", [])
        if isinstance(devices, dict):
            devices = [devices]

        for dev in devices:
            await self.add_nodetype(dev)
        logger.info("Finished device discovery")

    @retry(stop=stop_after_attempt(3))
    async def discover_relays(self):
        logger.info("Starting relays discovery")
        relays = await self.xml_interface.read_relays()
        relays = relays.get("relay", [])
        if isinstance(relays, dict):
            relays = [relays]

        for rel in relays:
            rel["nodetype"] = "1"
            await self.add_nodetype({f"@{k}": v for k, v in rel.items()})
        logger.info("Finished relays discovery")

    @retry(stop=stop_after_attempt(3))
    async def discover_var_outs(self):
        logger.info("Starting var_outs discovery")
        var_outs = await self.xml_interface.read_var_outs()
        var_outs = var_outs.get("var_output", [])
        if isinstance(var_outs, dict):
            var_outs = [var_outs]

        for var in var_outs:
            var["nodetype"] = "3"
            await self.add_nodetype({f"@{k}": v for k, v in var.items()})
        logger.info("Finished var_outs discovery")

    @retry(stop=stop_after_attempt(3))
    async def discover_additional_metadata(self):
        self.read_date_time = await self.xml_interface.read_date_time()
        self.schedule_summary = await self.xml_interface.schedule_summary()

    @retry(stop=stop_after_attempt(3))
    async def discover_hvacs(self):
        logger.info("Starting HVACs discovery")
        hvacs = await self.xml_interface.read_hvacs()
        hvacs = hvacs.get("hvacs", "null")
        hvacs = x if isinstance((x := hvacs.get("hvac")), list) else [x]
        for hvac in hvacs:
            await self.add_nodetype(hvac)
            self.hvacs[hvac.get("@ahindex")] = self.get_point(
                hvac.get("@nodetype"),
                hvac.get("@node"),
                hvac.get("@mod"),
                hvac.get("@point"),
            )

        for unit in self.hvacs:
            hu = await self.xml_interface.read_hvac_unit(int(unit))
            await self.add_nodetype(hu)

            hs = await self.xml_interface.read_hvac_service(int(unit))
            hs["@nodetype"] = hu.get("@nodetype")
            hs["@node"] = hu.get("@node")
            hs["@mod"] = hu.get("@mod")
            hs["@point"] = hu.get("@point")
            await self.add_nodetype(hs)

        logger.info("Finished HVACs discovery")

    @retry(stop=stop_after_attempt(3))
    async def discover_lighting(self):
        logger.info("Starting lighting discovery")
        lightings = await self.xml_interface.read_lighting()

        if lightings.get("total") == "0":
            logger.info("Finished lighting discovery")
            return

        lightings = lightings.get("device", "null")
        lightings = x if isinstance((x := lightings), list) else [x]
        for lighting in lightings:
            await self.add_nodetype(lighting)
            self.lighting[lighting.get("index")] = self.get_point(
                lighting.get("@nodetype"),
                lighting.get("@node"),
                lighting.get("@mod"),
                lighting.get("@point"),
            )
        logger.info("Finished lighting discovery")

    @retry(stop=stop_after_attempt(3))
    async def update_monitors(self):
        logger.info("Updating nodetype monitor points")

        cmds = []
        points = self.yield_points()
        for each in points:
            cmds.append(
                {
                    "nodetype": each.parent_nodetype.nodetype_id,
                    "node": each.parent_node.node_id,
                    "mod": each.parent_mod.mod_id,
                    "point": each.point_id,
                }
            )
        resp = await self.xml_interface.read_monitor_detail(cmds)

        resp_s = resp.get("monitor")

        if resp_s is None:
            return
        elif not isinstance(resp_s, list):
            resp_s = [resp_s]

        for s in resp_s:
            sx = {
                k: v
                for k, v in s.items()
                if k in ["@nodetype", "@node", "@mod", "@point"]
            }
            sx["monitor"] = {
                k: v
                for k, v in s.items()
                if k not in ["@nodetype", "@node", "@mod", "@point"]
            }
            await self.add_nodetype(sx)
        logger.info("Finished updating monitoring points")

    @retry(stop=stop_after_attempt(3))
    async def update_nodetype_0(self):
        logger.info("Updating nodetype 0")
        nodetype = self.nodetypes.get("0")
        if not nodetype:
            return

        cmds = []
        try:
            for n_id, n in nodetype.nodes.items():
                for m_id, m in n.mods.items():
                    for p_id, p in m.points.items():
                        cmds.append(
                            {"node": int(n_id), "mod": int(m_id), "point": int(p_id)}
                        )
        except:
            return

        resp = await self.xml_interface.read_input(cmds)

        resp_s = resp.get("input")

        if resp_s is None:
            return
        elif not isinstance(resp_s, list):
            resp_s = [resp_s]

        for s in resp_s:
            s["@nodetype"] = "0"
            await self.add_nodetype(s)
        logger.info("Finished updating nodetype 0")

    @retry(stop=stop_after_attempt(3))
    async def update_nodetype_1(self):
        logger.info("Updating nodetype 1")
        nodetype = self.nodetypes.get("1")
        if not nodetype:
            return

        cmds = []
        try:
            for n_id, n in nodetype.nodes.items():
                for m_id, m in n.mods.items():
                    for p_id, p in m.points.items():
                        cmds.append(
                            {"node": int(n_id), "mod": int(m_id), "point": int(p_id)}
                        )
        except:
            return

        resp = await self.xml_interface.read_relay(cmds)

        resp_s = resp.get("relay")

        if resp_s is None:
            return
        elif not isinstance(resp_s, list):
            resp_s = [resp_s]

        for s in resp_s:
            s["@nodetype"] = "1"
            await self.add_nodetype(s)
        logger.info("Finished updating nodetype 1")

    @retry(stop=stop_after_attempt(3))
    async def update_nodetype_2(self):
        logger.info("Updating nodetype 2")
        nodetype2 = self.nodetypes.get("2")
        if not nodetype2:
            return

        cmds = []
        try:
            for n_id, n in nodetype2.nodes.items():
                for m_id, m in n.mods.items():
                    for p_id, p in m.points.items():
                        cmds.append(
                            {"node": int(n_id), "mod": int(m_id), "point": int(p_id)}
                        )
        except:
            return

        resp = await self.xml_interface.read_sensor(cmds)

        resp_s = resp.get("sensor")

        if resp_s is None:
            return
        elif not isinstance(resp_s, list):
            resp_s = [resp_s]

        for s in resp_s:
            s["@nodetype"] = "2"
            await self.add_nodetype(s)
        logger.info("Finished updating nodetype 2")

    @retry(stop=stop_after_attempt(3))
    async def update_nodetype_3(self):
        logger.info("Updating nodetype 3")
        nodetype3 = self.nodetypes.get("3")
        if not nodetype3:
            return

        cmds = []
        try:
            for n_id, n in nodetype3.nodes.items():
                for m_id, m in n.mods.items():
                    for p_id, p in m.points.items():
                        cmds.append(
                            {"node": int(n_id), "mod": int(m_id), "point": int(p_id)}
                        )
        except:
            return

        resp = await self.xml_interface.read_var_out(cmds)

        resp_s = resp.get("var_output")

        if resp_s is None:
            return
        elif not isinstance(resp_s, list):
            resp_s = [resp_s]

        for s in resp_s:
            s["@nodetype"] = "3"
            await self.add_nodetype(s)
        logger.info("Finished updating nodetype 3")

    @retry(stop=stop_after_attempt(3))
    async def update_nodetype_6(self):
        logger.info("Updating nodetype 6")
        resp = await self.xml_interface.read_meters()

        meters = resp.get("@read_meters")
        if meters == "0" or meters == None:
            return

        meter = resp.get("meter")
        meter = meter if isinstance(meter, list) else [meter]

        for m in meter:
            m["@nodetype"] = m.get("nodetype")
            m["@node"] = m.get("node")
            m["@mod"] = m.get("@mod", "-1")
            m["@point"] = m.get("@point", "-1")

            await self.add_nodetype(m)
        logger.info("Finished updating nodetype 6")

    @retry(stop=stop_after_attempt(3))
    async def update_lighting_zone(self):
        logger.info("Updating lighting zones")
        if len(self.lighting) == 0:
            return

        for idx, pt in self.lighting.items():
            resp = await self.xml_interface.read_lighting_zone(int(idx))

            for k, v in resp.items():
                pt.meta[k] = v
        logger.info("Finished updating lighting zones")

    @retry(stop=stop_after_attempt(3))
    async def update_alarms(self):
        logger.info("Updating alarms")
        alarm_references = await self.xml_interface.alarm_summary()

        acked_refs = alarm_references.get("acked", {}).get("ref", None)
        if acked_refs is not None:
            if not isinstance(acked_refs, list):
                acked_refs = [acked_refs]
            for ref in acked_refs:
                details = await self.xml_interface.alarm_detail(ref)
                for each in ["nodetype", "node", "mod", "point"]:
                    if each in details.keys():
                        details[f"@{each}"] = details.get(each)
                    final = {
                        k: v
                        for k, v in details.items()
                        if k in ["@nodetype", "@node", "@mod", "@point"]
                    }
                    final["alarm_detail_data"] = {
                        k: v
                        for k, v in details.items()
                        if k not in ["@nodetype", "@node", "@mod", "@point"]
                    }
                await self.add_nodetype(final)

        active_refs = alarm_references.get("active", {}).get("ref", None)
        if active_refs is not None:
            if not isinstance(active_refs, list):
                active_refs = [active_refs]
            for ref in active_refs:
                details = await self.xml_interface.alarm_detail(ref)
                for each in ["nodetype", "node", "mod", "point"]:
                    if each in details.keys():
                        details[f"@{each}"] = details.get(each)
                    final = {
                        k: v
                        for k, v in details.items()
                        if k in ["@nodetype", "@node", "@mod", "@point"]
                    }
                    final["alarm_detail_data"] = {
                        k: v
                        for k, v in details.items()
                        if k not in ["@nodetype", "@node", "@mod", "@point"]
                    }
                await self.add_nodetype(final)

        cleared_refs = alarm_references.get("cleared", {}).get("ref", None)
        cleared_refs = (
            cleared_refs if isinstance(cleared_refs, list) else [cleared_refs]
        )
        try:
            points = self.yield_points()
            for each in points:
                for ref in cleared_refs:
                    try:
                        del each.meta["alarm_detail"][ref]
                        logger.info(
                            f"Alarm {ref} has been cleared from active/acked alarms at {self.xml_interface.ip}"
                        )
                    except:
                        pass
        except Exception as e:
            logger.warning(f"Unexpected error when clearing old alarm data: {e}")
        logger.info("Finished updating alarms")

    @retry(stop=stop_after_attempt(3))
    async def update_cs_devices(self):
        devs = []
        device_num = 1
        device_zone = 1
        conseq_flag = 0
        while conseq_flag < 3:

            resp = await self.xml_interface.read_cs_device_value(
                device_num, device_zone
            )

            resp_x = resp.get("devicevalue", {})
            name = resp_x.get("@name", "")
            status = resp_x.get("@status", "Offline")

            if name == "" and "Offline" in status:
                break
            elif name == "":
                device_num += 1
                device_zone = 1
                conseq_flag += 1
            elif name != "" and "Offline" in status:
                device_num += 1
                device_zone = 1
                conseq_flag += 1
            else:
                devs.append({"name": name, "status": status})
                device_zone += 1
                conseq_flag = 0

        final = {
            "@nodetype": "255",
            "@node": "-1",
            "@mod": "-1",
            "@point": "-1",
            "leak_devices": devs,
        }
        await self.add_nodetype(final)

    @logtimer
    async def update_nodetypes(self):
        logger.info("Starting update loop")
        await self.update_nodetype_0()
        await self.update_nodetype_1()
        await self.update_nodetype_2()
        await self.update_nodetype_3()
        await self.update_nodetype_6()
        await self.update_lighting_zone()
        await self.update_alarms()
        await self.update_monitors()
        logger.info("Finished update loop")

    def print_hierarchy(self):
        root = Tree(f"[bold]{self.xml_interface.ip}[/bold]")

        for nt_id, nt in self.nodetypes.items():
            nt_branch = root.add(
                f"[cyan]Nodetype {nt_id}[/cyan] ({nt.verbose_nodetype_id})"
            )
            for node_id, node in nt.nodes.items():
                node_branch = nt_branch.add(f"Node {node_id}")
                for mod_id, mod in node.mods.items():
                    mod_branch = node_branch.add(f"Mod {mod_id}")
                    for point_id, point in mod.points.items():
                        if nt_id == "6":
                            val = point.meta.get("kw", "?")
                        else:
                            val = point.meta.get("#text", "?")
                        mod_branch.add(f"Point {point_id} : {val}")

        rprint(root)

    def get_point(self, nodetype_id, node_id, mod_id, point_id):
        nodetype_id = str(nodetype_id)
        node_id = str(node_id)
        mod_id = str(mod_id)
        point_id = str(point_id)

        nodetype = self.nodetypes.get(nodetype_id)
        if nodetype is None:
            return None

        node = nodetype.nodes.get(node_id)
        if node is None:
            return None

        mod = node.mods.get(mod_id)
        if mod is None:
            return None

        point = mod.points.get(point_id)
        if point is None:
            return None

        return point

    def yield_points(self):
        for nt_id, nt in self.nodetypes.items():
            for n_id, n in nt.nodes.items():
                for m_id, m in n.mods.items():
                    for p_id, p in m.points.items():
                        yield p


class Point(aobject):
    async def __init__(self, data, parent):
        self.point_id = data.get("@point", "null")
        self.alarms = {}
        self.meta = data
        self.parent_mod = parent
        self.parent_node = self.parent_mod.parent_node
        self.parent_nodetype = self.parent_node.parent_nodetype
        self.parent_dbox = self.parent_nodetype.parent_dbox
        logger.debug(
            f"New point at {self.parent_dbox.xml_interface.ip}: {self.point_id}"
        )

        await self.get_condenser_data()
        await self.get_suction_group_data()

    def __repr__(self):
        return f"<Point {self.point_id}>"

    @retry(stop=stop_after_attempt(3))
    async def get_condenser_data(self):
        if x := self.meta.get("@rack_id"):
            logger.debug(f"Checking condenser mappings")
            if x not in self.parent_dbox.read_condenser.keys():
                self.parent_dbox.read_condenser[x] = (
                    await self.parent_dbox.xml_interface.read_condenser(x)
                )
            self.meta["read_condenser"] = self.parent_dbox.read_condenser[x]

    @retry(stop=stop_after_attempt(3))
    async def get_suction_group_data(self):
        if (y := self.meta.get("@suction_id")) and (x := self.meta.get("@rack_id")):
            logger.debug(f"Checking suction group mappings")
            if (x, y) not in self.parent_dbox.read_suction_group.keys():
                self.parent_dbox.read_suction_group[(x, y)] = (
                    await self.parent_dbox.xml_interface.read_suction_group(x, y)
                )

                # read circuits
                if (
                    nc := self.parent_dbox.read_suction_group[(x, y)].get(
                        "num_circuits", None
                    )
                ) is not None:
                    logger.info("Discovering circuits")
                    try:
                        for i in range(int(nc)):
                            circ = await self.parent_dbox.xml_interface.read_circuit(
                                x, y, i + 1
                            )
                            if (x, y) not in self.parent_dbox.read_circuit.keys():
                                self.parent_dbox.read_circuit[(x, y)] = []
                            self.parent_dbox.read_circuit[(x, y)].append(circ)
                            logger.debug(f"Circuit {x}_{y}_{i+1} added")
                    except:
                        pass

            self.meta["read_suction_group"] = self.parent_dbox.read_suction_group[
                (x, y)
            ]
            self.meta["read_circuit"] = self.parent_dbox.read_circuit[(x, y)]


class Mod:
    def __init__(self, mod_id: str, parent):
        self.mod_id = mod_id
        self.points: dict[str, Point] = {}
        self.parent_node = parent
        self.parent_nodetype = self.parent_node.parent_nodetype
        self.parent_dbox = self.parent_nodetype.parent_dbox
        logger.debug(f"New mod at {self.parent_dbox.xml_interface.ip}: {mod_id}")

    async def add_point(self, data):
        point_id = data.get("@point", "null")
        if point_id not in self.points:
            self.points[point_id] = await Point(
                {k: v for k, v in data.items() if k not in ["alarm_detail_data"]}, self
            )
            ref = data.get("alarm_detail_data", {}).get("@current", None)
            if ref is not None:
                self.points[point_id].meta["alarm_detail"] = {}
                self.points[point_id].meta["alarm_detail"][ref] = data.get(
                    "alarm_detail_data"
                )
        else:
            for k, v in data.items():
                if k != "alarm_detail_data":
                    self.points[point_id].meta[k] = v
                else:
                    ref = v.get("@current", "-1")
                    if "alarm_detail" not in self.points[point_id].meta.keys():
                        self.points[point_id].meta["alarm_detail"] = {}
                    self.points[point_id].meta["alarm_detail"][ref] = v


class Node(aobject):
    async def __init__(self, node_id: str, parent):
        self.node_id = node_id
        self.mods: dict[str, Mod] = {}
        self.parent_nodetype = parent
        self.parent_dbox = self.parent_nodetype.parent_dbox
        # self.read_device_summary = (
        #     await self.parent_dbox.xml_interface.read_device_summary(self.node_id)
        # )
        logger.debug(f"New node at {self.parent_dbox.xml_interface.ip}: {node_id}")

    async def add_mod(self, data):
        mod_id = data.get("@mod", "null")
        if mod_id not in self.mods:
            self.mods[mod_id] = Mod(mod_id, self)
        await self.mods[mod_id].add_point(data)


class Nodetype:
    def __init__(self, nodetype_id: str, parent: DanfossBox):
        self.nodetype_id = nodetype_id
        verbose_nodetypes = {
            "0": "On/Off Input",
            "1": "Relay Output",
            "2": "Sensor Input",
            "3": "Variable Output",
            "6": "Meter",
            "16": "Generic Device",
            "255": "Empty Node",
        }
        self.verbose_nodetype_id = verbose_nodetypes.get(self.nodetype_id, "Unknown")
        self.nodes: dict[str, Node] = {}
        self.parent_dbox = parent
        logger.debug(
            f"New nodetype at {self.parent_dbox.xml_interface.ip}: {nodetype_id}"
        )

    async def add_node(self, data: dict):
        node_id = data.get("@node", "null")
        if node_id not in self.nodes:
            self.nodes[node_id] = await Node(node_id, self)
        await self.nodes[node_id].add_mod(data)
