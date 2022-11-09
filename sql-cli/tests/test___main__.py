import pathlib
from tempfile import gettempdir

import pytest
from typer.testing import CliRunner

from sql_cli import __version__
from sql_cli.__main__ import app
from sql_cli.connections import CONNECTION_ID_OUTPUT_STRING_WIDTH
from tests.utils import list_dir
import datetime
runner = CliRunner()

CWD = pathlib.Path(__file__).parent


def get_stdout(result) -> str:
    """
    Get the results stdout without line breaks.

    :params result: The result object.

    :returns: the stdout without line breaks.
    """
    return result.stdout.replace("\n", "")


@pytest.mark.parametrize(
    "args",
    [
        ["--help"],
        ["version", "--help"],
    ],
    ids=[
        "group",
        "command",
    ],
)
@pytest.mark.parametrize(
    "env,usage",
    [
        ({}, "Usage: flow"),
        ({"ASTRO_CLI": "Yes"}, "Usage: astro flow"),
    ],
    ids=[
        "sql-cli",
        "astro-cli",
    ],
)
def test_usage(env, usage, args):
    result = runner.invoke(app, args, env=env)
    assert result.exit_code == 0
    assert usage in get_stdout(result)


def test_about():
    result = runner.invoke(app, ["about"])
    assert result.exit_code == 0
    assert "Find out more: https://docs.astronomer.io/astro/cli/sql-cli" == get_stdout(result)


def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert f"Astro SQL CLI {__version__}" == get_stdout(result)


@pytest.mark.parametrize(
    "workflow_name,environment",
    [
        ("example_basic_transform", "default"),
        ("example_templating", "dev"),
    ],
)
def test_generate(workflow_name, environment, initialised_project):
    result = runner.invoke(
        app,
        [
            "generate",
            workflow_name,
            "--env",
            environment,
            "--project-dir",
            initialised_project.directory.as_posix(),
        ],
    )
    assert result.exit_code == 0, result.output
    result_stdout = get_stdout(result)
    assert (
        f"The DAG file {initialised_project.airflow_dags_folder}/{workflow_name}.py has been successfully generated. 🎉"
        in result_stdout
    )


@pytest.mark.parametrize(
    "workflow_name,message",
    [
        ("non_existing", "The workflow non_existing does not exist!"),
        ("cycle", "The workflow cycle contains a cycle! A cycle between d and d has been detected!"),
        ("empty", "The workflow empty does not have any SQL files!"),
    ],
    ids=[
        "non_existing",
        "cycle",
        "empty",
    ],
)
def test_generate_invalid(workflow_name, message, initialised_project_with_tests_workflows):
    result = runner.invoke(
        app,
        [
            "generate",
            workflow_name,
            "--project-dir",
            initialised_project_with_tests_workflows.directory.as_posix(),
        ],
    )
    assert result.exit_code == 1
    result_stdout = get_stdout(result)
    assert message in result_stdout


@pytest.mark.parametrize(
    "env,connection,status",
    [
        ("default", "sqlite_conn", "PASSED"),
        ("test", "sqlite_conn_invalid", "FAILED"),
    ],
)
def test_validate(env, connection, status, initialised_project_with_test_config):
    result = runner.invoke(
        app,
        [
            "validate",
            initialised_project_with_test_config.directory.as_posix(),
            "--env",
            env,
            "--connection",
            connection,
        ],
    )
    assert result.exit_code == 0, result.exception
    output = get_stdout(result)
    assert f"Validating connection(s) for environment '{env}'" in output
    assert f"Validating connection {connection:{CONNECTION_ID_OUTPUT_STRING_WIDTH}} {status}" in output


def test_validate_all(initialised_project_with_test_config):
    result = runner.invoke(
        app,
        [
            "validate",
            initialised_project_with_test_config.directory.as_posix(),
        ],
    )
    assert result.exit_code == 0
    output = get_stdout(result)
    assert output.startswith("Validating connection(s)")


@pytest.mark.parametrize(
    "workflow_name,environment",
    [
        ("example_basic_transform", "default"),
        ("example_templating", "dev"),
    ],
)
@pytest.mark.parametrize("generate_tasks", ["--generate-tasks", "--no-generate-tasks"])
def test_run(workflow_name, environment, initialised_project, generate_tasks):
    result = runner.invoke(
        app,
        [
            "run",
            workflow_name,
            "--env",
            environment,
            "--project-dir",
            initialised_project.directory.as_posix(),
            generate_tasks,
        ],
    )
    assert result.exit_code == 0, result.output
    result_stdout = get_stdout(result)
    assert f"Completed running the workflow {workflow_name}. 🚀" in result_stdout
from unittest import TestCase, mock

@pytest.mark.parametrize("generate_tasks", ["--generate-tasks", "--no-generate-tasks"])
@mock.patch("sql_cli.cli.run_dag")
@pytest.mark.parametrize("final_state,message", [
    ("FAILED","Final state: FAILED"),
    ("SKIPPED","Final state: SKIPPED")
], ids=["failed", "skipped"])
def test_run_state(mock_run_dag, initialised_project, generate_tasks, final_state, message):
    workflow_name = "example_basic_transform"
    environment="dev"
    mock_run_dag.return_value = mock.MagicMock(state=final_state, dag_id=workflow_name, start_date=datetime.datetime(2020,1,1),  end_date=datetime.datetime(2020,1,1))

    result = runner.invoke(
        app,
        [
            "run",
            workflow_name,
            "--env",
            environment,
            "--project-dir",
            initialised_project.directory.as_posix(),
            generate_tasks,
        ],
    )
    assert result.exit_code == 0, result.output
    result_stdout = get_stdout(result)
    assert message in result_stdout

@pytest.mark.parametrize(
    "workflow_name,message",
    [
        ("non_existing", "The workflow non_existing does not exist!"),
        ("cycle", "The workflow cycle contains a cycle! A cycle between d and d has been detected!"),
        ("empty", "The workflow empty does not have any SQL files!"),
        ("undefined_variable", "'foo' is undefined"),
        ("missing_table_or_conn_id", "You need to provide a table or a connection id"),
        ("example_templating", "no such table: orders using connection sqlite_conn"),
    ],
    ids=[
        "non_existing",
        "cycle",
        "empty",
        "undefined_variable",
        "missing_table_or_conn_id",
        "example_templating",
    ],
)
@pytest.mark.parametrize("generate_tasks", ["--generate-tasks", "--no-generate-tasks"])
def test_run_invalid(workflow_name, message, initialised_project_with_tests_workflows, generate_tasks):
    result = runner.invoke(
        app,
        [
            "run",
            workflow_name,
            "--project-dir",
            initialised_project_with_tests_workflows.directory.as_posix(),
            generate_tasks,
        ],
    )
    assert result.exit_code == 1
    result_stdout = get_stdout(result)
    assert message in result_stdout


def test_init_with_directory(tmp_path):
    result = runner.invoke(app, ["init", tmp_path.as_posix()])
    assert result.exit_code == 0
    expected_msg = f"Initialized an Astro SQL project at {tmp_path.as_posix()}"
    assert expected_msg in get_stdout(result)
    assert list_dir(tmp_path.as_posix())


def test_init_with_custom_airflow_config(tmp_path):
    tmp_dir = gettempdir()
    result = runner.invoke(
        app, ["init", tmp_path.as_posix(), "--airflow-home", tmp_dir, "--airflow-dags-folder", tmp_dir]
    )
    assert result.exit_code == 0
    expected_msg = f"Initialized an Astro SQL project at {tmp_path.as_posix()}"
    assert expected_msg in get_stdout(result)
    assert list_dir(tmp_path.as_posix())


def test_init_without_directory():
    # Creates a temporary directory and cd into it.
    # This isolates tests that affect the contents of the CWD to prevent them from interfering with each other.
    with runner.isolated_filesystem() as temp_dir:
        assert not list_dir(temp_dir)
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        expected_msg = "Initialized an Astro SQL project at"
        result_stdout = get_stdout(result)
        # We are not checking the full temp_dir because in MacOS the temp directory starts with /private
        assert result_stdout.startswith(expected_msg)
        assert result_stdout.endswith(temp_dir)
        assert list_dir(temp_dir)
