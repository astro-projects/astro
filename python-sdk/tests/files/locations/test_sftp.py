import json
from unittest.mock import patch

from airflow.models.connection import Connection
from airflow.providers.sftp.hooks.sftp import SFTPHook

from astro.files.locations import create_file_location


@patch("airflow.providers.sftp.hooks.sftp.SFTPHook.get_connection")
def test_get_transport_params_for_sftp(mock_sftp_hook):  # skipcq: PYL-W0612, PTC-W0065
    """test get_transport_params() method which should return connect_kwargs when keyfile is passed"""
    mock_sftp_hook.return_value = Connection(
        conn_id="sftp_default",
        conn_type="test",
        login=1234,
        host="localhost",
        extra=json.dumps({"key_file": "/some/local/path/rsa.pem"}),
    )
    path = "sftp://bucket/some-file"
    location = create_file_location(path)
    credentials = location.transport_params
    assert credentials == {"connect_kwargs": {"key_filename": "/some/local/path/rsa.pem"}}


@patch("airflow.providers.sftp.hooks.sftp.SFTPHook.get_connection")
def test_get_transport_params_for_sftp_no_value(mock_sftp_hook):  # skipcq: PYL-W0612, PTC-W0065
    """test get_transport_params() method when no keyfile is passed"""
    mock_sftp_hook.return_value = Connection(
        conn_id="sftp_default",
        conn_type="test",
        login=1234,
        host="localhost",
    )
    path = "sftp://bucket/some-file"
    location = create_file_location(path)
    credentials = location.transport_params
    assert credentials == {}


@patch("airflow.providers.sftp.hooks.sftp.SFTPHook.get_connection")
def test_get_transport_params_for_sftp_password(mock_sftp_hook):  # skipcq: PYL-W0612, PTC-W0065
    """test get_transport_params() method when no keyfile is passed"""
    mock_sftp_hook.return_value = Connection(
        conn_id="sftp_default", conn_type="test", login=1234, host="localhost", password="test"
    )
    path = "sftp://bucket/some-file"
    location = create_file_location(path)
    credentials = location.transport_params
    assert credentials == {"connect_kwargs": {"password": "test"}}


@patch("airflow.providers.sftp.hooks.sftp.SFTPHook.isdir")
@patch("airflow.providers.sftp.hooks.sftp.SFTPHook.list_directory")
@patch("airflow.providers.sftp.hooks.sftp.SFTPHook.get_connection")
def test_get_paths_from_sftp(mock_sftp_conn, mock_list, mock_isdir):
    """Get the list of files from the sftp path"""
    mock_sftp_conn.return_value = Connection(
        conn_id="sftp_default", conn_type="test", login=1234, host="localhost", password="test", port=1234
    )
    mock_isdir.return_value = True
    mock_list.return_value = ["sample.csv"]
    location = create_file_location("sftp://user@host/some")
    assert sorted(location.paths) == sorted(["sftp://user@host:1234/some/sample.csv"])
    mock_isdir.return_value = False
    assert sorted(location.paths) == sorted(["sftp://user@host:1234/some"])


@patch("airflow.providers.sftp.hooks.sftp.SFTPHook.get_conn")
def test_size(mock_get_conn):
    """Test get_size() of for Google Drive file."""

    mock_get_conn.return_value.stat.return_value.st_size = 110
    location = create_file_location("sftp://user@host/some")
    assert location.size == 110


def test_hook():
    """Test whether GoogleDriveHook is being called or not."""
    location = create_file_location("sftp://user@host/some")
    hook = location.hook
    assert isinstance(hook, SFTPHook)
