import math
import pathlib

import pandas as pd
import pytest
from airflow.decorators import task_group
from airflow.utils import timezone

from astro import sql as aql
from astro.constants import Database
from astro.databases.base import BaseDatabase
from astro.files import File
from astro.sql.table import Metadata, Table
from astro.utils.database import create_database_from_conn_id
from tests.sql.operators import utils as test_utils

DEFAULT_DATE = timezone.datetime(2016, 1, 1)
CWD = pathlib.Path(__file__).parent

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": 0,
}


def merge_keys(sql_name, mode):
    """
    To match with their respective API's, we have a slightly different "merge_keys" value
    when a user is using snowflake.
    :param sql_name:
    :return:
    """
    keys = []
    if mode == "single":
        keys = ["list"]
    if mode == "multi":
        keys = ["list", "sell"]
    if mode == "update":
        keys = ["list", "sell"]

    if sql_name == "snowflake":
        return {k: k for k in keys}

    return keys


@pytest.fixture
def merge_parameters(request, database_table_fixture):
    database, _ = database_table_fixture
    mode = request.param
    if mode == "single":
        return (
            {
                "merge_keys": merge_keys(database.sql_type, mode),
                "merge_columns": ["list"],
                "target_columns": ["list"],
                "conflict_strategy": "ignore",
            },
            mode,
        )
    elif mode == "multi":
        return (
            {
                "merge_keys": merge_keys(database.sql_type, mode),
                "merge_columns": ["list", "sell"],
                "target_columns": ["list", "sell"],
                "conflict_strategy": "ignore",
            },
            mode,
        )
    # elif mode == "update":
    return (
        {
            "merge_keys": merge_keys(database.sql_type, mode),
            "target_columns": ["list", "sell", "taxes"],
            "merge_columns": ["list", "sell", "age"],
            "conflict_strategy": "update",
        },
        mode,
    )


@aql.transform
def do_a_thing(input_table: Table):
    return "SELECT * FROM {{input_table}}"


@aql.run_raw_sql
def add_constraint(table: Table, columns):
    database = create_database_from_conn_id(table.conn_id)
    if database == Database.SQLITE:
        return (
            "CREATE UNIQUE INDEX unique_index ON {{table}}" + f"({','.join(columns)})"
        )
    elif database == Database.BIGQUERY:
        # bigquery does not have constraints, so we offer a useless statement
        return "SELECT 1 + 1"

    return (
        "ALTER TABLE {{table}} ADD CONSTRAINT airflow UNIQUE"
        + f" ({','.join(columns)})"
    )


@aql.dataframe
def validate_results(df: pd.DataFrame, mode):
    def set_compare(l1, l2):
        l1 = list(filter(lambda val: not math.isnan(val), l1))
        return set(l1) == set(l2)

    df = df.sort_values(by=["list"], ascending=True)

    if mode == "single":
        assert set_compare(df.age.to_list()[:-1], [60.0, 12.0, 41.0, 22.0])
        assert set_compare(df.taxes.to_list()[:-1], [3167.0, 4033.0, 1471.0, 3204.0])
        assert set_compare(df.taxes.to_list()[:-1], [3167.0, 4033.0, 1471.0, 3204.0])
        assert set_compare(df.list.to_list(), [160, 180, 132, 140, 240])
        assert set_compare(df.sell.to_list()[:-1], [142, 175, 129, 138])
    elif mode == "multi":
        assert set_compare(df.age.to_list()[:-1], [60.0, 12.0, 41.0, 22.0])
        assert set_compare(df.taxes.to_list()[:-1], [3167.0, 4033.0, 1471.0, 3204.0])
        assert set_compare(df.taxes.to_list()[:-1], [3167.0, 4033.0, 1471.0, 3204.0])
        assert set_compare(df.list.to_list(), [160, 180, 132, 140, 240])
        assert set_compare(df.sell.to_list()[:-1], [142, 175, 129, 138])
    elif mode == "update":
        assert df.taxes.to_list() == [1, 1, 1, 1, 1]
        assert set_compare(df.age.to_list()[:-1], [60.0, 12.0, 41.0, 22.0])


@task_group
def run_merge(
    target_table: Table,
    merge_table: Table,
    database: BaseDatabase,
    merge_parameters: dict,
    mode: str,
):
    con1 = add_constraint(target_table, merge_parameters["merge_keys"])

    merged_table = aql.merge(
        target_table=target_table,
        merge_table=merge_table,
        **merge_parameters,
    )
    con1 >> merged_table
    validate_results(df=merged_table, mode=mode)


@pytest.mark.integration
@pytest.mark.parametrize(
    "merge_parameters",
    [
        # "None",
        "single",
        "multi",
        "update",
    ],
    indirect=True,
)
@pytest.mark.parametrize(
    "database_table_fixture",
    [{"database": Database.SNOWFLAKE}, {"database": Database.BIGQUERY}],
    indirect=True,
    ids=["snowflake", "bigquery"],
)
@pytest.mark.parametrize(
    "tables_fixture",
    [
        {
            "items": [
                {
                    "file": File(
                        str(pathlib.Path(CWD.parent.parent, "data/homes_merge_1.csv"))
                    )
                },
                {
                    "file": File(
                        str(pathlib.Path(CWD.parent.parent, "data/homes_merge_2.csv"))
                    )
                },
            ]
        }
    ],
    indirect=True,
    ids=["two_tables_same_schema"],
)
def test_merge(database_table_fixture, tables_fixture, sample_dag, merge_parameters):
    database, _ = database_table_fixture
    target_table, merge_table = tables_fixture
    merge_params, mode = merge_parameters
    with sample_dag:
        run_merge(
            target_table=target_table,
            merge_table=merge_table,
            database=database,
            merge_parameters=merge_params,
            mode=mode,
        )
    test_utils.run_dag(sample_dag)


@pytest.mark.integration
@pytest.mark.parametrize(
    "database_table_fixture",
    [{"database": Database.SNOWFLAKE}, {"database": Database.BIGQUERY}],
    indirect=True,
    ids=["snowflake", "bigquery"],
)
@pytest.mark.parametrize(
    "tables_fixture",
    [
        {
            "items": [
                {"file": File(str(pathlib.Path(CWD.parent.parent, "data/sample.csv")))},
                {
                    "file": File(
                        str(pathlib.Path(CWD.parent.parent, "data/sample_part2.csv"))
                    )
                },
            ]
        }
    ],
    indirect=True,
    ids=["two_tables_same_schema"],
)
def test_merge_with_the_same_schema(database_table_fixture, tables_fixture, sample_dag):
    """
    Validate that the output of merge is what we expect.
    """
    database, _ = database_table_fixture
    first_table, second_table = tables_fixture

    with sample_dag:
        aql.merge(
            target_table=first_table,
            merge_table=second_table,
            merge_keys=["id"],
            target_columns=["id", "name"],
            merge_columns=["id", "name"],
            conflict_strategy="update",
        )

    test_utils.run_dag(sample_dag)
    computed = database.export_table_to_pandas_dataframe(first_table)
    computed = computed.sort_values(by="id", ignore_index=True)
    expected = pd.DataFrame(
        [
            {"id": 1, "name": "First"},
            {"id": 2, "name": "Second"},
            {"id": 3, "name": "Third with unicode पांचाल"},
            {"id": 4, "name": "Czwarte imię"},
        ]
    )

    test_utils.assert_dataframes_are_equal(computed, expected)


@pytest.mark.integration
@pytest.mark.parametrize(
    "database_table_fixture",
    [{"database": Database.BIGQUERY}],
    indirect=True,
    ids=["bigquery"],
)
@pytest.mark.parametrize(
    "tables_fixture",
    [
        {
            "items": [
                {
                    "table": Table(
                        conn_id="bigquery",
                        metadata=Metadata(schema="first_table_schema"),
                    ),
                    "file": File(
                        str(pathlib.Path(CWD.parent.parent, "data/sample.csv"))
                    ),
                },
                {
                    "table": Table(
                        conn_id="bigquery",
                        metadata=Metadata(schema="second_table_schema"),
                    ),
                    "file": File(
                        str(pathlib.Path(CWD.parent.parent, "data/sample_part2.csv"))
                    ),
                },
            ]
        }
    ],
    indirect=True,
    ids=["two_tables"],
)
def test_merge_with_different_schemas(
    database_table_fixture, tables_fixture, sample_dag
):
    """
    Validate that the output of merge is what we expect.
    """
    database, _ = database_table_fixture
    first_table, second_table = tables_fixture

    with sample_dag:
        aql.merge(
            target_table=first_table,
            merge_table=second_table,
            merge_keys=["id"],
            target_columns=["id", "name"],
            merge_columns=["id", "name"],
            conflict_strategy="update",
        )

    test_utils.run_dag(sample_dag)
    computed = database.export_table_to_pandas_dataframe(first_table)
    computed = computed.sort_values(by="id", ignore_index=True)
    expected = pd.DataFrame(
        [
            {"id": 1, "name": "First"},
            {"id": 2, "name": "Second"},
            {"id": 3, "name": "Third with unicode पांचाल"},
            {"id": 4, "name": "Czwarte imię"},
        ]
    )

    test_utils.assert_dataframes_are_equal(computed, expected)
