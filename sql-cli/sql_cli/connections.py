from __future__ import annotations

import importlib
import os

import airflow
from airflow.api_connexion.schemas.connection_schema import connection_schema
from airflow.models import Connection
from airflow.utils.session import create_session

from sql_cli.project import Project

CONNECTION_ID_OUTPUT_STRING_WIDTH = 25


def _create_or_replace_connection(conn_obj: Connection) -> None:
    """Creates a new or replaces existing connection in the Airflow DB with the given connection object."""
    conn_id = conn_obj.conn_id
    with create_session() as session:
        db_connection = session.query(Connection).filter_by(conn_id=conn_id).one_or_none()
        if db_connection:
            session.delete(db_connection)
            session.commit()
        session.add(conn_obj)
        session.commit()


def validate_connections(
    project: Project, environment: str = "default", connection_id: str | None = None
) -> None:
    """
    Validates that the given connections are valid and registers them to Airflow with replace policy for existing
    connections.
    """
    config_file_contains_connection = False

    os.environ["AIRFLOW__DATABASE__SQL_ALCHEMY_CONN"] = "sqlite:////tmp/daniel/.airflow/default/airflow.db"
    importlib.reload(airflow)
    importlib.reload(airflow.configuration)
    importlib.reload(airflow.models.base)
    importlib.reload(airflow.models.connection)

    logs = f"\nValidating connection(s) for environment '{environment}'\n"
    for conn in project.connections:
        conn_id = conn["conn_id"]
        conn["connection_id"] = conn_id
        conn.pop("conn_id")
        data = connection_schema.load(conn)
        if connection_id and conn_id != connection_id:
            continue
        if connection_id:
            config_file_contains_connection = True
        # data["host"] = "/tmp/daniel/data/movies.db"
        conn_obj = Connection(**data)
        _create_or_replace_connection(conn_obj)

        success_status, _ = conn_obj.test_connection()
        if not success_status:
            logs += f"Validating connection {conn_id:{CONNECTION_ID_OUTPUT_STRING_WIDTH}} FAILED\n"
            continue

        logs += f"Validating connection {conn_id:{CONNECTION_ID_OUTPUT_STRING_WIDTH}} PASSED\n"

    print(logs)

    if connection_id and not config_file_contains_connection:
        print("Error: Config file does not contain given connection", connection_id)
