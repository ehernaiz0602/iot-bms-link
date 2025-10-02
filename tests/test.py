from pprint import pprint
import pandas as pd
import pickle
from collections import defaultdict, Counter
import json
import numbers
import asyncio
from functools import reduce
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from azure.iot.device import IoTHubDeviceClient, Message


# with open("box.pkl", "rb") as f:
#     example = pickle.load(f)

example = {
    "@mod": "-1",
    "@node": "-1",
    "@nodetype": "255",
    "@point": "-1",
    "leak_devices": [
        {"name": "A12 Deli Frz", "status": "0ppm"},
        {"name": "B19 Meat Clr", "status": "0ppm"},
        {"name": "B20 Meat prp", "status": "0ppm"},
        {"name": "B21 Seafood Clr", "status": "0ppm"},
        {"name": "B22 Serv Deli", "status": "0ppm"},
        {"name": "C1 Groc F", "status": "0ppm"},
        {"name": "C3 Bakery Frz", "status": "4ppm"},
        {"name": "C4 Bakery Clr", "status": "5ppm"},
        {"name": "C5 Dairy Clr", "status": "0ppm"},
        {"name": "C6 fruit Cut", "status": "0ppm"},
        {"name": "C7 Floral Clr", "status": "0ppm"},
        {"name": "C9 Prod Clr", "status": "2ppm"},
        {"name": "Protocol A B", "status": "3ppm"},
        {"name": "Protocol C D", "status": "4ppm"},
        {"name": "Leak Detecti:Zone 15", "status": "0ppm"},
        {"name": "Leak Detecti:Zone 16", "status": "0ppm"},
    ],
}


def normalize_data(data):
    # pre-process
    for each in [
        "aux_heats",
        "cooling_stages",
        "heat_reclaims",
        "inputs",
        "relays",
        "sensors",
    ]:
        one_down = each[:-1]
        if isinstance(data.get(each, {}).get(one_down, None), dict):
            data[each][one_down] = [data[each][one_down]]

        if isinstance(
            data.get(each, {}).get("nightsetback", {}).get("schedule", None), list
        ):
            data[each]["nightsetback"]["schedule"] = data[each]["nightsetback"][
                "schedule"
            ][0]

    if isinstance(
        data.get("dehumid_type", {}).get("stages", {}).get("stage", None), dict
    ):
        data["dehumid_type"]["stages"]["stage"] = [
            data["dehumid_type"]["stages"]["stage"]
        ]

    def deep_get(keys, default=None):
        try:
            return reduce(lambda d, k: d.get(k, {}), keys, data) or default
        except AttributeError:
            return default

    ret = {
        "nodetype": data.get("@nodetype"),
        "node": data.get("@node"),
        "mod": data.get("@mod"),
        "point": data.get("@point"),
        "rack_id": data.get("@rack_id"),
        "suction_id": data.get("@suction_id"),
        "name": data.get("@name"),
        "alternate_name": data.get("name"),
        "alternate_value": data.get("@value"),
        "type": data.get("type"),
        "value": data.get("#text"),
        "setpoint": data.get("@ctrl_val"),
        "offset": data.get("@offset"),
        "status": data.get("@status"),
        "modelname": data.get("@modelname"),
        "alternate_setpoint": data.get("@setpoint"),
        "device_id": data.get("device_id"),
        "ordernum": data.get("@ordernum"),
        "num_suction": data.get("num_suction"),
        "alternate_status": data.get("status"),
        "hvac_type": data.get("hvac_type"),
        "meter": {
            "kw": data.get("kw"),
            "kwh": {
                "value": data.get("kwh"),
                "reset_epoch": data.get("kwh_reset_epoch"),
            },
            "peak": {
                "reset_epoch": data.get("pk_reset_epoch"),
                "epoch": data.get("pk_epoch"),
                "kw": data.get("pk"),
            },
        },
        "condenser": {
            "alarm_high": {
                "limit": f'{deep_get(["read_condenser", "almhi_limit", "#text"])} {deep_get(["read_condenser", "almhi_limit", "@units"])}',
                "duration": f'{deep_get(["read_condenser", "almhi_dur", "#text"])} {deep_get(["read_condenser", "almhi_dur", "@units"])}',
            },
            "delta": f'{deep_get(["read_condenser", "cond_delta", "#text"])} {deep_get(["read_condenser", "cond_delta", "@units"])}',
            "type": deep_get(["read_condenser", "cond_type", "#text"]),
            "control_sensor": deep_get(["read_condenser", "control_type", "#text"]),
            "control_type": deep_get(["read_condenser", "control_type", "#text"]),
            "fans": {
                "number": deep_get(["read_condenser", "fans", "@num_fans"]),
                "type": deep_get(["read_condenser", "fans", "@type"]),
            },
            "condensing": {
                "max": f'{deep_get(["read_condenser", "max_cond", "#text"])} {deep_get(["read_condenser", "max_cond", "@units"])}',
                "min": f'{deep_get(["read_condenser", "min_cond", "#text"])} {deep_get(["read_condenser", "min_cond", "@units"])}',
            },
            "name": deep_get(["read_condenser", "name"]),
            "value": f'{deep_get(["read_condenser", "value", "#text"])} {deep_get(["read_condenser", "value", "@units"])}',
        },
        "suction_group": {
            "alarm_high": {
                "limit": f'{deep_get(["read_suction_group", "almhi_limit", "#text"])} {deep_get(["read_suction_group", "almhi_limit", "@units"])}',
                "duration": f'{deep_get(["read_suction_group", "almhi_dur", "#text"])} {deep_get(["read_suction_group", "almhi_dur", "@units"])}',
            },
            "alarm_low": {
                "limit": f'{deep_get(["read_suction_group", "almlo_limit", "#text"])} {deep_get(["read_suction_group", "almlo_limit", "@units"])}',
                "duration": f'{deep_get(["read_suction_group", "almlo_dur", "#text"])} {deep_get(["read_suction_group", "almlo_dur", "@units"])}',
            },
            "auto_schedule": deep_get(["read_suction_group", "auto_schedule"]),
            "num_circuits": deep_get(["read_suction_group", "num_circuits"]),
            "suction_control": deep_get(
                ["read_suction_group", "suction_control", "@type"]
            ),
            "suction_cutout": f'{deep_get(["read_suction_group", "suction_cutout", "#text"])} {deep_get(["read_suction_group", "suction_cutout", "@units"])}',
            "suction_target": f'{deep_get(["read_suction_group", "suction_target", "#text"])} {deep_get(["read_suction_group", "suction_target", "@units"])}',
            "value": f'{deep_get(["read_suction_group", "value", "#text"])} {deep_get(["read_suction_group", "value", "@units"])}',
            "name": deep_get(["read_suction_group", "name"]),
        },
        "aux_heats": {
            "stages": [
                {k.replace("@", ""): v for k, v in each.items()}
                for each in deep_get(["aux_heats", "aux_heat"], [{"None": None}])
            ],
            "nightsetback": {
                k.replace("@", ""): v
                for k, v in deep_get(
                    ["aux_heats", "nightsetback", "schedule"], {"None": None}
                ).items()
            },
        },
        "cooling_stages": {
            "stages": [
                {k.replace("@", ""): v for k, v in each.items()}
                for each in deep_get(
                    ["cooling_stages", "cooling_stage"], [{"None": None}]
                )
            ],
            "nightsetback": {
                k.replace("@", ""): v
                for k, v in deep_get(
                    ["cooling_stages", "nightsetback", "schedule"], {"None": None}
                ).items()
            },
        },
        "heat_reclaims": {
            "stages": [
                {k.replace("@", ""): v for k, v in each.items()}
                for each in deep_get(
                    ["heat_reclaims", "heat_reclaim"], [{"None": None}]
                )
            ],
            "nightsetback": {
                k.replace("@", ""): v
                for k, v in deep_get(
                    ["heat_reclaims", "nightsetback", "schedule"], {"None": None}
                ).items()
            },
        },
        "inputs": [
            {k.replace("@", ""): v for k, v in each.items()}
            for each in deep_get(["inputs", "input"], [{"None": None}])
        ],
        "relays": [
            {k.replace("@", ""): v for k, v in each.items()}
            for each in deep_get(["relays", "relay"], [{"None": None}])
        ],
        "sensors": [
            {k.replace("@", ""): v for k, v in each.items()}
            for each in deep_get(["sensors", "sensor"], [{"None": None}])
        ],
        "alarms": [
            {
                "ref": deep_get(["alarm_detail", alarm_id, "ref"]),
                "ref_tag_id": deep_get(["alarm_detail", alarm_id, "ref_tag_id"]),
                "status": deep_get(["alarm_detail", alarm_id, "status"]),
                "clearable": deep_get(["alarm_detail", alarm_id, "clearable"]),
                "action": deep_get(["alarm_detail", alarm_id, "action"]),
                "name": deep_get(["alarm_detail", alarm_id, "name"]),
                "setting": deep_get(["alarm_detail", alarm_id, "setting"]),
                "acknowledge": {
                    "account_number": str(
                        int(deep_get(["alarm_detail", alarm_id, "ack"], 0)) % 256
                    ),
                    "authorization_number": str(
                        int(deep_get(["alarm_detail", alarm_id, "ack"], 0)) // 256
                    ),
                    "acknowledgement": deep_get(
                        ["alarm_detail", alarm_id, "acknowledgement"]
                    ),
                    "user_account": deep_get(["alarm_detail", alarm_id, "ackUserAcct"]),
                },
                "epoch": {
                    "inactive": deep_get(["alarm_detail", alarm_id, "epoch_inactive"]),
                    "cleared": deep_get(["alarm_detail", alarm_id, "epoch_cleared"]),
                    "active": deep_get(["alarm_detail", alarm_id, "epoch"]),
                },
                "state": {
                    "active": deep_get(["alarm_detail", alarm_id, "active_state"]),
                    "acked": deep_get(["alarm_detail", alarm_id, "acked_state"]),
                    "cleared": deep_get(["alarm_detail", alarm_id, "cleared_state"]),
                },
            }
            for alarm_id in data.get("alarm_detail", {})
        ],
        "circuit": [
            {
                "id": circuit.get("@circuit_id"),
                "defrost": {
                    "type": circuit.get("defrosts", {}).get("@type"),
                    "duration": circuit.get("defrosts", {}).get("defrost_dur"),
                    "drip_delay": circuit.get("defrosts", {}).get("drip_delay"),
                    "min_defrost_time": circuit.get("defrosts", {})
                    .get("min_defrost", {})
                    .get("#text"),
                    "term": circuit.get("defrosts", {}).get("term", {}).get("@type"),
                },
                "name": circuit.get("name", {}).get("#text"),
                "name_index": circuit.get("name", {}).get("@name_index"),
                "status": circuit.get("status", {}).get("#text"),
                "temperature": {
                    "range": f'{circuit.get("temp_range", {}).get("#text")} {circuit.get("temp_range", {}).get("@units")}',
                    "target": f'{circuit.get("temp_target", {}).get("#text")} {circuit.get("temp_target", {}).get("@units")}',
                    "control": circuit.get("temp_control", {}).get("#text"),
                },
            }
            for circuit in data.get("read_circuit", [])
        ],
        "leak_devices": data.get("leak_devices", []),
    }

    # post-process
    ret = {k: v for k, v in ret.items() if v is not None}

    if ret.get("condenser").get("type") is None:
        del ret["condenser"]

    if ret.get("suction_group").get("name") is None:
        del ret["suction_group"]

    if ret.get("meter").get("kw") is None:
        del ret["meter"]

    # if ret.get("alarms") == []:
    #     del ret["alarms"]

    for each in ["aux_heats", "cooling_stages", "heat_reclaims"]:
        if ret.get(each).get("stages") == [{"None": None}]:
            del ret[each]
    for each in ["sensors", "relays", "inputs"]:
        if ret.get(each) == [{"None": None}]:
            del ret[each]

    final = {}
    for k, v in ret.items():
        if "alternate_" in k and k.replace("alternate_", "") not in ret.keys():
            final[k.replace("alternate_", "")] = v
        else:
            final[k] = v
    return final


def ret_to_array_schema(ret: dict) -> dict:
    id_fields = ["nodetype", "node", "mod", "point"]
    id_block = {k: ret.get(k) for k in id_fields if k in ret}

    keys = []
    values = []

    def walk(obj, prefix=""):
        if isinstance(obj, Mapping):
            for k, v in obj.items():
                new_prefix = f"{prefix}__{k}" if prefix else k
                walk(v, new_prefix)
        elif isinstance(obj, Sequence) and not isinstance(obj, (str, bytes, bytearray)):
            for idx, v in enumerate(obj):
                new_prefix = f"{prefix}[{idx}]"
                walk(v, new_prefix)
        else:
            keys.append(prefix)
            values.append(obj)

    walk(ret)

    return {
        "id": id_block,
        "denorm_keys": keys,
        "denorm_values": values,
    }


def denormalize_data(data, ip: str):
    ret = normalize_data(data)
    fin = ret_to_array_schema(ret)
    fin["id"]["ip"] = ip
    fin["timestamp"] = datetime.now(timezone.utc).isoformat()
    return fin


x = denormalize_data(example, "1.2.3.4")
x_id = pd.DataFrame([x.get("id")])
x_time = pd.DataFrame([x.get("timestamp")])
z = {"dv": x.get("denorm_values"), "dk": x.get("denorm_keys")}
zz = pd.DataFrame(z)
zz = zz.join(x_id, how="cross").join(x_time, how="cross")
pprint(zz)

# for x in range(len(data)):
#     pprint(data[x])
#     print("-------------------------------------------------")
#     pprint(normalize_data(data[x]))
#     print("-------------------------------------------------")
#     print("-------------------------------------------------")
