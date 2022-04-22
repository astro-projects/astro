import pytest
from pandas import DataFrame

from astro.databases.base import BaseDatabase
from astro.sql.tables import Table


class DatabaseSubclass(BaseDatabase):
    pass


def test_subclass_missing_hook_raises_exception():
    db = DatabaseSubclass(conn_id="fake_conn_id")
    with pytest.raises(NotImplementedError):
        db.hook


def test_subclass_missing_get_table_qualified_name_raises_exception():
    db = DatabaseSubclass(conn_id="fake_conn_id")
    table = Table()
    with pytest.raises(NotImplementedError):
        db.get_table_qualified_name(table)


def test_subclass_missing_load_file_to_table_raises_exception():
    db = DatabaseSubclass(conn_id="fake_conn_id")
    table = Table()
    filepath = "/tmp/filepath.csv"
    with pytest.raises(NotImplementedError):
        db.load_file_to_table(filepath, table)


def test_subclass_missing_load_pandas_dataframe_to_table_raises_exception():
    db = DatabaseSubclass(conn_id="fake_conn_id")
    table = Table()
    df = DataFrame()
    with pytest.raises(NotImplementedError):
        db.load_pandas_dataframe_to_table(df, table)


def test_subclass_missing_export_table_to_file_raises_exception():
    db = DatabaseSubclass(conn_id="fake_conn_id")
    table = Table()
    filepath = "/tmp/filepath.csv"
    with pytest.raises(NotImplementedError):
        db.export_table_to_file(table, filepath)


def test_subclass_missing_export_table_to_pandas_dataframe_raises_exception():
    db = DatabaseSubclass(conn_id="fake_conn_id")
    table = Table()
    with pytest.raises(NotImplementedError):
        db.export_table_to_pandas_dataframe(table)
