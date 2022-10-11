import pytest
from sql_cli.dag_generator import DagCycle


def test_sql_files_dag(sql_files_dag, sql_files_dag_with_parameters, sql_file, sql_file_with_parameters):
    """Test that a simple build will return the sql files."""
    assert sql_files_dag.sorted_sql_files() == [sql_file]
    assert sql_files_dag_with_parameters.sorted_sql_files() == [sql_file_with_parameters]


def test_sql_files_dag_raises_exception(sql_files_dag_with_cycle):
    """Test that an exception is being raised when it is not a DAG."""
    with pytest.raises(DagCycle):
        assert sql_files_dag_with_cycle.sorted_sql_files()
