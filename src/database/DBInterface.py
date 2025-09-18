import aiosqlite
import asyncio

from pandas.core.internals.blocks import quantile_compat
import core.files
import logging
import pandas as pd
from typing import Optional

logger = logging.getLogger(__name__)


class DBInterface:
    def __init__(self):
        self.db_path = core.files.DATABASE

    async def initialize(self):
        self.conn = await aiosqlite.connect(self.db_path)
        await self.conn.execute("PRAGMA foreign_keys = ON")
        await self.conn.commit()

    async def ensure_table(self, table_name, schema_dict):
        columns = ", ".join(f"{col} {dtype}" for col, dtype in schema_dict.items())
        await self.conn.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({columns})")
        await self.conn.commit()

        async with self.conn.execute(f"PRAGMA table_info({table_name})") as cursor:
            existing = {row[1] async for row in cursor}
        for col, dtype in schema_dict.items():
            if col not in existing:
                await self.conn.execute(
                    f"ALTER TABLE {table_name} ADD COLUMN {col} {dtype}"
                )
        await self.conn.commit()

    async def insert_data(self, table_name, data_dict):
        keys = ", ".join(data_dict.keys())
        placeholders = ", ".join("?" for _ in data_dict)
        values = tuple(data_dict.values())
        await self.conn.execute(
            f"INSERT INTO {table_name} ({keys}) VALUES ({placeholders})", values
        )
        await self.conn.commit()

    def df_to_sqlite_payload(self, df: pd.DataFrame):
        dtype_map = {
            "int64": "INTEGER",
            "float64": "REAL",
            "bool": "INTEGER",
            "object": "TEXT",
            "datetime64[ns]": "TEXT",
            "category": "TEXT",
        }

        schema_dict = {
            col: dtype_map.get(str(dtype), "TEXT")  # default to TEXT if unknown
            for col, dtype in df.dtypes.items()
        }

        data_dict = df.to_dict(orient="records")

        return schema_dict, data_dict

    async def upsert_data(self, table_name, data_dict, conflict_column):
        keys = ", ".join(data_dict.keys())
        placeholders = ", ".join("?" for _ in data_dict)

        updates = ", ".join(
            f"{key}=excluded.{key}"
            for key in data_dict.keys()
            if key != conflict_column
        )

        values = tuple(data_dict.values())

        query = f"""
        INSERT INTO {table_name} ({keys}) 
        VALUES ({placeholders}) 
        ON CONFLICT({conflict_column}) DO UPDATE SET {updates}
        """

        await self.conn.execute(query, values)
        await self.conn.commit()

    async def write_dataframe(
        self,
        table_name: str,
        df: pd.DataFrame,
        upsert: bool = False,
        conflict_column: Optional[str] = None,
    ):
        schema_dict, records = self.df_to_sqlite_payload(df)

        await self.ensure_table(table_name, schema_dict)

        if upsert:
            if not conflict_column:
                raise ValueError("conflict_column is required for upsert")
            for record in records:
                await self.upsert_data(table_name, records, conflict_column)
        else:
            for record in records:
                await self.insert_data(table_name, record)

    async def read_dataframe(self, table_name: str) -> pd.DataFrame:
        try:
            async with self.conn.execute(f"SELECT * FROM {table_name}") as cursor:
                columns = [description[0] for description in cursor.description]
                rows = await cursor.fetchall()

            return pd.DataFrame(rows, columns=columns)
        except Exception as e:
            logger.error(f"Could not read from {table_name}: {e}")

    async def delete_table(self, table_name):
        await self.conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        await self.conn.commit()

    async def clear_table(self, table_name):
        await self.conn.execute(f"DELETE FROM TABLE {table_name}")
        await self.conn.commit()

    async def close(self):
        try:
            logger.debug("Closing connection to database")
            await self.conn.close()
        except:
            logger.debug("No database connection to close")
