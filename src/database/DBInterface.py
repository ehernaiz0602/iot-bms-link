import aiosqlite
import asyncio
import core.files
import logging
import pandas as pd
from collections.abc import Mapping, Sequence

logger = logging.getLogger(__name__)


class DBInterface:
    def __init__(self):
        self.db_path = core.files.DATABASE
        self.active: bool = False

    def __repr__(self):
        return f"DBInterface(active={self.active})"

    async def fetch_cov_data(
        self, data: list[dict], full_frame: bool = False
    ) -> list[dict]:
        if not self.active:
            await self.initialize()
            await self.ensure_table("data_table")

        incoming_df = self.raw_data_to_df(data)
        if full_frame:
            await self.clear_table("data_table")
        df = await self.upsert_and_get_changes(incoming_df, "data_table")

        grouped_payloads = []
        for ip, group in df.groupby("ip"):
            payload = {
                "device": ip,
                "schema": ["nodetype", "node", "mod", "point", "key", "value"],
                "records": group[
                    ["nodetype", "node", "mod", "point", "key", "value"]
                ].values.tolist(),
            }
            grouped_payloads.append(payload)

        return grouped_payloads

    async def initialize(self):
        self.conn = await aiosqlite.connect(self.db_path)
        await self.conn.execute("PRAGMA foreign_keys = ON")
        await self.conn.commit()
        self.active = True

    async def ensure_table(self, table_name: str):
        await self.conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                nodetype TEXT,
                node TEXT,
                mod TEXT,
                point TEXT,
                ip TEXT,
                key TEXT,
                value TEXT,
                primary key (nodetype, node, mod, point, ip, key)
            )
        """
        )
        await self.conn.commit()

    async def fetch_full_data(self) -> list[dict]:
        if not self.active:
            await self.initialize()
            await self.ensure_table("data_table")

        db_rows = await self.conn.execute_fetchall("SELECT * FROM data_table")

        # Build DataFrame, even if empty
        df = (
            pd.DataFrame(
                db_rows,
                columns=["nodetype", "node", "mod", "point", "ip", "key", "value"],
            )
            if db_rows
            else pd.DataFrame(
                columns=["nodetype", "node", "mod", "point", "ip", "key", "value"]
            )
        )

        if df.empty:
            return []

        # Ensure all fields have consistent string types and fill missing
        df = df.fillna("novalue").astype(str)

        # Group by IP (each IP → one device payload)
        grouped_payloads = []
        for ip, group in df.groupby("ip"):
            payload = {
                "device": ip,
                "schema": ["nodetype", "node", "mod", "point", "key", "value"],
                "records": group[
                    ["nodetype", "node", "mod", "point", "key", "value"]
                ].values.tolist(),
            }
            grouped_payloads.append(payload)

        return grouped_payloads

    async def upsert_and_get_changes(
        self, df: pd.DataFrame, table_name: str
    ) -> pd.DataFrame:
        """Compare incoming dataframe to DB, upsert changes, return changed/new rows."""
        await self.ensure_table(table_name)

        # Load current DB data into a dataframe
        db_df = await self.conn.execute_fetchall(f"SELECT * FROM {table_name}")
        db_df = (
            pd.DataFrame(
                db_df,
                columns=["nodetype", "node", "mod", "point", "ip", "key", "value"],
            )
            if db_df
            else pd.DataFrame(
                columns=["nodetype", "node", "mod", "point", "ip", "key", "value"]
            )
        )

        # Normalize incoming DataFrame columns
        df = df.rename(
            columns={
                "@nodetype": "nodetype",
                "@node": "node",
                "@mod": "mod",
                "@point": "point",
                "keys": "key",
                "values": "value",
            }
        ).fillna("novalue")

        # Merge to find changed or new rows
        merged = df.merge(
            db_df,
            on=["nodetype", "node", "mod", "point", "ip", "key"],
            how="left",
            suffixes=("", "_old"),
        )
        changed = merged[
            (merged["value_old"].isna()) | (merged["value"] != merged["value_old"])
        ]

        # Upsert changed rows
        async with self.conn.executemany(
            f"""
            INSERT INTO {table_name} (nodetype, node, mod, point, ip, key, value)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(nodetype, node, mod, point, ip, key)
            DO UPDATE SET value = excluded.value
            """,
            [
                tuple(r)
                for r in changed[
                    ["nodetype", "node", "mod", "point", "ip", "key", "value"]
                ].values
            ],
        ):
            pass
        await self.conn.commit()

        # Return only changed/new rows
        return changed[["nodetype", "node", "mod", "point", "ip", "key", "value"]]

    def raw_data_to_df(self, data_list: list[dict]):
        def denormalize_dict(ret: dict) -> dict | None:
            def walk(obj, prefix=""):
                if isinstance(obj, Mapping):
                    for k, v in obj.items():
                        new_prefix = f"{prefix}__{k}" if prefix else k
                        walk(v, new_prefix)
                elif isinstance(obj, Sequence) and not isinstance(
                    obj, (str, bytes, bytearray)
                ):
                    for idx, v in enumerate(obj):
                        new_prefix = f"{prefix}[{idx}]"
                        walk(v, new_prefix)
                else:
                    keys.append(prefix)
                    values.append(obj)

            try:
                id_fields = ["@nodetype", "@node", "@mod", "@point", "ip"]
                id_block = {k: ret.get(k) for k in id_fields if k in ret}

                keys: list[str] = []
                values: list[str] = []

                walk({k: v for k, v in ret.items() if k not in id_fields})
            except Exception as e:
                logger.error(f"Could not denormalize data: {e}")
                return None

            return {
                "id": id_block,
                "keys": keys,
                "values": values,
            }

        frames = []
        for data in data_list:
            d_dict = denormalize_dict(data)
            id_df = pd.DataFrame({k: [v] for k, v in d_dict["id"].items()})
            data_df = pd.DataFrame({"keys": d_dict["keys"], "values": d_dict["values"]})
            frames.append(id_df.merge(data_df, how="cross"))

        full_frame = pd.concat(frames)
        return full_frame

    async def delete_table(self, table_name):
        await self.conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        await self.conn.commit()

    async def clear_table(self, table_name):
        await self.conn.execute(f"DELETE FROM {table_name}")
        await self.conn.commit()

    async def close(self):
        try:
            logger.debug("Closing connection to database")
            await self.conn.close()
        except:
            logger.debug("No database connection to close")
