import os
import pathlib

import pandas as pd
import pytest

from astro.constants import Database
from astro.files import File
from astro.utils.load import copy_remote_file_to_local
from tests.sql.operators import utils as test_utils

DEFAULT_CONN_ID = "sftp_conn"
CWD = pathlib.Path(__file__).parent


@pytest.mark.integration
@pytest.mark.parametrize(
    "database_table_fixture",
    [
        {
            "database": Database.POSTGRES,
            "file": File(str(pathlib.Path(CWD.parent.parent, "data/sample.csv"))),
        }
    ],
    indirect=True,
    ids=["postgres"],
)
def test_export_table_to_file_in_the_cloud(database_table_fixture):
    """Test export_table_to_file_file() where end file location is in cloud object stores"""
    object_path = "sftp://upload/test.csv"
    database, populated_table = database_table_fixture
    database.export_table_to_file(
        populated_table,
        File(object_path, conn_id=DEFAULT_CONN_ID),
        if_exists="replace",
    )

    filepath = copy_remote_file_to_local(
        source_filepath=object_path, transport_params={"connect_kwargs": {"password": "foo"}}
    )
    df = pd.read_csv(filepath)
    assert len(df) == 3
    expected = pd.DataFrame(
        [
            {"id": 1, "name": "First"},
            {"id": 2, "name": "Second"},
            {"id": 3, "name": "Third with unicode पांचाल"},
        ]
    )
    test_utils.assert_dataframes_are_equal(df, expected)
    os.remove(filepath)
