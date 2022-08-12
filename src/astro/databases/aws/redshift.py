"""AWS Redshift table implementation."""
import sqlalchemy
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from airflow.providers.amazon.aws.hooks.redshift_sql import RedshiftSQLHook

from google.api_core.exceptions import (
    ClientError,
    Conflict,
    Forbidden,
    GoogleAPIError,
    InvalidArgument,
)
from google.api_core.exceptions import NotFound as GoogleNotFound
from google.api_core.exceptions import (
    ResourceExhausted,
    RetryError,
    ServerError,
    ServiceUnavailable,
    TooManyRequests,
    Unauthorized,
    Unknown,
)

from google.protobuf import timestamp_pb2  # type: ignore
from google.protobuf.struct_pb2 import Struct  # type: ignore
from google.resumable_media import InvalidResponse
from sqlalchemy import create_engine
from sqlalchemy.engine.base import Engine
from tenacity import retry, stop_after_attempt

from astro.constants import (
    DEFAULT_CHUNK_SIZE,
    FileLocation,
    FileType,
    LoadExistStrategy,
    MergeConflictStrategy,
)
from astro.databases.base import BaseDatabase, DatabaseCustomError
from astro.files import File
from astro.settings import REDSHIFT_SChEMA
from astro.sql.table import Metadata, Table

DEFAULT_CONN_ID = RedshiftSQLHook.default_conn_name
NATIVE_PATHS_SUPPORTED_FILE_TYPES = {
    FileType.CSV: "CSV",
    FileType.NDJSON: "NEWLINE_DELIMITED_JSON",
    FileType.PARQUET: "PARQUET",
}
BIGQUERY_WRITE_DISPOSITION = {"replace": "WRITE_TRUNCATE", "append": "WRITE_APPEND"}


class RedshiftDatabase(BaseDatabase):
    """
    Handle interactions with Redshift databases.
    """

    DEFAULT_SCHEMA = REDSHIFT_SChEMA

    illegal_column_name_chars: List[str] = ["."]
    illegal_column_name_chars_replacement: List[str] = ["_"]

    def __init__(self, conn_id: str = DEFAULT_CONN_ID):
        super().__init__(conn_id)

    @property
    def sql_type(self):
        return "redshift"

    @property
    def hook(self) -> RedshiftSQLHook:
        """Retrieve Airflow hook to interface with the Redshift database."""
        return RedshiftSQLHook(redshift_conn_id=self.conn_id, use_legacy_sql=False)

    @property
    def sqlalchemy_engine(self) -> Engine:
        """Return SQAlchemy engine."""
        uri = self.hook.get_uri()
        return create_engine(uri)

    @property
    def default_metadata(self) -> Metadata:
        """
        Fill in default metadata values for table objects addressing redshift databases

        :return:
        """
        # TODO: Change airflow RedshiftSQLHook to fetch database and schema separately.
        database = self.hook.conn.schema
        return Metadata(database=database, schema=self.DEFAULT_SCHEMA)

    def schema_exists(self, schema: str) -> bool:
        """
        Checks if a dataset exists in the Redshift

        :param schema: Redshift namespace
        """
        schema_result = self.hook.run(
            "SELECT schema_name FROM information_schema.schemata WHERE lower(schema_name) = lower(%s);",
            parameters={"schema_name": schema.lower()},
            handler=lambda x: [y[0] for y in x.fetchall()],
        )
        return len(schema_result) > 0

    @staticmethod
    def get_merge_initialization_query(parameters: Tuple) -> str:
        """
        Handles database-specific logic to handle constraints
        for Redshift. The only constraint that Redshift supports
        is NOT NULL.
        """
        return "RETURN"

    def table_exists(self, table: Table) -> bool:
        """
        Check if a table exists in the database.

        :param table: Details of the table we want to check that exists
        """
        inspector = sqlalchemy.inspect(self.sqlalchemy_engine)
        return bool(inspector.dialect.has_table(self.connection, table.name, schema=table.metadata.schema))

    def load_pandas_dataframe_to_table(
        self,
        source_dataframe: pd.DataFrame,
        target_table: Table,
        if_exists: LoadExistStrategy = "replace",
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> None:
        """
        Create a table with the dataframe's contents.
        If the table already exists, append or replace the content, depending on the value of `if_exists`.

        :param source_dataframe: Local or remote filepath
        :param target_table: Table in which the file will be loaded
        :param if_exists: Strategy to be used in case the target table already exists.
        :param chunk_size: Specify the number of rows in each batch to be written at a time.
        """
        source_dataframe.to_sql(
            target_table.name,
            self.connection,
            index=False,
            schema=target_table.metadata.schema,
            if_exists=if_exists,
            chunksize=chunk_size,
        )

    def merge_table(
        self,
        source_table: Table,
        target_table: Table,
        source_to_target_columns_map: Dict[str, str],
        target_conflict_columns: List[str],
        if_conflicts: MergeConflictStrategy = "exception",
    ) -> None:
        """
        Merge the source table rows into a destination table.
        The argument `if_conflicts` allows the user to define how to handle conflicts.

        :param source_table: Contains the rows to be merged to the target_table
        :param target_table: Contains the destination table in which the rows will be merged
        :param source_to_target_columns_map: Dict of target_table columns names to source_table columns names
        :param target_conflict_columns: List of cols where we expect to have a conflict while combining
        :param if_conflicts: The strategy to be applied if there are conflicts.
        """

        source_columns = list(source_to_target_columns_map.keys())
        target_columns = list(source_to_target_columns_map.values())

        target_table_name = self.get_table_qualified_name(target_table)
        source_table_name = self.get_table_qualified_name(source_table)

        statement = f"MERGE {target_table_name} T USING {source_table_name} S\
            ON {' AND '.join(['T.' + col + '= S.' + col for col in target_conflict_columns])}\
            WHEN NOT MATCHED BY TARGET THEN INSERT ({','.join(target_columns)}) VALUES ({','.join(source_columns)})"

        update_statement_map = ", ".join(
            [
                f"T.{target_columns[idx]}=S.{source_columns[idx]}"
                for idx in range(len(target_columns))
            ]
        )
        if if_conflicts == "update":
            update_statement = f"UPDATE SET {update_statement_map}"  # skipcq: BAN-B608
            statement += f" WHEN MATCHED THEN {update_statement}"
        self.run_sql(sql_statement=statement)

    def is_native_load_file_available(
        self, source_file: File, target_table: Table
    ) -> bool:
        """
        Check if there is an optimised path for source to destination.

        :param source_file: File from which we need to transfer data
        :param target_table: Table that needs to be populated with file data
        """
        return False
