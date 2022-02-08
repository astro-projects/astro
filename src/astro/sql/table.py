"""
Copyright Astronomer, Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
from airflow.hooks.base import BaseHook
from airflow.models import DagRun, TaskInstance


class Table:
    def __init__(
        self,
        table_name="",
        conn_id=None,
        database=None,
        schema=None,
        warehouse=None,
        role=None,
    ):
        from astro.utils.schema_util import get_schema

        self.table_name = table_name
        self.conn_id = conn_id
        self.database = database
        self.schema = schema or get_schema()
        self.warehouse = warehouse
        self.conn_type = BaseHook.get_connection(self.conn_id).conn_type
        self.role = role

    def identifier_args(self):
        return (self.schema, self.table_name) if self.schema else (self.table_name,)

    def fully_qualified_name(self, schema=None):
        """
        To make our SQL queries more clear in scope and to allow queries containing multiple
        schemas or databases, we should start generating SQL that uses fully qualified names (eg.
        schema.table in postgres and DATABASE.SCHEMA.TABLE in snowflake).
        :param conn_type: What type of connection are we creating.
        :param schema: an optional schema if the output_table has a schema set. Defaults to the temp schema
        :return:
        """
        table_name = self.table_name
        schema = self.schema or schema
        if (self.conn_type == "postgres" or self.conn_type == "postgresql") and schema:
            table_name = schema + "." + self.table_name
        elif self.conn_type == "snowflake" and schema and "." not in self.table_name:
            table_name = self.database + "." + schema + "." + self.table_name
        return table_name

    def __str__(self):
        return f"Table(table_name={self.table_name}, database={self.database}, schema={self.schema}, conn_id={self.conn_id}, warehouse={self.warehouse})"


class TempTable(Table):
    def __init__(self, conn_id=None, database=None, warehouse=""):
        super().__init__(
            table_name="", conn_id=conn_id, database=database, warehouse=warehouse
        )

    def to_table(self, table_name: str, schema: str) -> Table:
        return Table(
            table_name=table_name,
            conn_id=self.conn_id,
            database=self.database,
            warehouse=self.warehouse,
            schema=schema,
        )


def create_table_name(context):
    ti: TaskInstance = context["ti"]
    dag_run: DagRun = ti.get_dagrun()
    table_name = f"{dag_run.dag_id}_{ti.task_id}_{dag_run.id}".replace("-", "_")
    if not table_name.isidentifier():
        table_name = f'"{table_name}"'
    return table_name
