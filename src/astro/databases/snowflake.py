import pandas as pd
from airflow.providers.snowflake.hooks.snowflake import SnowflakeHook
from pandas.io.sql import SQLDatabase

from astro.constants import DEFAULT_CHUNK_SIZE, LoadExistStrategy
from astro.databases.base import BaseDatabase
from astro.sql.tables import Table
from astro.utils.dependencies import pandas_tools

DEFAULT_CONN_ID = SnowflakeHook.default_conn_name


class SnowflakeDatabase(BaseDatabase):
    """
    Handle interactions with Postgres databases. If this class is successful, we should not have any Postgres-specific
    logic in other parts of our code-base.
    """

    def __init__(self, conn_id: str = DEFAULT_CONN_ID):
        super().__init__(conn_id)

    @property
    def hook(self):
        """Retrieve Airflow hook to interface with the Postgres database."""
        return SnowflakeHook(snowflake_conn_id=self.conn_id)

    # def get_table_qualified_name(self, table: Table) -> str:
    #     """
    #     Return table qualified name. This is Database-specific.
    #     For instance, in Sqlite this is the table name. In Snowflake, however, it is the database, schema and table
    #
    #     :param table: The table we want to retrieve the qualified name for.
    #     """
    #     name: str = table.name
    #     return name

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

        db = SQLDatabase(engine=self.sqlalchemy_engine)
        # Make columns uppercase to prevent weird errors in snowflake
        source_dataframe.columns = source_dataframe.columns.str.upper()
        db.prep_table(
            source_dataframe,
            target_table.name,
            schema=target_table.metadata.schema,
            if_exists=if_exists,
            index=False,
        )
        pandas_tools.write_pandas(
            self.hook.get_conn(),
            source_dataframe,
            target_table.name,
            chunk_size=chunk_size,
            quote_identifiers=False,
        )
