"""
Tests specific to the Sqlite Database implementation.
"""
import pathlib
from urllib.parse import urlparse

import pandas as pd
import pytest
import sqlalchemy

from astro.constants import Database
from astro.databases import get_database_from_conn_id
from astro.databases.sqlite import SqliteDatabase
from astro.sql.tables import Table
from tests.operators import utils as test_utils

DEFAULT_CONN_ID = "sqlite_default"
CUSTOM_CONN_ID = "sqlite_conn"
SUPPORTED_CONN_IDS = [DEFAULT_CONN_ID, CUSTOM_CONN_ID]
CWD = pathlib.Path(__file__).parent


TEST_TABLE = Table()


@pytest.mark.parametrize("conn_id", SUPPORTED_CONN_IDS)
def test_get_database_from_conn_id(conn_id):
    database = get_database_from_conn_id(conn_id)
    assert isinstance(database, SqliteDatabase)


@pytest.mark.parametrize(
    "conn_id,expected_uri",
    [
        (DEFAULT_CONN_ID, "//tmp/sqlite_default.db"),
        (CUSTOM_CONN_ID, "////tmp/sqlite.db"),
    ],
    ids=SUPPORTED_CONN_IDS,
)
def test_sqlite_sqlalchemy_engine(conn_id, expected_uri):
    database = SqliteDatabase(conn_id)
    engine = database.sqlalchemy_engine
    assert isinstance(engine, sqlalchemy.engine.base.Engine)
    url = urlparse(str(engine.url))
    assert url.path == expected_uri


@pytest.mark.integration
def test_sqlite_run_sql():
    statement = "SELECT 1 + 1;"
    database = SqliteDatabase()
    response = database.run_sql(statement)
    assert response.first()[0] == 2


@pytest.mark.parametrize(
    "database_table_fixture",
    [
        {
            "database": Database.SQLITE,
            "table": Table(
                columns=[
                    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
                    sqlalchemy.Column(
                        "name", sqlalchemy.String(60), nullable=False, key="name"
                    ),
                ]
            ),
        }
    ],
    indirect=True,
)
@pytest.mark.integration
def test_sqlite_create_table_with_columns(database_table_fixture):
    database, table = database_table_fixture

    statement = f"PRAGMA table_info({table.name});"
    response = database.run_sql(statement)
    assert response.first() is None

    database.create_table(table)
    response = database.run_sql(statement)
    rows = response.fetchall()
    assert len(rows) == 2
    assert rows[0] == (0, "id", "INTEGER", 1, None, 1)
    assert rows[1] == (1, "name", "VARCHAR(60)", 1, None, 0)


@pytest.mark.parametrize(
    "database_table_fixture",
    [
        {"database": Database.SQLITE},
    ],
    indirect=True,
)
@pytest.mark.integration
def test_load_pandas_dataframe_to_table(database_table_fixture):
    database, table = database_table_fixture

    pandas_dataframe = pd.DataFrame(data={"id": [1, 2]})
    database.load_pandas_dataframe_to_table(pandas_dataframe, table)

    statement = f"SELECT * FROM {table.name};"
    response = database.run_sql(statement)

    rows = response.fetchall()
    assert len(rows) == 2
    assert rows[0] == (1,)
    assert rows[1] == (2,)


@pytest.mark.parametrize(
    "database_table_fixture",
    [
        {"database": Database.SQLITE},
    ],
    indirect=True,
)
@pytest.mark.integration
def test_load_file_to_table(database_table_fixture):
    database, target_table = database_table_fixture
    filepath = pathlib.Path(CWD.parent, "data/sample.csv")
    database.load_file_to_table(filepath, target_table)

    df = database.hook.get_pandas_df(f"SELECT * FROM {target_table.name}")
    assert len(df) == 3
    expected = pd.DataFrame(
        [
            {"id": 1, "name": "First"},
            {"id": 2, "name": "Second"},
            {"id": 3, "name": "Third with unicode पांचाल"},
        ]
    )
    test_utils.assert_dataframes_are_equal(df, expected)


@pytest.mark.parametrize(
    "database_table_fixture",
    [
        {"database": Database.SQLITE},
    ],
    indirect=True,
)
@pytest.mark.integration
def test_export_table_to_file_file_already_exists_raises_exception(
    database_table_fixture,
):
    database, source_table = database_table_fixture
    filepath = pathlib.Path(CWD.parent, "data/sample.csv")
    with pytest.raises(FileExistsError) as exception_info:
        database.export_table_to_file(source_table, filepath)
    err_msg = exception_info.value.args[0]
    assert err_msg.startswith("The file")
    assert err_msg.endswith("tests/data/sample.csv already exists.")


@pytest.mark.parametrize(
    "database_table_fixture",
    [
        {
            "database": Database.SQLITE,
            "filepath": pathlib.Path(CWD.parent, "data/sample.csv"),
        }
    ],
    indirect=True,
)
@pytest.mark.integration
def test_export_table_to_file_overrides_existing_file(database_table_fixture):
    database, populated_table = database_table_fixture

    filepath = str(pathlib.Path(CWD.parent, "data/sample.csv"))
    database.export_table_to_file(populated_table, filepath, if_exists="replace")

    df = test_utils.load_to_dataframe(filepath, "csv")
    assert len(df) == 3
    expected = pd.DataFrame(
        [
            {"id": 1, "name": "First"},
            {"id": 2, "name": "Second"},
            {"id": 3, "name": "Third with unicode पांचाल"},
        ]
    )
    assert df.rename(columns=str.lower).equals(expected)


@pytest.mark.parametrize(
    "database_table_fixture",
    [
        {
            "database": Database.SQLITE,
            "filepath": pathlib.Path(CWD.parent, "data/sample.csv"),
        }
    ],
    indirect=True,
)
@pytest.mark.parametrize(
    "cloud_object_fixture",
    [{"provider": "google", "extension": "csv"}],
    indirect=True,
)
@pytest.mark.integration
def test_export_table_to_file_in_the_cloud(
    database_table_fixture, cloud_object_fixture
):
    object_path, hook = cloud_object_fixture
    database, populated_table = database_table_fixture

    database.export_table_to_file(
        populated_table,
        object_path,
        if_exists="replace",
    )
    object_prefix = object_path[object_path.find("test") :]
    bucket = object_path[object_path.find("//") + 2 : object_path.find("/test")]
    file_content = hook.download(bucket, object_prefix).decode("utf-8")
    expected = "id,name\n1,First\n2,Second\n3,Third with unicode पांचाल\n"
    assert file_content == expected


@pytest.mark.parametrize(
    "database_table_fixture",
    [
        {
            "database": Database.SQLITE,
            "filepath": pathlib.Path(CWD.parent, "data/sample.csv"),
        }
    ],
    indirect=True,
)
def test_create_table_from_select_statement(database_table_fixture):
    database, original_table = database_table_fixture

    statement = "SELECT * FROM {} WHERE id = 1;".format(
        database.get_table_qualified_name(original_table)
    )
    target_table = Table()
    database.create_table_from_select_statement(statement, target_table)

    df = database.hook.get_pandas_df(f"SELECT * FROM {target_table.name}")
    assert len(df) == 1
    expected = pd.DataFrame([{"id": 1, "name": "First"}])
    test_utils.assert_dataframes_are_equal(df, expected)
    database.drop_table(target_table)
