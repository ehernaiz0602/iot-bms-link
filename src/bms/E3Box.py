import asyncio
import logging
from typing import Optional
from rich.tree import Tree
from rich import print as rprint
from .E3HttpInterface import E3HttpInterface

logger = logging.getLogger(__name__)


class E3Box:
    def __init__(self, ip: str, name: str):
        self.http_interface = E3HttpInterface(ip)
        self.ip = ip
        self.name = name
        self.groups: dict[str, Group] = {}

    async def get_groups(self):
        logger.info(f"{self.name} is getting groups")
        groups = await self.http_interface.get_groups()

        if groups:
            self.groups = {
                x.get("name", "null_name"): Group(x)
                for x in groups.get("result", {}).get("groups", [])
            }
        logger.info(f"{self.name} finished getting groups")

    async def update_all(self):
        logger.info(f"{self.name} is updating all data")
        await self.get_alarms()
        await self.get_values()
        logger.info(f"{self.name} finished updating all data")

    async def get_alarms(self) -> None:
        if self.groups == {}:
            await self.get_logged_points()

        logger.info(f"{self.name} is getting alarm information")
        alarm_buf: dict[str, list[dict[str, str]]] = {}
        alarm_data = await self.http_interface.get_alarms()
        if alarm_data:
            alarms = alarm_data.get("result", {}).get("alarms", [])
            alarms = [alarms] if not isinstance(alarms, list) else alarms

            for alarm in alarms:
                alarm_iid = alarm.get("iid", "")
                if alarm_iid not in alarm_buf:
                    alarm_buf[alarm_iid] = [alarm]
                else:
                    alarm_buf[alarm_iid].append(alarm)

            for group in self.groups.values():
                for app in group.applications.values():
                    try:
                        app.alarms = alarm_buf[app.iid]
                    except Exception as e:
                        logger.warning(f"No app to attach alarm to: {e}")
        logger.info(f"{self.name} finished updating alarm data")

    async def get_values(self) -> None:
        if not self.groups:
            await self.get_logged_points()

        logger.info(f"{self.name} is getting point values")

        for group in self.groups.values():
            for app in group.applications.values():
                pid_map = {f"{app.iid}:{pid.pid}": pid for pid in app.pids.values()}

                request_buffer = [{"ptr": ptr} for ptr in pid_map.keys()]
                response = await self.http_interface.get_point_values(request_buffer)

                if response:
                    points = response.get("result", {}).get("points", [])
                    for point in points:
                        try:
                            ptr = point.get("ptr", "")
                            value = point.get("val", None)
                            pid = pid_map.get(ptr)
                            if pid:
                                pid.present_value = value
                        except Exception as e:
                            logger.error(f"Could not update point: {e}")

        logger.info(f"{self.name} finished getting point values")

    async def get_logged_points(self) -> None:
        if self.groups == {}:
            await self.get_inventory()

        lgriids = await self.http_interface.get_default_log_group()

        if lgriids:
            lgriids = lgriids.get("result", {}).get("lgriid", [])
            lgriids = [lgriids] if not isinstance(lgriids, list) else lgriids

        pointerbuf: dict[str, dict[str, Pid]] = {}
        descrbuf: dict[str, dict[str, dict[str, str]]] = {}
        for lgriid in lgriids:
            lgpoints = await self.http_interface.get_apps_for_log_group(lgriid)
            lgpoints_pts = lgpoints.get("result", {}).get("loggedpoints", [])
            lgpoints_pts = (
                [lgpoints_pts] if not isinstance(lgpoints_pts, list) else lgpoints_pts
            )

            for entry in lgpoints_pts:
                try:
                    ptr_string = entry.get("ptr", None)
                    if ptr_string:
                        split = ptr_string.split(":")
                        iid = split[0]
                        pid = split[1]
                        if iid not in pointerbuf:
                            pointerbuf[iid] = {}
                            app_description = (
                                await self.http_interface.get_app_description(iid)
                            )
                            description_data = app_description.get("result", {}).get(
                                "points", []
                            )
                            if not description_data:
                                description_data = []
                            if iid not in descrbuf:
                                descrbuf[iid] = {}
                            for entry in description_data:
                                entry_pid = entry.get("pid", "")
                                if entry_pid not in descrbuf[iid]:
                                    descrbuf[iid][entry_pid] = entry

                        pointerbuf[iid][pid] = Pid(pid, descrbuf[iid][pid])
                except Exception as e:
                    logger.error(f"Unexpected error: {e}")

        for group in self.groups.values():
            for application in group.applications.values():
                if application.iid in pointerbuf:
                    pids = pointerbuf[application.iid]
                    for pid in pids.values():
                        pid.parent_application = application
                    application.pids = pids

    async def get_inventory(self):
        if self.groups == {}:
            await self.get_groups()

        apps = await self.http_interface.get_system_inventory()

        if apps:
            for each in apps.get("result", {}).get("aps", []):
                categorydef = each.get("categorydef", None)
                if categorydef in self.groups:
                    self.groups[categorydef].applications[
                        each.get("iid", "default")
                    ] = Application(each, self.groups[categorydef])

    def print_hierarchy(self):
        root = Tree(f"[bold]{self.ip}[/bold]")

        for gname, g in self.groups.items():
            if g.applications != {}:
                g_branch = root.add(f"[cyan]Group[/cyan] {gname} ({g.id})")
                for a in g.applications.values():
                    if a.pids:
                        app_branch = g_branch.add(
                            f"[cyan]Application[/cyan] {a.appname} ({a.categorydef})"
                        )
                        app_branch.add(
                            f"[yellow]Number of alarms[/yellow]: {len(a.alarms)}"
                        )
                        for pid in a.pids.values():
                            pid_branch = app_branch.add(f"[cyan]pid[/cyan] {pid.pid}")
                            pid_branch.add(f"[cyan]Value[/cyan] {pid.present_value}")
                            pid_branch.add(f"[cyan]Name[/cyan] {pid.normal_name}")

        rprint(root)

    def __repr__(self):
        return f"E3Box(ip={self.ip}, name={self.name})"


class Group:
    def __init__(self, group_data: dict):
        self.id: Optional[str] = group_data.get("id", None)
        self.is_native: Optional[bool] = group_data.get("isNative", None)
        self.name: Optional[str] = group_data.get("name", None)
        self.applications: dict[str, Application] = {}

    def __repr__(self):
        return f"Group(id={self.id})"


class Application:
    def __init__(self, application_data: dict, parent_group: Group):
        self.appname: Optional[str] = application_data.get("appname", None)
        self.apptype: Optional[str] = application_data.get("apptype", None)
        self.iid: Optional[str] = application_data.get("iid", None)
        self.category: Optional[str] = application_data.get("category", None)
        self.categorydef: Optional[str] = application_data.get("categorydef", None)
        self.parent_group: Group = parent_group
        self.pids: dict[str, Pid] = {}
        self.alarms: list[dict] = []

    def __repr__(self):
        return f"Application(appname={self.appname}, iid={self.iid}, category={self.category}, categorydef={self.categorydef})"


class Pid:
    def __init__(self, pid: str, descrdata: dict):
        self.pid: str = pid
        self.present_value = None
        self.normal_name: str = descrdata.get("desc", "")
        self.parent_application: Optional[Application] = None

    def __repr__(self):
        return f"Pid(pid={self.pid})"
